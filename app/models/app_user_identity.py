"""A sign-in identity from an external provider (Google, Apple) linked to an
:class:`~app.models.app_user.AppUser`.

One account can carry several identities (and a password). The provider's
stable subject id — never the email, which can change or be a relay address —
is what identifies the person on later sign-ins.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppUserIdentity(Base):
    __tablename__ = "app_user_identities"
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_app_user_identities_provider_subject"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # The address the provider reported at linking — for support only; the
    # account's own email stays the one that counts.
    email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
