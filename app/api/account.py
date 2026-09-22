"""Public account endpoints: sign-up, session, profile, favourites, proposals.

Served by every deployment (mounted unconditionally in app.main) because the
account area lives on the public site. Auth is a session JWT in the app-scoped
httpOnly cookie (see app.account.security) — separate from the admin session.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account import service
from app.account.email import MailUnavailable, send_account_link, send_account_notice
from app.account.deps import current_account
from app.account.security import create_app_session_token
from app.account.service import AuthError, EmailExistsError
from app.config import get_settings
from app.db.session import get_db
from app.models import AppUser, Spot
from app.community.ratelimit import RateLimiter, enforce, get_rate_limiter
from app.csrf import clear_csrf_cookie, set_csrf_cookie

router = APIRouter(prefix="/account", tags=["account"])


# --- schemas ---------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(default="", alias="displayName", max_length=120)

    model_config = {"populate_by_name": True, "extra": "forbid"}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, alias="displayName", max_length=120)

    model_config = {"populate_by_name": True, "extra": "forbid"}


class PasswordChange(BaseModel):
    old_password: str = Field(alias="oldPassword", min_length=1, max_length=1024)
    new_password: str = Field(alias="newPassword", min_length=8, max_length=1024)

    model_config = {"populate_by_name": True, "extra": "forbid"}


class EmailChange(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class EmailConfirmation(BaseModel):
    token: str = Field(min_length=1)
    password: str | None = None


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirmation(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=1024)


class UnitPreferences(BaseModel):
    wind: Literal["kn", "bft", "ms"]
    wave: Literal["m", "ft"]
    temp: Literal["c", "f"]
    distance: Literal["km", "mi"]


SportKey = Literal["surf", "windsurf", "kitesurf", "wing"]


class SportConditions(BaseModel):
    windMinKn: float | None = Field(default=None, ge=0, le=80, allow_inf_nan=False)
    windMaxKn: float | None = Field(default=None, ge=0, le=80, allow_inf_nan=False)
    waveMinM: float | None = Field(default=None, ge=0, le=12, allow_inf_nan=False)
    waveMaxM: float | None = Field(default=None, ge=0, le=12, allow_inf_nan=False)
    waterTempMinC: float | None = Field(default=None, ge=-5, le=40, allow_inf_nan=False)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def valid_ranges(self) -> "SportConditions":
        if self.windMinKn is not None and self.windMaxKn is not None and self.windMinKn > self.windMaxKn:
            raise ValueError("Der minimale Wind darf nicht über dem maximalen Wind liegen.")
        if self.waveMinM is not None and self.waveMaxM is not None and self.waveMinM > self.waveMaxM:
            raise ValueError("Die minimale Wellenhöhe darf nicht über der maximalen Wellenhöhe liegen.")
        return self


class PreferencesPatch(BaseModel):
    units: UnitPreferences | None = None
    sports: list[SportKey] | None = Field(default=None, max_length=4)
    conditions: dict[SportKey, SportConditions] | None = Field(default=None, max_length=4)
    submissionEmails: bool | None = None

    model_config = {"extra": "forbid"}


class SubmissionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    regionId: uuid.UUID | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    sports: list[Literal["surf", "windsurf", "kitesurf", "wing"]] = Field(default_factory=list, max_length=4)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class AccountOut(BaseModel):
    id: str
    email: str
    displayName: str
    createdAt: str
    emailVerified: bool
    pendingEmail: str | None
    preferences: dict
    mailAvailable: bool

    @classmethod
    def of(cls, u: AppUser) -> "AccountOut":
        return cls(
            id=str(u.id),
            email=u.email,
            displayName=u.display_name,
            createdAt=u.created_at.isoformat(),
            emailVerified=u.email_verified_at is not None,
            pendingEmail=u.pending_email,
            preferences=u.preferences or {},
            mailAvailable=bool(get_settings().account_smtp_host and get_settings().account_smtp_from),
        )


class RegisterAccepted(BaseModel):
    accepted: bool = True
    message: str = "Falls noch kein Konto existierte, wurde ein Bestätigungslink versendet."


# --- helpers ---------------------------------------------------------------

def _set_session_cookie(response: Response, user: AppUser) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.app_auth_cookie_name,
        value=create_app_session_token(user.id, user.session_version),
        max_age=settings.app_jwt_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    set_csrf_cookie(response)


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.app_auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    clear_csrf_cookie(response)


# --- auth ------------------------------------------------------------------

@router.post("/register", response_model=RegisterAccepted, status_code=202)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> RegisterAccepted:
    enforce(limiter, request, "account-register", limit=5, window=3600)
    if not get_settings().account_smtp_host or not get_settings().account_smtp_from:
        raise HTTPException(status_code=503, detail="Registrierung ist derzeit nicht verfügbar.")
    try:
        user = service.register(
            db,
            email=body.email,
            password=secrets.token_urlsafe(32),
            display_name=body.display_name,
        )
    except EmailExistsError:
        db.rollback()
        existing = service.get_by_email(db, body.email)
        if existing is not None and existing.email_verified_at is None:
            try:
                send_account_link(existing.email, purpose="verify", token=service.registration_token(existing))
            except MailUnavailable:
                pass
        return RegisterAccepted()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        send_account_link(user.email, purpose="verify", token=service.registration_token(user))
    except MailUnavailable as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    return RegisterAccepted()


@router.post("/email/confirm", response_model=AccountOut)
def confirm_email(body: EmailConfirmation, db: Session = Depends(get_db)) -> AccountOut:
    try:
        user = service.confirm_email(db, body.token, password=body.password)
    except (AuthError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return AccountOut.of(user)


@router.post("/password-reset/request", status_code=202)
def request_password_reset(
    body: ResetRequest, request: Request, db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    enforce(limiter, request, "account-reset", limit=5, window=3600)
    if not get_settings().account_smtp_host or not get_settings().account_smtp_from:
        raise HTTPException(status_code=503, detail="Passwort-Zurücksetzen ist derzeit nicht verfügbar.")
    user = service.get_by_email(db, body.email)
    if user is not None and user.email_verified_at is not None:
        try:
            send_account_link(user.email, purpose="reset", token=service.reset_token(user))
        except MailUnavailable:
            pass  # Never reveal whether this email belongs to an account.
    return {"accepted": True}


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(body: ResetConfirmation, db: Session = Depends(get_db)) -> Response:
    try:
        service.reset_password(db, body.token, body.password)
    except (AuthError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return Response(status_code=204)


@router.post("/login", response_model=AccountOut)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> AccountOut:
    enforce(limiter, request, "account-login", limit=12, window=900)
    try:
        user = service.authenticate(db, body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    _set_session_cookie(response, user)
    return AccountOut.of(user)


@router.post("/logout", status_code=204)
def logout() -> Response:
    response = Response(status_code=204)
    _clear_session_cookie(response)
    return response


@router.get("/me", response_model=AccountOut)
def me(user: AppUser = Depends(current_account)) -> AccountOut:
    return AccountOut.of(user)


@router.patch("/profile", response_model=AccountOut)
def update_profile(
    body: ProfilePatch,
    user: AppUser = Depends(current_account),
    db: Session = Depends(get_db),
) -> AccountOut:
    try:
        service.update_profile(
            db, user, display_name=body.display_name
        )
    except EmailExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return AccountOut.of(user)


@router.post("/email/change", response_model=AccountOut)
def request_email_change(
    body: EmailChange, request: Request, user: AppUser = Depends(current_account),
    db: Session = Depends(get_db), limiter: RateLimiter = Depends(get_rate_limiter),
) -> AccountOut:
    enforce(limiter, request, "account-email-change", limit=5, window=3600)
    old_email = user.email
    try:
        token = service.start_email_change(db, user, body.email, body.password)
        send_account_link(user.pending_email, purpose="change_email", token=token)
    except (AuthError, EmailExistsError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MailUnavailable as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    try:
        send_account_notice(
            old_email, subject="Änderung deiner E-Mail-Adresse angefordert",
            body="Für dein Konto wurde eine neue E-Mail-Adresse angefordert. "
                 "Falls du das nicht warst, ändere bitte sofort dein Passwort.",
        )
    except MailUnavailable:
        pass
    return AccountOut.of(user)


@router.patch("/preferences", response_model=AccountOut)
def update_preferences(
    body: PreferencesPatch, user: AppUser = Depends(current_account), db: Session = Depends(get_db)
) -> AccountOut:
    patch = body.model_dump(exclude_none=True)
    if patch.get("submissionEmails") and not (
        get_settings().account_smtp_host and get_settings().account_smtp_from
    ):
        raise HTTPException(status_code=503, detail="E-Mail-Benachrichtigungen sind derzeit nicht verfügbar.")
    if "sports" in patch:
        patch["sports"] = list(dict.fromkeys(patch["sports"]))
    service.update_preferences(db, user, patch)
    db.commit()
    return AccountOut.of(user)


@router.get("/activity")
def list_activity(
    user: AppUser = Depends(current_account), db: Session = Depends(get_db)
) -> dict:
    return service.list_my_activity(db, user)


@router.post("/password", status_code=204)
def change_password(
    body: PasswordChange,
    request: Request,
    user: AppUser = Depends(current_account),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> Response:
    enforce(limiter, request, "account-password-change", limit=5, window=3600)
    try:
        service.change_password(db, user, body.old_password, body.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    response = Response(status_code=204)
    _set_session_cookie(response, user)
    return response


@router.get("/export")
def export_account(
    user: AppUser = Depends(current_account), db: Session = Depends(get_db)
) -> JSONResponse:
    response = JSONResponse(service.export_account_data(db, user))
    response.headers["Content-Disposition"] = 'attachment; filename="surfwinddata-export.json"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.delete("", status_code=204)
def delete_account(
    body: DeleteAccountRequest,
    user: AppUser = Depends(current_account),
    db: Session = Depends(get_db),
) -> Response:
    try:
        service.delete_account(db, user, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    response = Response(status_code=204)
    _clear_session_cookie(response)
    return response


# --- favourites ------------------------------------------------------------

@router.get("/favorites")
def list_favorites(
    user: AppUser = Depends(current_account), db: Session = Depends(get_db)
) -> dict:
    return {"items": service.list_favorites(db, user)}


@router.put("/favorites/{spot_id}", status_code=204)
def add_favorite(
    spot_id: uuid.UUID,
    user: AppUser = Depends(current_account),
    db: Session = Depends(get_db),
) -> Response:
    try:
        service.add_favorite(db, user, spot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return Response(status_code=204)


@router.delete("/favorites/{spot_id}", status_code=204)
def remove_favorite(
    spot_id: uuid.UUID,
    user: AppUser = Depends(current_account),
    db: Session = Depends(get_db),
) -> Response:
    service.remove_favorite(db, user, spot_id)
    db.commit()
    return Response(status_code=204)


# --- spot proposals --------------------------------------------------------

@router.get("/submissions")
def list_submissions(
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(current_account), db: Session = Depends(get_db)
) -> dict:
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail="Ungültige Seitengröße.")
    rows = service.list_my_submissions(db, user, limit=limit + 1, offset=offset)
    return {"items": rows[:limit], "hasMore": len(rows) > limit}


@router.get("/submissions/similar")
def similar_spots(
    q: str = "", user: AppUser = Depends(current_account), db: Session = Depends(get_db)
) -> dict:
    term = " ".join(q.split())[:80]
    if len(term) < 3:
        return {"items": []}
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = db.scalars(select(Spot).where(
        Spot.status == "published", Spot.name.ilike(f"%{escaped}%", escape="\\")
    ).order_by(Spot.name).limit(6)).all()
    return {"items": [{"id": str(spot.id), "name": spot.name} for spot in rows]}


@router.post("/submissions", status_code=201)
def create_submission(
    body: SubmissionRequest,
    request: Request,
    user: AppUser = Depends(current_account),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    enforce(limiter, request, "account-submission", limit=5, window=86400)
    try:
        result = service.create_named_submission(
            db, user, body.name, region_id=body.regionId, lat=body.lat, lon=body.lon,
            sports=body.sports,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return result


@router.delete("/submissions/{submission_id}", status_code=204)
def withdraw_submission(
    submission_id: uuid.UUID, user: AppUser = Depends(current_account), db: Session = Depends(get_db)
) -> Response:
    try:
        service.withdraw_submission(db, user, submission_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return Response(status_code=204)
