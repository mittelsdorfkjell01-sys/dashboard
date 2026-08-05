"""Session tokens for public visitor accounts.

Password hashing is shared with the admin side (:mod:`app.auth.security` — one
bcrypt implementation for the whole app). The session token is deliberately
*not* shared: it carries a ``"typ": "app"`` claim and is validated for it, so an
admin session JWT can never authenticate against the account API, nor the
reverse. Both are signed with the same secret; the claim — not the signature —
is what separates the two audiences.
"""

from __future__ import annotations

import datetime as dt
import uuid

import jwt

from app.auth.security import hash_password, verify_password  # re-exported
from app.config import get_settings

__all__ = [
    "hash_password",
    "verify_password",
    "create_app_session_token",
    "decode_app_session_token",
]

_ALG = "HS256"
_TYP = "app"


def create_app_session_token(user_id: uuid.UUID, session_version: int = 0) -> str:
    settings = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "typ": _TYP,
        "ver": session_version,
        "iat": now,
        "exp": now + dt.timedelta(hours=settings.app_jwt_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALG)


def decode_app_session_token(token: str) -> dict:
    """Decode + verify signature/expiry **and** the app audience.

    Raises ``jwt.PyJWTError`` (specifically ``InvalidTokenError``) when the token
    is not an app-scoped session — e.g. an admin JWT presented to the account
    API.
    """
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALG])
    if payload.get("typ") != _TYP:
        raise jwt.InvalidTokenError("not an app session token")
    return payload
