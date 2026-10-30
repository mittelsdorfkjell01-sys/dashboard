"""Field-level provenance for editorial spot content."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class SpotContentSource(Base, TimestampMixin):
    """A source used to verify one concrete field of a spot record.

    The field path is deliberately explicit (for example
    ``editorial.description`` or ``location``).  This prevents a generic source
    list from making unrelated claims look reviewed.
    """

    __tablename__ = "spot_content_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spots.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_path: Mapped[str] = mapped_column(String(160), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(200))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'unreviewed'")
    )
    note: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_by: Mapped[str | None] = mapped_column(String(120))

    spot: Mapped["Spot"] = relationship(back_populates="content_sources")  # noqa: F821

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unreviewed', 'verified', 'rejected', 'conflict')",
            name="ck_spot_content_sources_verification_status",
        ),
        UniqueConstraint(
            "spot_id", "field_path", "url", name="uq_spot_content_sources_field_url"
        ),
        Index("ix_spot_content_sources_spot_field", "spot_id", "field_path"),
        Index("ix_spot_content_sources_status", "verification_status"),
    )
