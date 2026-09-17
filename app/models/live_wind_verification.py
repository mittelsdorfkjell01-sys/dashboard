"""Immutable scientific evidence for manually activating LiveWind candidates."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeatherLiveWindHoldoutCase(Base):
    """Insert-only snapshot of one spatial/temporal shadow holdout."""

    __tablename__ = "weather_live_wind_holdout_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    candidate_version: Mapped[str] = mapped_column(String(80), nullable=False)
    target_station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weather_stations.id"), nullable=False
    )
    target_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weather_observations.id"), nullable=False
    )
    shadow_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weather_live_wind_jobs.id"), nullable=False
    )
    analysis_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dataset_bundle_hash: Mapped[str | None] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(24), nullable=False)
    exclusion_reasons: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "candidate_version", "target_observation_id", "analysis_cutoff_at",
            "input_hash", name="uq_live_wind_holdout_case_version",
        ),
        CheckConstraint(
            "eligibility_status IN ('eligible','not_activation_eligible')",
            name="ck_live_wind_holdout_eligibility",
        ),
        Index("ix_live_wind_holdout_candidate_time", "candidate_version", "analysis_cutoff_at"),
        Index("ix_live_wind_holdout_eligibility", "candidate_version", "eligibility_status"),
    )


class WeatherLiveWindVerificationEvidence(Base):
    __tablename__ = "weather_live_wind_verification_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    candidate_version: Mapped[str] = mapped_column(String(80), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    training_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    matched_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_stations: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    stratified_metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    policy: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "candidate_version",
            "context_hash",
            "training_window_end",
            name="uq_live_wind_verification_context",
        ),
        CheckConstraint(
            "status IN ('collecting','rejected','passed')",
            name="ck_live_wind_verification_status",
        ),
        CheckConstraint(
            "matched_samples >= 0 AND distinct_stations >= 0 AND distinct_days >= 0",
            name="ck_live_wind_verification_counts",
        ),
        CheckConstraint(
            "training_window_end < window_start AND window_start <= window_end",
            name="ck_live_wind_verification_windows",
        ),
        Index(
            "ix_live_wind_verification_candidate",
            "candidate_version",
            "status",
            "computed_at",
        ),
    )
