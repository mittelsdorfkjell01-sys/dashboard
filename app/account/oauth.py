"""Sign in with Google and Apple (OpenID Connect, authorization-code flow).

What this module does, and only this: build the provider's authorization URL,
exchange the returned code for tokens, and verify the provider's ID token
(signature against the provider's published keys, issuer, audience, expiry and
our nonce). It returns the verified claims; deciding which account they belong
to is :func:`app.account.service.sign_in_with_identity`.

Both providers get PKCE and a nonce. The browser binding (state + nonce +
verifier in an httpOnly cookie) lives in the API layer.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.config import get_settings

Provider = Literal["google", "apple"]

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

APPLE_AUTH = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN = "https://appleid.apple.com/auth/token"
APPLE_JWKS = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"


class OAuthError(Exception):
    """The provider refused, or its answer did not verify."""


@dataclass(frozen=True)
class Identity:
    provider: Provider
    subject: str
    email: str | None
    email_verified: bool
    name: str | None


def enabled_providers() -> dict[str, bool]:
    s = get_settings()
    return {
        "google": bool(s.google_oauth_client_id and s.google_oauth_client_secret),
        "apple": bool(
            s.apple_oauth_client_id and s.apple_oauth_team_id
            and s.apple_oauth_key_id and s.apple_oauth_private_key
        ),
    }


def callback_url(provider: Provider) -> str:
    return f"{get_settings().account_api_public_origin.rstrip('/')}/account/oauth/{provider}/callback"


def new_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorization_url(provider: Provider, *, state: str, nonce: str, challenge: str) -> str:
    s = get_settings()
    if provider == "google":
        params = {
            "client_id": s.google_oauth_client_id,
            "redirect_uri": callback_url("google"),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH}?{urlencode(params)}"
    params = {
        "client_id": s.apple_oauth_client_id,
        "redirect_uri": callback_url("apple"),
        "response_type": "code",
        # Asking for name/email makes Apple answer with a form POST.
        "response_mode": "form_post",
        "scope": "name email",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{APPLE_AUTH}?{urlencode(params)}"


def apple_client_secret() -> str:
    """Apple's client secret is a short-lived JWT signed with our key (ES256)."""
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    key = (s.apple_oauth_private_key or "").replace("\\n", "\n")
    return jwt.encode(
        {
            "iss": s.apple_oauth_team_id,
            "iat": now,
            "exp": now + dt.timedelta(minutes=5),
            "aud": APPLE_ISSUER,
            "sub": s.apple_oauth_client_id,
        },
        key,
        algorithm="ES256",
        headers={"kid": s.apple_oauth_key_id},
    )


@lru_cache(maxsize=2)
def _jwks(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def verify_id_token(token: str, *, provider: Provider, nonce: str) -> dict:
    s = get_settings()
    if provider == "google":
        jwks_url, issuers, audience, algorithms = GOOGLE_JWKS, GOOGLE_ISSUERS, s.google_oauth_client_id, ["RS256"]
    else:
        jwks_url, issuers, audience, algorithms = APPLE_JWKS, (APPLE_ISSUER,), s.apple_oauth_client_id, ["RS256"]
    try:
        signing_key = _jwks(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=algorithms,
            audience=audience,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise OAuthError("Die Anmeldung konnte nicht bestätigt werden.") from exc
    if claims.get("iss") not in issuers:
        raise OAuthError("Die Anmeldung konnte nicht bestätigt werden.")
    # Apple and Google both echo our nonce; a missing or foreign one means the
    # token was not issued for this sign-in.
    if not nonce or not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OAuthError("Die Anmeldung konnte nicht bestätigt werden.")
    return claims


def _truthy(value: object) -> bool:
    # Apple sends email_verified as the string "true".
    return value is True or str(value).lower() == "true"


def exchange_code(provider: Provider, *, code: str, verifier: str, nonce: str, apple_name: str | None = None) -> Identity:
    s = get_settings()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_url(provider),
        "code_verifier": verifier,
    }
    if provider == "google":
        data |= {"client_id": s.google_oauth_client_id, "client_secret": s.google_oauth_client_secret}
        url = GOOGLE_TOKEN
    else:
        data |= {"client_id": s.apple_oauth_client_id, "client_secret": apple_client_secret()}
        url = APPLE_TOKEN
    try:
        response = httpx.post(url, data=data, timeout=10.0)
    except httpx.HTTPError as exc:
        raise OAuthError("Der Anmeldedienst ist gerade nicht erreichbar.") from exc
    if response.status_code != 200:
        raise OAuthError("Die Anmeldung wurde vom Anbieter abgelehnt.")
    id_token = response.json().get("id_token")
    if not id_token:
        raise OAuthError("Die Anmeldung konnte nicht bestätigt werden.")
    claims = verify_id_token(id_token, provider=provider, nonce=nonce)
    name = claims.get("name") if provider == "google" else apple_name
    return Identity(
        provider=provider,
        subject=str(claims["sub"]),
        email=(claims.get("email") or None),
        email_verified=_truthy(claims.get("email_verified")),
        name=(name or None),
    )
