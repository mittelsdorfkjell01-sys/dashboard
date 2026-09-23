"""Internal audit rows for computed personalized recommendations."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecommendationLog(Base):
    __tablename__ = "recommendation_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE")
    )
    user_ref: Mapped[str] = mapped_column(String(96), nullable=False)
    audience_segment: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'anonymous'")
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False
    )
    surface: Mapped[str] = mapped_column(String(24), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    components: Mapped[dict] = mapped_column(JSONB, nullable=False)
    params_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "user_ref", "spot_id", "surface", "window_start",
            name="uq_recommendation_log_window",
        ),
        Index("ix_recommendation_log_user_created", "app_user_id", "created_at"),
        Index("ix_recommendation_log_surface_window", "surface", "window_start"),
    )


class ScoringCalibrationProposal(Base):
    __tablename__ = "scoring_calibration_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    sport: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    base_params_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(160))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_params_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_scoring_calibration_status_created", "status", "created_at"),
    )
