"""Admin user management (admin-only). Sprint A.

Separate router from ``app.api.admin`` because these routes require the ``admin``
role, whereas the rest of ``/admin/*`` also allows ``curator``.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import Principal, require_role
from app.auth.service import EmailExistsError
from app.db.session import get_db
from app.models import AdminUser
from app.models.admin_user import ROLES

router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_role("admin"))],
)


class AdminUserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    is_active: bool
    last_login_at: str | None = None
    last_seen_at: str | None = None
    created_at: str
    mfa_enabled: bool

    @classmethod
    def from_user(cls, u: AdminUser) -> "AdminUserOut":
        return cls(
            id=str(u.id),
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            last_seen_at=u.last_seen_at.isoformat() if u.last_seen_at else None,
            created_at=u.created_at.isoformat(),
            mfa_enabled=u.totp_enabled_at is not None,
        )


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)
    display_name: str | None = Field(default=None, max_length=120)
    # Two operators, both full admins — no role granularity. New accounts are
    # admins; the UI exposes no role picker.
    role: Literal["admin", "curator"] = "admin"


class AdminUserUpdate(BaseModel):
    role: Literal["admin", "curator"] | None = None
    is_active: bool | None = None
    display_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None


class PasswordUpdate(BaseModel):
    password: str = Field(min_length=12, max_length=1024)


@router.get("", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db)) -> list[AdminUserOut]:
    return [AdminUserOut.from_user(u) for u in service.list_users(db)]


@router.post("", response_model=AdminUserOut, status_code=201)
def create_user(body: AdminUserCreate, db: Session = Depends(get_db)) -> AdminUserOut:
    try:
        user = service.create_user(
            db,
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            role=body.role,
        )
    except EmailExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return AdminUserOut.from_user(user)


@router.patch("/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("admin")),
) -> AdminUserOut:
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(status_code=422, detail=f"Ungültige Rolle: {body.role}")
        # Never demote the last active admin — that would orphan the system.
        if body.role != "admin" and _is_last_active_admin(db, user):
            raise HTTPException(
                status_code=422,
                detail="Der letzte aktive Admin kann nicht herabgestuft werden.",
            )
        user.role = body.role
        user.session_version += 1
    if body.display_name is not None:
        name = body.display_name.strip()
        if name:
            user.display_name = name
    if body.email is not None:
        from app.models.admin_user import normalize_email

        email = normalize_email(body.email)
        if not email:
            raise HTTPException(status_code=422, detail="E-Mail darf nicht leer sein.")
        existing = service.get_by_email(db, email)
        if existing is not None and existing.id != user.id:
            raise HTTPException(status_code=409, detail="E-Mail ist bereits vergeben.")
        user.email = email
    if body.is_active is not None:
        # Guard against locking yourself (or the last admin) out — same two
        # protections as delete_user, enforced server-side (the UI only greys
        # the buttons out).
        if (
            not body.is_active
            and principal.user_id is not None
            and user.id == principal.user_id
        ):
            raise HTTPException(
                status_code=422,
                detail="Du kannst dein eigenes Konto nicht deaktivieren.",
            )
        if (
            user.is_active
            and not body.is_active
            and _is_last_active_admin(db, user)
        ):
            raise HTTPException(
                status_code=422,
                detail="Der letzte aktive Admin kann nicht deaktiviert werden.",
            )
        if user.is_active != body.is_active:
            user.is_active = body.is_active
            user.session_version += 1
    db.flush()
    db.commit()
    return AdminUserOut.from_user(user)


@router.post("/{user_id}/password", status_code=204)
def set_user_password(
    user_id: uuid.UUID, body: PasswordUpdate, db: Session = Depends(get_db)
):
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    try:
        service.set_password(db, user, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return Response(status_code=204)


@router.delete("/{user_id}/mfa", status_code=204)
def reset_user_mfa(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("admin")),
):
    from app.auth import mfa

    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    if principal.user_id == user.id:
        raise HTTPException(
            status_code=422,
            detail="Die eigene 2FA muss mit Passwort und aktuellem Code deaktiviert werden.",
        )
    mfa.disable(user)
    db.commit()
    return Response(status_code=204)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_role("admin")),
):
    user = db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    # Two guards: never delete your own account (lock-out / accident), never
    # delete the last active admin (orphan the system).
    if principal.user_id is not None and user.id == principal.user_id:
        raise HTTPException(
            status_code=422, detail="Du kannst dein eigenes Konto nicht löschen."
        )
    if _is_last_active_admin(db, user):
        raise HTTPException(
            status_code=422, detail="Der letzte aktive Admin kann nicht gelöscht werden."
        )
    db.delete(user)
    db.commit()
    return Response(status_code=204)


def _is_last_active_admin(db: Session, user: AdminUser) -> bool:
    if user.role != "admin":
        return False
    # Lock the complete invariant set. Concurrent demote/deactivate/delete
    # requests then serialize and the second request observes the first commit.
    active_admins = db.scalars(
        select(AdminUser)
        .where(AdminUser.role == "admin", AdminUser.is_active.is_(True))
        .order_by(AdminUser.id)
        .with_for_update()
    ).all()
    others = [u for u in active_admins if u.id != user.id]
    return len(others) == 0
