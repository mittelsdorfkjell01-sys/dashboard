"""Reviewed evidence for forecast-dependent product capabilities."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DecisionSupportGate(Base, TimestampMixin):
    __tablename__ = "decision_support_gates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    data_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    sport: Mapped[str] = mapped_column(String(24), nullable=False)
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id", ondelete="CASCADE"))
    horizon_bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    source_model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending_review'"))
    artifact_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_start: Mapped[date] = mapped_column(Date, nullable=False)
    dataset_end: Mapped[date] = mapped_column(Date, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_days: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_ratio: Mapped[float] = mapped_column(nullable=False)
    quality_ratio: Mapped[float] = mapped_column(nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    monitor_fresh_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint("data_kind IN ('wind','wave','tide')", name="ck_decision_gates_kind"),
        CheckConstraint("status IN ('pending_review','accepted','rejected','expired')", name="ck_decision_gates_status"),
        CheckConstraint("dataset_end >= dataset_start", name="ck_decision_gates_dataset_order"),
        CheckConstraint("observation_count >= 0 AND distinct_days >= 0", name="ck_decision_gates_counts"),
        CheckConstraint("coverage_ratio >= 0 AND coverage_ratio <= 1", name="ck_decision_gates_coverage"),
        CheckConstraint("quality_ratio >= 0 AND quality_ratio <= 1", name="ck_decision_gates_quality"),
        CheckConstraint("artifact_sha256 ~ '^[0-9a-f]{64}$'", name="ck_decision_gates_sha256"),
        Index("ix_decision_gates_scope", "data_kind", "sport", "region_id", "horizon_bucket", "status"),
    )
