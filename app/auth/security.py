"""Password hashing (bcrypt) and short-lived session JWTs.

bcrypt is used directly (not via passlib, which is unmaintained and breaks
against bcrypt 5.x). bcrypt only considers the first 72 bytes of a secret, so we
truncate on the byte string for both hash and verify to stay consistent.
"""

from __future__ import annotations

import datetime as dt
import uuid

import bcrypt
import jwt

from app.config import get_settings

_ALG = "HS256"
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()
    ).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
            password_hash.encode("ascii"),
        )
    except (ValueError, TypeError):
        return False


def create_session_token(user_id: uuid.UUID, role: str, session_version: int = 0) -> str:
    settings = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "typ": "admin",
        "ver": session_version,
        "iat": now,
        "exp": now + dt.timedelta(hours=settings.jwt_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALG)


def decode_session_token(token: str) -> dict:
    """Decode + verify signature/expiry. Raises ``jwt.PyJWTError`` on failure."""
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALG])
    if payload.get("typ") != "admin":
        raise jwt.InvalidTokenError("not an admin session token")
    return payload
