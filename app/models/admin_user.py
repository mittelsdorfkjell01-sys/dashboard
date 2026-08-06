"""Admin/curator accounts for the operator back office (Sprint A).

Replaces the shared ``X-Admin-Key``. A logged-in :class:`AdminUser` is the
``actor`` recorded in every audit entry. Two roles:

* ``admin``   — full access, including user management.
* ``curator`` — curate/moderate content, but **not** user management.

Emails are stored lower-cased (see :func:`normalize_email`) so lookups are
effectively case-insensitive without needing the ``citext`` extension.
"""

import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

ROLES = ("admin", "curator")


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'curator'")
    )  # admin | curator
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    session_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_login_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    # Presence heartbeat: refreshed (throttled) on every authenticated request
    # so the user table can show a real online/offline indicator.
    last_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'curator')", name="ck_admin_users_role"),
    )
