"""FastAPI dependency: the current visitor account from the session cookie.

Distinct from :mod:`app.auth.deps` (admins). Reads the app-scoped cookie, decodes
the app-typed token, and loads the :class:`AppUser`. There is no break-glass and
no role — a visitor is just a visitor.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.account.security import decode_app_session_token
from app.config import get_settings
from app.db.session import get_db
from app.models import AppUser


def current_account(
    request: Request, db: Session = Depends(get_db)
) -> AppUser:
    token = request.cookies.get(get_settings().app_auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Nicht angemeldet.")
    try:
        payload = decode_app_session_token(token)
    except Exception:  # jwt.PyJWTError, wrong typ, malformed
        raise HTTPException(status_code=401, detail="Sitzung ungültig oder abgelaufen.")

    sub = payload.get("sub")
    user: AppUser | None = None
    if sub:
        try:
            user = db.get(AppUser, uuid.UUID(str(sub)))
        except (ValueError, TypeError):
            user = None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401, detail="Konto nicht gefunden oder deaktiviert."
        )
    if payload.get("ver") != user.session_version:
        raise HTTPException(status_code=401, detail="Sitzung wurde widerrufen.")
    return user
