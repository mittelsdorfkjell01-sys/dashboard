"""Immutable wave observations, forecast samples and verification evidence."""

from __future__ import annotations

from datetime import date, datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WaveObservationPlatform(Base, TimestampMixin):
    __tablename__ = "wave_observation_platforms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str | None] = mapped_column(String(240))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    region_code: Mapped[str] = mapped_column(String(40), nullable=False)
    location_class: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'unknown'")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    platform_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        UniqueConstraint(
            "provider_key", "external_id", name="uq_wave_platform_provider_external"
        ),
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_wave_platform_latitude",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_wave_platform_longitude",
        ),
        CheckConstraint(
            "location_class IN ('nearshore','shelf','offshore','unknown')",
            name="ck_wave_platform_location_class",
        ),
        Index("ix_wave_platform_active_region", "active", "region_code"),
    )


class WaveObservation(Base):
    __tablename__ = "wave_observations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wave_observation_platforms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    significant_height_m: Mapped[float | None] = mapped_column(Float)
    period_s: Mapped[float | None] = mapped_column(Float)
    period_semantic: Mapped[str | None] = mapped_column(String(48))
    direction_from_deg: Mapped[float | None] = mapped_column(Float)
    direction_semantic: Mapped[str | None] = mapped_column(String(48))
    qc_status: Mapped[str] = mapped_column(String(24), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(120), nullable=False)
    source_file: Mapped[str | None] = mapped_column(Text)
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    raw_values: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "observed_at",
            "source_revision",
            name="uq_wave_observation_identity",
        ),
        CheckConstraint(
            "significant_height_m IS NULL OR "
            "(significant_height_m >= 0 AND significant_height_m <= 40)",
            name="ck_wave_observation_height",
        ),
        CheckConstraint(
            "period_s IS NULL OR (period_s > 0 AND period_s <= 40)",
            name="ck_wave_observation_period",
        ),
        CheckConstraint(
            "direction_from_deg IS NULL OR "
            "(direction_from_deg >= 0 AND direction_from_deg < 360)",
            name="ck_wave_observation_direction",
        ),
        CheckConstraint(
            "qc_status IN ('good','probably_good','interpolated','unknown','bad')",
            name="ck_wave_observation_qc",
        ),
        CheckConstraint(
            "source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_wave_observation_sha256",
        ),
        Index("ix_wave_observation_platform_time", "platform_id", "observed_at"),
        Index("ix_wave_observation_qc_time", "qc_status", "observed_at"),
    )


class WaveForecastSample(Base):
    __tablename__ = "wave_forecast_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wave_observation_platforms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    field_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    model_key: Mapped[str] = mapped_column(String(80), nullable=False)
    model_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lead_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_version: Mapped[str] = mapped_column(String(80), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    significant_height_m: Mapped[float | None] = mapped_column(Float)
    period_s: Mapped[float | None] = mapped_column(Float)
    period_semantic: Mapped[str | None] = mapped_column(String(48))
    direction_from_deg: Mapped[float | None] = mapped_column(Float)
    direction_semantic: Mapped[str | None] = mapped_column(String(48))
    interpolation: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "model_key",
            "model_run_at",
            "valid_at",
            "processing_version",
            name="uq_wave_forecast_sample_identity",
        ),
        CheckConstraint("lead_hours >= 0", name="ck_wave_forecast_sample_lead"),
        CheckConstraint(
            "significant_height_m IS NULL OR "
            "(significant_height_m >= 0 AND significant_height_m <= 40)",
            name="ck_wave_forecast_sample_height",
        ),
        CheckConstraint(
            "period_s IS NULL OR (period_s > 0 AND period_s <= 40)",
            name="ck_wave_forecast_sample_period",
        ),
        CheckConstraint(
            "direction_from_deg IS NULL OR "
            "(direction_from_deg >= 0 AND direction_from_deg < 360)",
            name="ck_wave_forecast_sample_direction",
        ),
        CheckConstraint(
            "evidence_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_wave_forecast_sample_sha256",
        ),
        Index("ix_wave_forecast_sample_model_time", "model_key", "valid_at"),
        Index("ix_wave_forecast_sample_platform_time", "platform_id", "valid_at"),
    )


class WaveVerificationRun(Base, TimestampMixin):
    __tablename__ = "wave_verification_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    dataset_start: Mapped[date] = mapped_column(Date, nullable=False)
    dataset_end: Mapped[date] = mapped_column(Date, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('completed','failed')", name="ck_wave_verification_run_status"
        ),
        CheckConstraint(
            "dataset_end >= dataset_start", name="ck_wave_verification_run_dates"
        ),
        CheckConstraint(
            "artifact_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_wave_verification_run_sha256",
        ),
        Index("ix_wave_verification_run_period", "dataset_start", "dataset_end"),
    )


class WaveVerificationScore(Base):
    __tablename__ = "wave_verification_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    verification_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wave_verification_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_key: Mapped[str] = mapped_column(String(80), nullable=False)
    parameter: Mapped[str] = mapped_column(String(32), nullable=False)
    lead_bucket: Mapped[str] = mapped_column(String(24), nullable=False)
    region_code: Mapped[str] = mapped_column(String(40), nullable=False)
    location_class: Mapped[str] = mapped_column(String(24), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_days: Mapped[int] = mapped_column(Integer, nullable=False)
    bias: Mapped[float] = mapped_column(Float, nullable=False)
    mae: Mapped[float] = mapped_column(Float, nullable=False)
    rmse: Mapped[float] = mapped_column(Float, nullable=False)
    correlation: Mapped[float | None] = mapped_column(Float)
    scatter_index: Mapped[float | None] = mapped_column(Float)
    within_tolerance_ratio: Mapped[float | None] = mapped_column(Float)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "verification_run_id",
            "model_key",
            "parameter",
            "lead_bucket",
            "region_code",
            "location_class",
            name="uq_wave_verification_score_scope",
        ),
        CheckConstraint(
            "parameter IN ('significant_height','period','direction')",
            name="ck_wave_verification_score_parameter",
        ),
        CheckConstraint(
            "sample_count >= 0 AND distinct_days >= 0",
            name="ck_wave_verification_score_counts",
        ),
        CheckConstraint(
            "within_tolerance_ratio IS NULL OR "
            "(within_tolerance_ratio >= 0 AND within_tolerance_ratio <= 1)",
            name="ck_wave_verification_score_tolerance",
        ),
        Index(
            "ix_wave_verification_score_lookup",
            "model_key",
            "parameter",
            "lead_bucket",
            "region_code",
        ),
    )
