"""Sign in with Google / Apple (2026-11-21). The provider round trip is mocked
at `oauth.exchange_code`; everything on our side — flow cookie, state check,
account linking, session — runs for real. DB-gated like test_account.
"""

from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.account import oauth
from app.api import account as account_api
from app.config import get_settings
from app.main import app

ACCT_COOKIE = get_settings().app_auth_cookie_name


@pytest.fixture(autouse=True)
def _providers(monkeypatch):
    s = get_settings()
    for key, value in {
        "google_oauth_client_id": "google-client",
        "google_oauth_client_secret": "google-secret",
        "apple_oauth_client_id": "apple-client",
        "apple_oauth_team_id": "TEAM",
        "apple_oauth_key_id": "KEY",
        "apple_oauth_private_key": "pem",
        "account_smtp_host": "smtp.test",
        "account_smtp_from": "noreply@test.example",
    }.items():
        monkeypatch.setattr(s, key, value)
    # Into the outbox the shared `_register` helper of test_account reads.
    from tests.test_account import MAIL_OUTBOX

    MAIL_OUTBOX.clear()
    monkeypatch.setattr(
        account_api, "send_account_link",
        lambda address, *, purpose, token: MAIL_OUTBOX.append((address, purpose, token)),
    )


def _identity(monkeypatch, *, provider="google", subject=None, email=None, verified=True, name="Kim Surfer"):
    subject = subject or uuid.uuid4().hex
    seen = {}

    def fake_exchange(p, *, code, verifier, nonce, apple_name=None):
        seen.update(provider=p, code=code, verifier=verifier, nonce=nonce, apple_name=apple_name)
        return oauth.Identity(provider=p, subject=subject, email=email, email_verified=verified, name=apple_name or name)

    monkeypatch.setattr(oauth, "exchange_code", fake_exchange)
    return seen


def _start(c: TestClient, provider="google", redirect="/konto/favoriten") -> str:
    resp = c.get(f"/account/oauth/{provider}/start", params={"redirect": redirect}, follow_redirects=False)
    assert resp.status_code == 302, resp.text
    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    return query["state"][0]


def test_providers_lists_only_configured_ones(anon_client, monkeypatch):
    assert anon_client.get("/account/oauth/providers").json() == {"google": True, "apple": True}
    monkeypatch.setattr(get_settings(), "apple_oauth_private_key", None)
    assert anon_client.get("/account/oauth/providers").json() == {"google": True, "apple": False}
    assert anon_client.get("/account/oauth/apple/start", follow_redirects=False).status_code == 404


def test_google_sign_in_creates_a_confirmed_account_and_session(anon_client, monkeypatch):
    email = f"g-{uuid.uuid4().hex[:8]}@example.com"
    seen = _identity(monkeypatch, email=email)
    state = _start(anon_client)
    resp = anon_client.get(
        "/account/oauth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/konto/favoriten")
    assert seen["code"] == "abc" and seen["verifier"] and seen["nonce"]
    me = anon_client.get("/account/me").json()
    assert me["email"] == email and me["displayName"] == "Kim Surfer" and me["emailVerified"] is True

    from app.db.session import SessionLocal
    from app.models import AppUser

    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == email))
        assert user.terms_accepted_at is not None and user.age_confirmed_at is not None


def test_a_wrong_or_missing_state_is_refused(anon_client, monkeypatch):
    _identity(monkeypatch, email=f"s-{uuid.uuid4().hex[:8]}@example.com")
    _start(anon_client)
    resp = anon_client.get(
        "/account/oauth/google/callback", params={"code": "abc", "state": "forged"}, follow_redirects=False
    )
    assert resp.status_code == 303 and "oauth_error=failed" in resp.headers["location"]
    # No flow cookie at all (another browser): refused too.
    other = TestClient(app)
    resp = other.get(
        "/account/oauth/google/callback", params={"code": "abc", "state": "x"}, follow_redirects=False
    )
    assert "oauth_error=expired" in resp.headers["location"]
    assert not other.cookies.get(ACCT_COOKIE)


def test_the_same_identity_signs_into_the_same_account(anon_client, monkeypatch):
    email = f"same-{uuid.uuid4().hex[:8]}@example.com"
    _identity(monkeypatch, subject="sub-fixed-" + email, email=email)
    state = _start(anon_client)
    anon_client.get("/account/oauth/google/callback", params={"code": "a", "state": state}, follow_redirects=False)
    first = anon_client.get("/account/me").json()["id"]
    again = TestClient(app)
    state = _start(again)
    again.get("/account/oauth/google/callback", params={"code": "b", "state": state}, follow_redirects=False)
    assert again.get("/account/me").json()["id"] == first


def test_links_to_a_confirmed_account_with_the_same_email(anon_client, monkeypatch):
    from tests.test_account import _register

    acct = _register(TestClient(app))
    _identity(monkeypatch, email=acct["email"])
    state = _start(anon_client)
    anon_client.get("/account/oauth/google/callback", params={"code": "a", "state": state}, follow_redirects=False)
    assert anon_client.get("/account/me").json()["id"] == acct["body"]["id"]
    # The password still works: linking adds a way in, it takes none away.
    assert TestClient(app).post("/account/login", json={
        "email": acct["email"], "password": acct["password"],
    }).status_code == 200


def test_linking_an_unconfirmed_account_discards_the_registrants_password(anon_client, monkeypatch):
    email = f"hijack-{uuid.uuid4().hex[:8]}@example.com"
    # Someone registers the owner's address with their own password and never confirms.
    attacker = TestClient(app)
    assert attacker.post("/account/register", json={
        "email": email, "password": "attacker-pw-123", "acceptedTerms": True,
    }).status_code == 202
    # The owner signs in with Google: the address is now proven…
    _identity(monkeypatch, email=email)
    state = _start(anon_client)
    anon_client.get("/account/oauth/google/callback", params={"code": "a", "state": state}, follow_redirects=False)
    assert anon_client.get("/account/me").json()["emailVerified"] is True
    # …and the registrant's password does not open the now confirmed account.
    assert TestClient(app).post("/account/login", json={
        "email": email, "password": "attacker-pw-123",
    }).status_code == 401


def test_an_unverified_provider_email_creates_nothing(anon_client, monkeypatch):
    email = f"unv-{uuid.uuid4().hex[:8]}@example.com"
    _identity(monkeypatch, email=email, verified=False)
    state = _start(anon_client)
    resp = anon_client.get(
        "/account/oauth/google/callback", params={"code": "a", "state": state}, follow_redirects=False
    )
    assert "oauth_error=account" in resp.headers["location"]
    assert anon_client.get("/account/me").status_code == 401


def test_the_redirect_target_stays_on_this_site(anon_client, monkeypatch):
    _identity(monkeypatch, email=f"r-{uuid.uuid4().hex[:8]}@example.com")
    for target in ("https://evil.example/", "//evil.example/x", "/\\evil.example"):
        state = _start(anon_client, redirect=target)
        resp = anon_client.get(
            "/account/oauth/google/callback", params={"code": "a", "state": state}, follow_redirects=False
        )
        location = resp.headers["location"]
        assert location == f"{get_settings().account_public_origin.rstrip('/')}/konto", location


def test_apple_form_post_signs_in_even_with_a_session_already_present(anon_client, monkeypatch):
    from tests.test_account import _register

    _register(anon_client)  # a signed-in browser: CSRF middleware must not block Apple's POST
    email = f"a-{uuid.uuid4().hex[:8]}@privaterelay.appleid.com"
    seen = _identity(monkeypatch, provider="apple", email=email)
    state = _start(anon_client, provider="apple")
    resp = anon_client.post(
        "/account/oauth/apple/callback",
        data={"code": "apple-code", "state": state, "user": '{"name":{"firstName":"Kim","lastName":"Surfer"}}'},
        headers={"origin": "https://appleid.apple.com"},
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    assert seen["apple_name"] == "Kim Surfer"
    assert anon_client.get("/account/me").json()["email"] == email


def test_provider_refusal_returns_to_the_page_with_a_reason(anon_client):
    resp = anon_client.get(
        "/account/oauth/google/callback", params={"error": "access_denied"}, follow_redirects=False
    )
    assert "oauth_error=denied" in resp.headers["location"]
