"""ID-token verification and the Apple client secret (app.account.oauth),
with keys generated here instead of Google's/Apple's published ones. No DB."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app.account import oauth
from app.config import get_settings


@pytest.fixture
def signing(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    s = get_settings()
    monkeypatch.setattr(s, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(s, "apple_oauth_client_id", "apple-client")
    monkeypatch.setattr(
        oauth, "_jwks",
        lambda url: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())),
    )

    def token(**overrides):
        now = dt.datetime.now(dt.timezone.utc)
        claims = {
            "iss": "https://accounts.google.com", "aud": "google-client", "sub": "123",
            "iat": now, "exp": now + dt.timedelta(minutes=5), "nonce": "n-1",
            "email": "kim@example.com", "email_verified": True,
        } | overrides
        return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm="RS256")

    return token


def test_a_valid_google_token_verifies(signing):
    claims = oauth.verify_id_token(signing(), provider="google", nonce="n-1")
    assert claims["sub"] == "123"


@pytest.mark.parametrize("overrides", [
    {"nonce": "other"},                      # not issued for this sign-in
    {"nonce": None},                         # no nonce at all
    {"aud": "someone-else"},                 # for another client
    {"iss": "https://evil.example"},         # not Google
    {"exp": dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)},  # expired
])
def test_a_token_that_does_not_belong_to_this_sign_in_is_refused(signing, overrides):
    with pytest.raises(oauth.OAuthError):
        oauth.verify_id_token(signing(**overrides), provider="google", nonce="n-1")


def test_a_token_signed_by_another_key_is_refused(signing):
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = dt.datetime.now(dt.timezone.utc)
    forged = jwt.encode(
        {"iss": "https://accounts.google.com", "aud": "google-client", "sub": "1", "iat": now,
         "exp": now + dt.timedelta(minutes=5), "nonce": "n-1"},
        stranger, algorithm="RS256",
    )
    with pytest.raises(oauth.OAuthError):
        oauth.verify_id_token(forged, provider="google", nonce="n-1")


def test_apple_tokens_need_apples_issuer_and_audience(signing):
    token = signing(iss="https://appleid.apple.com", aud="apple-client")
    assert oauth.verify_id_token(token, provider="apple", nonce="n-1")["sub"] == "123"
    with pytest.raises(oauth.OAuthError):
        oauth.verify_id_token(signing(), provider="apple", nonce="n-1")  # a Google token


def test_the_apple_client_secret_is_an_es256_jwt_for_apple(monkeypatch):
    from cryptography.hazmat.primitives import serialization

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode().replace("\n", "\\n")  # as it would sit in an env var
    s = get_settings()
    for k, v in {"apple_oauth_private_key": pem, "apple_oauth_team_id": "TEAM",
                 "apple_oauth_key_id": "KEY1", "apple_oauth_client_id": "de.surfwind.web"}.items():
        monkeypatch.setattr(s, k, v)
    secret = oauth.apple_client_secret()
    assert jwt.get_unverified_header(secret)["kid"] == "KEY1"
    claims = jwt.decode(secret, key.public_key(), algorithms=["ES256"], audience="https://appleid.apple.com")
    assert claims["iss"] == "TEAM" and claims["sub"] == "de.surfwind.web"


def test_apple_sends_email_verified_as_a_string():
    assert oauth._truthy("true") and oauth._truthy(True)
    assert not oauth._truthy("false") and not oauth._truthy(None)
