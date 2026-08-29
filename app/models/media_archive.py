"""Compressed long-term evidence for retired image moderation rows."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, LargeBinary, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SpotImageArchive(Base):
    __tablename__ = "spot_image_archives"

    # Preserve the original image id so append-only moderation audit rows can
    # still be joined to the archived evidence without a translation table.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    entity_type: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    compressed_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_spot_image_archive_entity", "entity_type", "entity_id"),
        Index("ix_spot_image_archive_archived_at", "archived_at"),
    )
