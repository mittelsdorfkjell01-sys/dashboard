"""Internal immutable phase-4 forecast/observation shadow records."""

from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class WeatherShadowStudy(Base):
    __tablename__ = "weather_shadow_studies"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    version: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    algorithms: Mapped[dict] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WeatherShadowRun(Base):
    __tablename__ = "weather_shadow_runs"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_shadow_studies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    run_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    diagnostics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WeatherShadowForecast(Base):
    __tablename__ = "weather_shadow_forecasts"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_shadow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="RESTRICT"), nullable=False
    )
    shadow_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spot_geo_shadow_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    variant: Mapped[str] = mapped_column(String(48), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(80), nullable=False)
    model_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lead_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    wind_speed_ms: Mapped[float | None] = mapped_column(Float)
    wind_gust_ms: Mapped[float | None] = mapped_column(Float)
    wind_direction_deg: Mapped[float | None] = mapped_column(Float)
    u_ms: Mapped[float | None] = mapped_column(Float)
    v_ms: Mapped[float | None] = mapped_column(Float)
    versions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "spot_id",
            "variant",
            "provider_model",
            "model_run_at",
            "valid_at",
            "lead_hours",
            name="uq_weather_shadow_forecast_issued",
        ),
        Index("ix_weather_shadow_forecast_match", "spot_id", "valid_at", "variant"),
    )


class WeatherShadowStationBinding(Base):
    __tablename__ = "weather_shadow_station_bindings"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_shadow_studies.id", ondelete="CASCADE"),
        nullable=False,
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    station_id: Mapped[str] = mapped_column(String(80), nullable=False)
    binding_version: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_m: Mapped[float | None] = mapped_column(Float)
    measurement_height_m: Mapped[float | None] = mapped_column(Float)
    representativity: Mapped[str] = mapped_column(String(24), nullable=False)
    binding_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "study_id", "spot_id", "provider", "station_id", "binding_version",
            name="uq_weather_shadow_station_binding",
        ),
    )


class WeatherShadowObservation(Base):
    __tablename__ = "weather_shadow_observations"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_shadow_station_bindings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    wind_speed_ms: Mapped[float | None] = mapped_column(Float)
    wind_gust_ms: Mapped[float | None] = mapped_column(Float)
    wind_direction_deg: Mapped[float | None] = mapped_column(Float)
    u_ms: Mapped[float | None] = mapped_column(Float)
    v_ms: Mapped[float | None] = mapped_column(Float)
    quality_status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_qc: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "binding_id", "observed_at", "interval_minutes",
            name="uq_weather_shadow_observation",
        ),
    )


class WeatherShadowMatch(Base):
    __tablename__ = "weather_shadow_matches"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_shadow_forecasts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_shadow_observations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    time_delta_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WeatherShadowMetric(Base):
    __tablename__ = "weather_shadow_metrics"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_shadow_studies.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "study_id", "dimension_hash", name="uq_weather_shadow_metric_dimension"
        ),
    )
