"""Public account tests: sign-up, session, profile, favourites, proposals, and
the admin/app token separation. DB-gated (touches app_users / favorites).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.main import app
from app.models import Favorite, Spot, SpotSubmission
from app.api import account as account_api

ACCT_COOKIE = get_settings().app_auth_cookie_name
MAIL_OUTBOX: list[tuple[str, str, str]] = []


@pytest.fixture(autouse=True)
def _account_mail(monkeypatch):
    MAIL_OUTBOX.clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "account_smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "account_smtp_from", "noreply@test.example")
    monkeypatch.setattr(
        account_api, "send_account_link",
        lambda address, *, purpose, token: MAIL_OUTBOX.append((address, purpose, token)),
    )
    monkeypatch.setattr(account_api, "send_account_notice", lambda *args, **kwargs: None)


def _register(c: TestClient, email: str | None = None, pw: str = "pw-123456789") -> dict:
    email = email or f"visitor-{uuid.uuid4().hex[:8]}@example.com"
    resp = c.post(
        "/account/register",
        json={"email": email, "displayName": "Test Visitor"},
    )
    assert resp.status_code == 202, resp.text
    assert MAIL_OUTBOX[-1][1] == "verify"
    confirm = c.post("/account/email/confirm", json={
        "token": MAIL_OUTBOX[-1][2], "password": pw,
    })
    assert confirm.status_code == 200, confirm.text
    login = c.post("/account/login", json={"email": email, "password": pw})
    assert login.status_code == 200, login.text
    c.headers["X-CSRF-Token"] = c.cookies.get(get_settings().csrf_cookie_name)
    return {"email": email, "password": pw, "body": login.json(), "client": c}


@pytest.fixture
def acct(anon_client):
    """A freshly-registered, logged-in visitor on a clean client."""
    return _register(anon_client)


@pytest.fixture
def spot_id(client):
    """A real published-able spot to favourite, via the admin client."""
    suffix = uuid.uuid4().hex[:8]
    rid = client.post("/admin/regions", json={
        "name": f"Acct Region {suffix}", "slug": f"acct-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    }).json()["id"]
    return client.post("/admin/spots", json={
        "name": f"Acct Spot {suffix}", "slug": f"acct-spot-{suffix}",
        "region_id": rid, "lat": 54.41, "lon": 10.22, "sports": ["kitesurf"],
    }).json()["id"]


@pytest.fixture(autouse=True)
def _cleanup(db):
    """Spots first, before the region — see the identical fix in
    test_admin_moderation for why."""
    from sqlalchemy import delete

    yield
    from app.models import Region, Spot

    regions = db.scalars(
        select(Region).where(Region.slug.like("acct-region-%"))
    ).all()
    if not regions:
        return
    ids = [region.id for region in regions]
    db.execute(delete(Spot).where(Spot.region_id.in_(ids)))
    db.execute(delete(Region).where(Region.id.in_(ids)))
    db.commit()


# --- registration / session ------------------------------------------------

def test_register_then_login_returns_account(acct):
    body = acct["body"]
    assert body["email"] == acct["email"]
    assert body["displayName"] == "Test Visitor"
    assert body["id"] and body["createdAt"]
    assert acct["client"].cookies.get(ACCT_COOKIE)


def test_registration_requires_mail_ownership_and_new_password(anon_client):
    email = f"verify-{uuid.uuid4().hex[:8]}@example.com"
    resp = anon_client.post("/account/register", json={
        "email": email, "displayName": "Visitor",
    })
    assert resp.status_code == 202
    assert anon_client.post("/account/login", json={
        "email": email, "password": "attacker-pw-123",
    }).status_code == 401
    token = MAIL_OUTBOX[-1][2]
    assert anon_client.post("/account/email/confirm", json={"token": token}).status_code == 400
    assert anon_client.post("/account/email/confirm", json={
        "token": token, "password": "owner-pw-123",
    }).status_code == 200
    assert anon_client.post("/account/login", json={
        "email": email, "password": "attacker-pw-123",
    }).status_code == 401
    assert anon_client.post("/account/login", json={
        "email": email, "password": "owner-pw-123",
    }).status_code == 200


def test_register_duplicate_email_has_generic_response(anon_client):
    first = _register(anon_client)
    other = TestClient(app)
    dup = other.post("/account/register", json={
        "email": first["email"], "displayName": "X",
    })
    assert dup.status_code == 202
    assert dup.json() == {
        "accepted": True,
        "message": "Falls noch kein Konto existierte, wurde ein Bestätigungslink versendet.",
    }


def test_confirmation_weak_password_rejected(anon_client):
    resp = anon_client.post("/account/register", json={
        "email": f"weak-{uuid.uuid4().hex[:8]}@example.com", "displayName": "X",
    })
    assert resp.status_code == 202
    assert anon_client.post("/account/email/confirm", json={
        "token": MAIL_OUTBOX[-1][2], "password": "123",
    }).status_code == 400


def test_login_me_logout_flow(acct):
    c = acct["client"]
    assert c.get("/account/me").json()["email"] == acct["email"]
    assert c.post("/account/logout").status_code == 204
    assert c.get("/account/me").status_code == 401
    # log back in on a fresh client
    fresh = TestClient(app)
    login = fresh.post("/account/login", json={
        "email": acct["email"], "password": acct["password"],
    })
    assert login.status_code == 200
    assert fresh.get("/account/me").status_code == 200


def test_login_wrong_password_401(acct):
    fresh = TestClient(app)
    resp = fresh.post("/account/login", json={
        "email": acct["email"], "password": "wrong",
    })
    assert resp.status_code == 401
    assert not fresh.cookies.get(ACCT_COOKIE)


def test_me_requires_auth(anon_client):
    assert anon_client.get("/account/me").status_code == 401


# --- token separation ------------------------------------------------------

def test_admin_token_is_rejected_by_account_api(acct):
    """An admin session JWT placed in the account cookie must not authenticate —
    the typ claim separates the two audiences."""
    from app.auth.security import create_session_token

    admin_token = create_session_token(uuid.uuid4(), "admin")
    c = TestClient(app)
    c.cookies.set(ACCT_COOKIE, admin_token)
    assert c.get("/account/me").status_code == 401


def test_account_token_is_rejected_by_admin_api(acct):
    """Symmetric: an app session cookie must not open the admin /auth/me."""
    from app.config import get_settings as gs

    token = acct["client"].cookies.get(ACCT_COOKIE)
    c = TestClient(app)
    c.cookies.set(gs().auth_cookie_name, token)
    assert c.get("/auth/me").status_code == 401


# --- profile / password ----------------------------------------------------

def test_update_profile_name_and_email(acct):
    c = acct["client"]
    new_email = f"renamed-{uuid.uuid4().hex[:8]}@example.com"
    resp = c.patch("/account/profile", json={"displayName": "Neuer Name"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["displayName"] == "Neuer Name"
    change = c.post("/account/email/change", json={
        "email": new_email, "password": acct["password"],
    })
    assert change.status_code == 200, change.text
    assert change.json()["email"] == acct["email"]
    assert change.json()["pendingEmail"] == new_email
    first_token = MAIL_OUTBOX[-1][2]
    resent = c.post("/account/email/change", json={
        "email": new_email, "password": acct["password"],
    })
    assert resent.status_code == 200, resent.text
    assert c.post("/account/email/confirm", json={"token": first_token}).status_code == 400
    assert c.post("/account/email/confirm", json={"token": MAIL_OUTBOX[-1][2]}).status_code == 200
    assert c.get("/account/me").status_code == 401
    assert c.post("/account/login", json={
        "email": new_email, "password": acct["password"],
    }).status_code == 200


def test_update_profile_duplicate_email_409(acct):
    other = _register(TestClient(app))
    resp = acct["client"].post("/account/email/change", json={
        "email": other["email"], "password": acct["password"],
    })
    assert resp.status_code == 400


def test_change_password(acct):
    c = acct["client"]
    # wrong current password
    assert c.post("/account/password", json={
        "oldPassword": "nope", "newPassword": "brandnew-123",
    }).status_code == 400
    # correct
    assert c.post("/account/password", json={
        "oldPassword": acct["password"], "newPassword": "brandnew-123",
    }).status_code == 204
    assert c.get("/account/me").status_code == 200
    # new password works
    fresh = TestClient(app)
    assert fresh.post("/account/login", json={
        "email": acct["email"], "password": "brandnew-123",
    }).status_code == 200


def test_preferences_persist_and_are_exported(acct):
    c = acct["client"]
    preferences = {
        "units": {"wind": "bft", "wave": "ft", "temp": "f", "distance": "mi"},
        "sports": ["wing", "kitesurf"], "submissionEmails": True,
        "conditions": {
            "wing": {"windMinKn": 12, "windMaxKn": 28, "waveMaxM": 1.5},
            "kitesurf": {"windMinKn": 14, "waterTempMinC": 10},
        },
    }
    changed = c.patch("/account/preferences", json=preferences)
    assert changed.status_code == 200, changed.text
    assert changed.json()["preferences"] == preferences
    assert c.get("/account/me").json()["preferences"] == preferences
    export = c.get("/account/export")
    assert export.status_code == 200
    assert export.json()["account"]["preferences"] == preferences

    invalid = c.patch("/account/preferences", json={
        "conditions": {"wing": {"windMinKn": 30, "windMaxKn": 12}},
    })
    assert invalid.status_code == 422
    assert c.get("/account/me").json()["preferences"] == preferences

    cleared = c.patch("/account/preferences", json={
        "conditions": {"wing": {"windMaxKn": 28}},
    })
    assert cleared.status_code == 200
    assert cleared.json()["preferences"]["conditions"] == {"wing": {"windMaxKn": 28}}


# --- favourites ------------------------------------------------------------

def test_favorites_add_list_remove(acct, spot_id, db):
    c = acct["client"]
    spot = db.get(Spot, uuid.UUID(spot_id))
    spot.status = "published"
    db.commit()
    assert c.get("/account/favorites").json()["items"] == []

    assert c.put(f"/account/favorites/{spot_id}").status_code == 204
    # idempotent
    assert c.put(f"/account/favorites/{spot_id}").status_code == 204

    items = c.get("/account/favorites").json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == spot_id
    assert items[0]["name"].startswith("Acct Spot")
    assert items[0]["sports"] == ["kitesurf"]
    assert items[0]["region"]

    assert db.scalar(select(Favorite).where(Favorite.spot_id == uuid.UUID(spot_id)))

    assert c.delete(f"/account/favorites/{spot_id}").status_code == 204
    assert c.get("/account/favorites").json()["items"] == []


def test_favorite_unknown_spot_404(acct):
    resp = acct["client"].put(f"/account/favorites/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_favorite_draft_spot_404(acct, spot_id):
    assert acct["client"].put(f"/account/favorites/{spot_id}").status_code == 404


def test_saved_spot_disappears_when_unpublished(acct, spot_id, db):
    spot = db.get(Spot, uuid.UUID(spot_id))
    spot.status = "published"
    db.commit()
    c = acct["client"]
    assert c.put(f"/account/favorites/{spot_id}").status_code == 204
    spot.status = "draft"
    db.commit()
    assert c.get("/account/favorites").json()["items"] == []


def test_favorites_require_auth(anon_client):
    assert anon_client.get("/account/favorites").status_code == 401
    assert anon_client.put(f"/account/favorites/{uuid.uuid4()}").status_code == 401


# --- spot proposals --------------------------------------------------------

def test_submission_create_and_list(acct, db):
    c = acct["client"]
    assert c.get("/account/submissions").json()["items"] == []

    created = c.post("/account/submissions", json={"name": "Fehmarn Wulfener Hals"})
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "pending"
    assert created.json()["name"] == "Fehmarn Wulfener Hals"

    items = c.get("/account/submissions").json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Fehmarn Wulfener Hals"
    assert items[0]["reviewNote"] is None
    assert c.delete(f"/account/submissions/{items[0]['id']}").status_code == 204
    assert c.get("/account/submissions").json()["items"][0]["status"] == "withdrawn"

    # linked to the account by app_user_id
    row = db.scalar(
        select(SpotSubmission).where(SpotSubmission.id == uuid.UUID(items[0]["id"]))
    )
    uid = acct["body"]["id"]
    assert str(row.app_user_id) == uid
    # clean up the submission (no cascade from a region here)
    db.delete(row)
    db.commit()


def test_submission_requires_auth(anon_client):
    assert anon_client.post("/account/submissions", json={"name": "x"}).status_code == 401


def test_proposal_stores_location_and_rejects_existing_spot(acct, spot_id, db):
    c = acct["client"]
    spot = db.get(Spot, uuid.UUID(spot_id))
    region_id = str(spot.region_id)
    spot.status = "published"
    db.commit()

    duplicate = c.post("/account/submissions", json={
        "name": spot.name, "regionId": region_id,
        "lat": 54.41, "lon": 10.22, "sports": ["kitesurf"],
    })
    assert duplicate.status_code == 409

    created = c.post("/account/submissions", json={
        "name": "Neuer Küstenabschnitt", "regionId": region_id,
        "lat": 54.45, "lon": 10.25, "sports": ["wing"],
    })
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["regionId"] == region_id
    assert item["lat"] == 54.45 and item["lon"] == 10.25
    assert item["sports"] == ["wing"]
    row = db.get(SpotSubmission, uuid.UUID(item["id"]))
    assert row.payload["region_id"] == region_id
    db.delete(row)
    db.commit()


def test_signed_in_correction_appears_in_profile_activity(acct, spot_id, db):
    spot = db.get(Spot, uuid.UUID(spot_id))
    spot.status = "published"
    db.commit()
    c = acct["client"]
    response = c.post("/submissions", json={
        "payload": {
            "kind": "spot_edit_suggestion", "spot_id": spot_id,
            "field": "location", "message": "Der Einstieg liegt weiter östlich.",
        },
    })
    assert response.status_code == 201, response.text
    item_id = response.json()["id"]
    activity = c.get("/account/activity")
    assert activity.status_code == 200
    assert any(item["id"] == item_id and item["kind"] == "correction"
               for item in activity.json()["items"])
    assert c.get("/account/submissions").json()["items"] == []
    row = db.get(SpotSubmission, uuid.UUID(item_id))
    db.delete(row)
    db.commit()


def test_password_reset_invalidates_old_sessions(acct):
    c = acct["client"]
    assert c.post("/account/password-reset/request", json={"email": acct["email"]}).status_code == 202
    assert MAIL_OUTBOX[-1][1] == "reset"
    token = MAIL_OUTBOX[-1][2]
    assert c.post("/account/password-reset/confirm", json={
        "token": token, "password": "reset-owner-123",
    }).status_code == 204
    assert c.get("/account/me").status_code == 401
    assert c.post("/account/password-reset/confirm", json={
        "token": token, "password": "again-owner-123",
    }).status_code == 400
