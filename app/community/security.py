"""Client-IP hashing and honeypot spam check for public write endpoints.

We never store a raw IP: ``ip_hash`` is a salted SHA-256 (salt = the app's
``jwt_secret``) used only for rate-limiting and light abuse correlation. The
honeypot is a hidden form field bots tend to fill; a non-empty value is spam.
"""

from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request

from app.config import get_settings


def client_ip(request: Request) -> str:
    """Client IP resolved only through an explicitly trusted proxy depth."""
    fwd = request.headers.get("x-forwarded-for")
    trusted_hops = max(0, get_settings().trusted_proxy_hops)
    if fwd and trusted_hops:
        chain = [part.strip() for part in fwd.split(",") if part.strip()]
        if chain:
            index = max(0, len(chain) - trusted_hops)
            return chain[index]
    return request.client.host if request.client else ""


def ip_hash(request: Request) -> str:
    salt = get_settings().jwt_secret
    digest = hashlib.sha256(f"{salt}:{client_ip(request)}".encode("utf-8")).hexdigest()
    return digest[:64]


def check_honeypot(value: str | None) -> None:
    """A filled honeypot field ⇒ almost certainly a bot. Reject as a bad request
    (deliberately generic — don't tell the bot which field gave it away)."""
    if value and value.strip():
        raise HTTPException(status_code=400, detail="Ungültige Anfrage.")
