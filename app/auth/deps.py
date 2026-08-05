"""FastAPI auth dependencies: current user, role guards, audit actor.

Replaces the old ``app.admin.deps.require_admin`` (shared key). The regular path
is the httpOnly session cookie; a configured ``ADMIN_KEY`` remains only as an
emergency **break-glass** (actor ``"break-glass"``, role ``admin``).
"""

from __future__ import annotations

import secrets
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Throttle presence writes to at most one per this window, per user, so the
# heartbeat stays cheap on the request hot path.
_HEARTBEAT_THROTTLE = timedelta(seconds=60)

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.security import decode_session_token
from app.config import get_settings
from app.db.session import get_db
from app.models import AdminUser
from app.community.security import client_ip

logger = logging.getLogger(__name__)


@dataclass
class Principal:
    """The authenticated caller for the current request."""

    email: str
    role: str
    user_id: uuid.UUID | None = None
    is_break_glass: bool = False


def _break_glass(request: Request) -> Principal | None:
    settings = get_settings()
    key = settings.admin_key
    if not key:
        return None
    provided = request.headers.get("X-Admin-Key")
    if provided and secrets.compare_digest(provided, key):
        try:
            expires = datetime.fromisoformat(
                (settings.break_glass_expires_at or "").replace("Z", "+00:00")
            )
            if expires.tzinfo is None:
                return None
        except ValueError:
            return None
        remote = client_ip(request)
        if expires <= datetime.now(timezone.utc) or remote not in settings.break_glass_allowed_ips:
            logger.warning("rejected break-glass use from %s on %s", remote, request.url.path)
            return None
        logger.critical("break-glass access from %s on %s", remote, request.url.path)
        return Principal(email="break-glass", role="admin", is_break_glass=True)
    return None


def current_user(request: Request, db: Session = Depends(get_db)) -> Principal:
    bg = _break_glass(request)
    if bg is not None:
        return bg

    token = request.cookies.get(get_settings().auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Nicht angemeldet.")
    try:
        payload = decode_session_token(token)
    except Exception:  # jwt.PyJWTError and any malformed token
        raise HTTPException(status_code=401, detail="Sitzung ungültig oder abgelaufen.")

    sub = payload.get("sub")
    user: AdminUser | None = None
    if sub:
        try:
            user = db.get(AdminUser, uuid.UUID(str(sub)))
        except (ValueError, TypeError):
            user = None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401, detail="Konto nicht gefunden oder deaktiviert."
        )
    if payload.get("ver") != user.session_version:
        raise HTTPException(status_code=401, detail="Sitzung wurde widerrufen.")

    # Presence heartbeat (throttled). Best-effort — never fail the request on it.
    now = datetime.now(timezone.utc)
    last_seen = user.last_seen_at
    if last_seen is None or (now - last_seen) > _HEARTBEAT_THROTTLE:
        try:
            user.last_seen_at = now
            db.commit()
        except Exception:
            db.rollback()

    return Principal(email=user.email, role=user.role, user_id=user.id)


def require_role(*roles: str):
    """Dependency factory: allow only principals whose role is in ``roles``."""

    def _dep(principal: Principal = Depends(current_user)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status_code=403, detail="Keine Berechtigung.")
        return principal

    return _dep


def get_actor(principal: Principal = Depends(current_user)) -> str:
    """The string recorded as ``actor`` in audit logs (the caller's email)."""
    return principal.email
