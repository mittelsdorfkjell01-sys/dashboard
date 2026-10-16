"""Immutable Phase-5 comparisons between point forecasts and field samples."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
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


class WeatherFieldShadowRun(Base, TimestampMixin):
    __tablename__ = "weather_field_shadow_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_jobs.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_publications.id", ondelete="RESTRICT"),
        nullable=False,
    )
    field_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    profile_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    diagnostics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('processing','succeeded','no_data','failed')",
            name="ck_weather_field_shadow_run_status",
        ),
        Index(
            "ix_weather_field_shadow_run_publication",
            "publication_id",
            "created_at",
        ),
    )


class WeatherFieldShadowSample(Base, TimestampMixin):
    __tablename__ = "weather_field_shadow_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    shadow_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_shadow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("forecast_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lead_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    field_lead_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_bucket: Mapped[str] = mapped_column(String(24), nullable=False)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    legacy_u_ms: Mapped[float | None] = mapped_column(Float)
    legacy_v_ms: Mapped[float | None] = mapped_column(Float)
    legacy_speed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    legacy_direction_deg: Mapped[float | None] = mapped_column(Float)
    legacy_gust_ms: Mapped[float | None] = mapped_column(Float)
    field_u_ms: Mapped[float] = mapped_column(Float, nullable=False)
    field_v_ms: Mapped[float] = mapped_column(Float, nullable=False)
    field_speed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    field_direction_deg: Mapped[float | None] = mapped_column(Float)
    field_gust_ms: Mapped[float | None] = mapped_column(Float)
    speed_delta_ms: Mapped[float] = mapped_column(Float, nullable=False)
    direction_delta_deg: Mapped[float | None] = mapped_column(Float)
    gust_delta_ms: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint(
            "shadow_run_id",
            "spot_id",
            "snapshot_id",
            "valid_at",
            name="uq_weather_field_shadow_sample",
        ),
        CheckConstraint("lead_hours >= 0", name="ck_weather_field_shadow_lead"),
        CheckConstraint(
            "field_lead_hours >= 0", name="ck_weather_field_shadow_field_lead"
        ),
        Index(
            "ix_weather_field_shadow_sample_dimensions",
            "shadow_run_id",
            "horizon_bucket",
        ),
        Index("ix_weather_field_shadow_sample_spot", "spot_id", "valid_at"),
    )


class WeatherFieldShadowMetric(Base, TimestampMixin):
    __tablename__ = "weather_field_shadow_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    shadow_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_shadow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "shadow_run_id",
            "dimension_hash",
            name="uq_weather_field_shadow_metric_dimension",
        ),
        CheckConstraint(
            "sample_count > 0", name="ck_weather_field_shadow_metric_samples"
        ),
        Index("ix_weather_field_shadow_metric_run", "shadow_run_id"),
    )
