"""AdminUser CRUD + first-run bootstrap.

Service functions flush but do not commit (the caller/endpoint owns the
transaction), except :func:`bootstrap_admin`, which runs outside a request and
commits its own unit of work.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.config import get_settings
from app.models import AdminUser
from app.models.admin_user import ROLES, normalize_email
from app.password_policy import ensure_password_safe


class EmailExistsError(ValueError):
    """Signals a duplicate email on user creation (→ 409 at the API)."""


def get_by_email(db: Session, email: str) -> AdminUser | None:
    return db.execute(
        select(AdminUser).where(AdminUser.email == normalize_email(email))
    ).scalar_one_or_none()


def count_users(db: Session) -> int:
    return int(db.execute(select(func.count()).select_from(AdminUser)).scalar_one())


def list_users(db: Session) -> list[AdminUser]:
    return list(
        db.execute(select(AdminUser).order_by(AdminUser.created_at)).scalars().all()
    )


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str | None = None,
    role: str = "curator",
    is_active: bool = True,
) -> AdminUser:
    if role not in ROLES:
        raise ValueError(f"Ungültige Rolle: {role!r} (erlaubt: {', '.join(ROLES)}).")
    ensure_password_safe(password)
    email = normalize_email(email)
    if not email:
        raise ValueError("E-Mail darf nicht leer sein.")
    if get_by_email(db, email) is not None:
        raise EmailExistsError(f"E-Mail bereits vergeben: {email}")
    user = AdminUser(
        email=email,
        password_hash=hash_password(password),
        display_name=(display_name or "").strip() or email,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> AdminUser | None:
    user = get_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def set_password(db: Session, user: AdminUser, new_password: str) -> None:
    ensure_password_safe(new_password)
    user.password_hash = hash_password(new_password)
    user.session_version += 1
    db.flush()


def touch_last_login(db: Session, user: AdminUser) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()


def bootstrap_admin(db: Session) -> AdminUser | None:
    """Create the first admin from ``ADMIN_BOOTSTRAP_*`` settings.

    No-op (returns ``None``) when the settings are unset or any AdminUser already
    exists — so it is safe to call on every start (idempotent). Commits its own
    transaction.
    """
    settings = get_settings()
    email = settings.admin_bootstrap_email
    password = settings.admin_bootstrap_password
    if not (email and password):
        return None
    if count_users(db) > 0:
        return None
    user = create_user(
        db,
        email=email,
        password=password,
        display_name="Administrator",
        role="admin",
    )
    db.commit()
    return user
