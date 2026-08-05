"""Authentication endpoints: login / logout / me (Sprint A)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import Principal, current_user
from app.auth.security import create_session_token
from app.auth.security import verify_password
from app.auth import mfa
from app.config import get_settings
from app.db.session import get_db
from app.models import AdminUser
from app.community.ratelimit import RateLimiter, enforce, get_rate_limiter
from app.csrf import clear_csrf_cookie, set_csrf_cookie

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=1024)
    otp: str | None = Field(default=None, pattern=r"^\d{6}$")


class MfaPasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class MfaCodeRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MfaDisableRequest(MfaPasswordRequest, MfaCodeRequest):
    pass


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    mfa_enabled: bool

    @classmethod
    def from_user(cls, user: AdminUser) -> "UserOut":
        return cls(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            mfa_enabled=user.totp_enabled_at is not None,
        )


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.jwt_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


@router.post("/login", response_model=UserOut)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> UserOut:
    enforce(limiter, request, "admin-login", limit=8, window=900)
    user = service.authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="E-Mail oder Passwort ist falsch.")
    if user.totp_enabled_at is not None:
        if not body.otp:
            raise HTTPException(status_code=401, detail="Zwei-Faktor-Code erforderlich.")
        if not mfa.verify_code(user, body.otp):
            raise HTTPException(status_code=401, detail="Anmeldedaten oder Zwei-Faktor-Code sind falsch.")
    service.touch_last_login(db, user)
    db.commit()
    set_session_cookie(
        response, create_session_token(user.id, user.role, user.session_version)
    )
    set_csrf_cookie(response)
    return UserOut.from_user(user)


@router.post("/logout", status_code=204)
def logout():
    response = Response(status_code=204)
    response.delete_cookie(get_settings().auth_cookie_name, path="/")
    clear_csrf_cookie(response)
    return response


@router.get("/me", response_model=UserOut)
def me(
    principal: Principal = Depends(current_user), db: Session = Depends(get_db)
) -> UserOut:
    if principal.user_id is None:  # break-glass: no backing DB row
        return UserOut(
            id="break-glass",
            email=principal.email,
            display_name="Break-Glass",
            role=principal.role,
            mfa_enabled=False,
        )
    user = db.get(AdminUser, principal.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Konto nicht gefunden.")
    return UserOut.from_user(user)


def _db_user(principal: Principal, db: Session) -> AdminUser:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Für Break-Glass ist MFA-Verwaltung gesperrt.")
    user = db.get(AdminUser, principal.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Konto nicht gefunden.")
    return user


@router.post("/mfa/setup")
def setup_mfa(
    body: MfaPasswordRequest,
    principal: Principal = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    user = _db_user(principal, db)
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Passwort ist falsch.")
    secret, uri = mfa.begin_enrollment(user)
    db.commit()
    return {"secret": secret, "provisioning_uri": uri}


@router.post("/mfa/confirm")
def confirm_mfa(
    body: MfaCodeRequest,
    response: Response,
    principal: Principal = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    user = _db_user(principal, db)
    if not user.totp_secret_encrypted or not mfa.enable(user, body.code):
        raise HTTPException(status_code=422, detail="Der Zwei-Faktor-Code ist ungültig.")
    db.commit()
    set_session_cookie(
        response, create_session_token(user.id, user.role, user.session_version)
    )
    return {"mfa_enabled": True}


@router.post("/mfa/disable")
def disable_mfa(
    body: MfaDisableRequest,
    response: Response,
    principal: Principal = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    user = _db_user(principal, db)
    if not verify_password(body.password, user.password_hash) or not mfa.verify_code(
        user, body.code
    ):
        raise HTTPException(status_code=401, detail="Passwort oder Zwei-Faktor-Code ist falsch.")
    mfa.disable(user)
    db.commit()
    set_session_cookie(
        response, create_session_token(user.id, user.role, user.session_version)
    )
    return {"mfa_enabled": False}
