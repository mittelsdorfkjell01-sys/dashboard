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


def _account_from_request(request: Request, db: Session) -> AppUser | None:
    token = request.cookies.get(get_settings().app_auth_cookie_name)
    if not token:
        return None
    try:
        payload = decode_app_session_token(token)
    except Exception:  # jwt.PyJWTError, wrong typ, malformed
        return None

    sub = payload.get("sub")
    user: AppUser | None = None
    if sub:
        try:
            user = db.get(AppUser, uuid.UUID(str(sub)))
        except (ValueError, TypeError):
            user = None
    if user is None or not user.is_active:
        return None
    if payload.get("ver") != user.session_version:
        return None
    return user


def optional_account(request: Request, db: Session = Depends(get_db)) -> AppUser | None:
    return _account_from_request(request, db)


def current_account(request: Request, db: Session = Depends(get_db)) -> AppUser:
    user = _account_from_request(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Nicht angemeldet oder Sitzung abgelaufen.")
    return user
