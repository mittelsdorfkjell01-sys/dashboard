"""Persistent observations and forecast verification used for wind calibration."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WeatherStation(Base, TimestampMixin):
    __tablename__ = "weather_stations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_station_id: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str | None] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float)
    elevation_difference_m: Mapped[float | None] = mapped_column(Float)
    setting_class: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unknown")
    exposure_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    representativeness_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unreviewed")
    recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    decision_reason: Mapped[str | None] = mapped_column(Text)
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("spot_id", "provider", "provider_station_id", name="uq_weather_station_spot_provider"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_weather_station_lat"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_weather_station_lon"),
    )


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    wind_speed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    wind_gust_ms: Mapped[float | None] = mapped_column(Float)
    wind_direction_deg: Mapped[float | None] = mapped_column(Float)
    quality: Mapped[int | None] = mapped_column(Integer)
    provider_quality: Mapped[str | None] = mapped_column(String(80))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="accepted")
    data_issues: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("station_id", "observed_at", name="uq_weather_observation_time"),
        CheckConstraint("wind_speed_ms >= 0 AND wind_speed_ms <= 100", name="ck_weather_observation_speed"),
        CheckConstraint("wind_direction_deg IS NULL OR (wind_direction_deg >= 0 AND wind_direction_deg < 360)", name="ck_weather_observation_dir"),
    )


class WeatherForecastSample(Base):
    __tablename__ = "weather_forecast_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(80), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lead_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    wind_speed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    wind_gust_ms: Mapped[float | None] = mapped_column(Float)
    wind_direction_deg: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("spot_id", "model_id", "issued_at", "valid_at", name="uq_weather_forecast_sample"),
        CheckConstraint("lead_hours >= 0 AND lead_hours <= 300", name="ck_weather_sample_lead"),
    )


class WeatherModelCalibration(Base, TimestampMixin):
    __tablename__ = "weather_model_calibrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(80), nullable=False)
    lead_bucket: Mapped[str] = mapped_column(String(12), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bias_ms: Mapped[float] = mapped_column(Float, nullable=False)
    mae_ms: Mapped[float] = mapped_column(Float, nullable=False)
    weight_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    decision_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="legacy_active")
    decision_version: Mapped[str | None] = mapped_column(String(32))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decision_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("spot_id", "model_id", "lead_bucket", name="uq_weather_calibration"),
        CheckConstraint("sample_count >= 0", name="ck_weather_calibration_samples"),
        CheckConstraint("weight_multiplier >= 0.5 AND weight_multiplier <= 2.0", name="ck_weather_calibration_weight"),
    )
