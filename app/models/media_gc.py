"""Persistent garbage-collection queue for hosted media objects."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MediaGarbageCandidate(Base, TimestampMixin):
    __tablename__ = "media_garbage_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    # SHA-256 keeps uniqueness indexable even when a provider URL is long.
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Variants point back to the canonical URL whose DB references decide
    # whether the individual object may be deleted.
    reference_url: Mapped[str] = mapped_column(Text, nullable=False)
    delete_set: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_media_gc_due", "not_before", "created_at"),
    )


class MediaGcState(Base, TimestampMixin):
    """Cursor for bounded, resumable provider-side orphan scans."""

    __tablename__ = "media_gc_state"

    backend: Mapped[str] = mapped_column(String(20), primary_key=True)
    cursor: Mapped[str | None] = mapped_column(Text)
