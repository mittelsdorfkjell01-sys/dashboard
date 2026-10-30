"""A user's durable record of having visited a spot."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SpotVisit(Base, TimestampMixin):
    __tablename__ = "spot_visits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    visited_at: Mapped[date] = mapped_column(Date, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(24))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("app_user_id", "spot_id", name="uq_spot_visits_user_spot"),
        CheckConstraint("outcome IS NULL OR outcome IN ('worthwhile','neutral','not_worthwhile')", name="ck_spot_visits_outcome"),
        Index("ix_spot_visits_user_date", "app_user_id", "visited_at"),
    )
