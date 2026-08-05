"""Public visitor accounts — the people who use surfwinddata.com (not the
operator back office).

Deliberately separate from :class:`app.models.admin_user.AdminUser`: admins and
curators run the back office (roles, audit actor, user management), whereas an
:class:`AppUser` is an ordinary visitor who signs up to save favourites and
propose spots. Keeping them in different tables means a public sign-up can never
gain any back-office capability, and the two auth surfaces evolve independently.

Emails are stored lower-cased (shared :func:`normalize_email`) so lookups are
case-insensitive without needing ``citext``.
"""

import uuid

from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.admin_user import normalize_email

__all__ = ["AppUser", "normalize_email"]


class AppUser(Base, TimestampMixin):
    __tablename__ = "app_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    session_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
