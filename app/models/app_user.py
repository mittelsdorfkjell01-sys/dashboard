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
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pending_email: Mapped[str | None] = mapped_column(String(255))
    email_token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Consent captured at registration: the accepted terms version and when, plus
    # the self-declared minimum-age (DSGVO Art. 8) confirmation timestamp. Nullable
    # so accounts created before this column, and any future non-registration path,
    # stay valid without a back-filled claim of consent.
    terms_accepted_version: Mapped[str | None] = mapped_column(String(32))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    age_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
