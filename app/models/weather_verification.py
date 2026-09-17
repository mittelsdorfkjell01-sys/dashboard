"""Persistent observations and forecast verification used for wind calibration."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WeatherStation(Base, TimestampMixin):
    __tablename__ = "weather_stations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_station_id: Mapped[str] = mapped_column(String(80), nullable=False)
    wigos_id: Mapped[str | None] = mapped_column(String(80))
    icao_id: Mapped[str | None] = mapped_column(String(16))
    name: Mapped[str | None] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float)
    measurement_height_m: Mapped[float | None] = mapped_column(Float)
    license: Mapped[str | None] = mapped_column(String(160))
    provenance: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
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
        CheckConstraint(
            "measurement_height_m IS NULL OR "
            "(measurement_height_m >= 0 AND measurement_height_m <= 300)",
            name="ck_weather_station_measurement_height",
        ),
    )


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    wind_speed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    wind_gust_ms: Mapped[float | None] = mapped_column(Float)
    gust_period_seconds: Mapped[int | None] = mapped_column(Integer)
    wind_direction_deg: Mapped[float | None] = mapped_column(Float)
    wind_u_ms: Mapped[float | None] = mapped_column(Float)
    wind_v_ms: Mapped[float | None] = mapped_column(Float)
    quality: Mapped[int | None] = mapped_column(Integer)
    provider_quality: Mapped[str | None] = mapped_column(String(80))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="accepted")
    data_issues: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("station_id", "observed_at", name="uq_weather_observation_time"),
        CheckConstraint("wind_speed_ms >= 0 AND wind_speed_ms <= 100", name="ck_weather_observation_speed"),
        CheckConstraint("wind_direction_deg IS NULL OR (wind_direction_deg >= 0 AND wind_direction_deg < 360)", name="ck_weather_observation_dir"),
        CheckConstraint(
            "gust_period_seconds IS NULL OR "
            "(gust_period_seconds >= 1 AND gust_period_seconds <= 86400)",
            name="ck_weather_observation_gust_period",
        ),
    )


class WeatherObservationQuarantine(Base):
    """Immutable audit trail for public observations unsafe to accept."""

    __tablename__ = "weather_observation_quarantine"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    station_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_stations.id", ondelete="SET NULL"),
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_station_id: Mapped[str] = mapped_column(Text, nullable=False)
    station_identity: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    import_status: Mapped[str] = mapped_column(String(24), nullable=False)
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    data_issues: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    raw_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    normalized_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "import_status IN ('raw','rejected','quarantined')",
            name="ck_weather_observation_quarantine_status",
        ),
        Index(
            "ix_weather_observation_quarantine_lookup",
            "provider",
            "provider_station_id",
            "observed_at",
        ),
        UniqueConstraint(
            "fingerprint", name="uq_weather_observation_quarantine_fingerprint"
        ),
    )


class WeatherObservationImportState(Base):
    """Latest sanitized import outcome per configured station."""

    __tablename__ = "weather_observation_import_states"

    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_stations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_class: Mapped[str | None] = mapped_column(String(120))
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_counts: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('success','error')",
            name="ck_weather_observation_import_state_status",
        ),
        CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_weather_observation_import_state_failures",
        ),
        Index(
            "ix_weather_observation_import_state_provider_status",
            "provider",
            "status",
        ),
    )


class WeatherStationPhysicsProfile(Base, TimestampMixin):
    """Versioned, reviewed local-physics input for a measurement station."""

    __tablename__ = "weather_station_physics_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_stations.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="draft"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    quality_tier: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="coordinates"
    )
    coastal_normal_deg: Mapped[float | None] = mapped_column(Float)
    physics_version: Mapped[str] = mapped_column(String(80), nullable=False)
    profile: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "station_id", "version", name="uq_weather_station_physics_profile_version"
        ),
        CheckConstraint(
            "status IN ('draft','reviewed','retired')",
            name="ck_weather_station_physics_profile_status",
        ),
        CheckConstraint(
            "version >= 1", name="ck_weather_station_physics_profile_version"
        ),
        CheckConstraint(
            "coastal_normal_deg IS NULL OR "
            "(coastal_normal_deg >= 0 AND coastal_normal_deg < 360)",
            name="ck_weather_station_physics_profile_coastal_normal",
        ),
        CheckConstraint(
            "NOT active OR (status = 'reviewed' AND reviewed_at IS NOT NULL)",
            name="ck_weather_station_physics_profile_active_reviewed",
        ),
        Index(
            "uq_weather_station_physics_profile_active",
            "station_id",
            unique=True,
            postgresql_where=text("active"),
        ),
    )


class WeatherStationModelResidual(Base):
    """Immutable evidence for measurement minus raw model at one station/time."""

    __tablename__ = "weather_station_model_residuals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_stations.id", ondelete="CASCADE"),
        nullable=False,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_observations.id", ondelete="CASCADE"),
        nullable=False,
    )
    station_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_station_physics_profiles.id", ondelete="SET NULL"),
    )
    analysis_id: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_bundle_hash: Mapped[str | None] = mapped_column(String(64))
    dataset_bundle_hash: Mapped[str | None] = mapped_column(String(64))
    dataset_manifest: Mapped[dict | None] = mapped_column(JSONB)
    sample_hash: Mapped[str | None] = mapped_column(String(64))
    sample_manifest: Mapped[dict | None] = mapped_column(JSONB)
    activation_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_runs: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    model_members: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    raw_model_vector: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    expected_station_vector: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    measurement_vector: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    residual_vector: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    gust_evidence: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    station_profile_version: Mapped[int | None] = mapped_column(Integer)
    physics_version: Mapped[str] = mapped_column(String(80), nullable=False)
    physics_applied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    model_member_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    representativeness_uncertainty: Mapped[str] = mapped_column(
        String(48), nullable=False
    )
    qc_status: Mapped[str] = mapped_column(String(16), nullable=False)
    qc_reasons: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    configuration: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "analysis_id",
            "calculation_version",
            name="uq_weather_station_model_residual_evidence",
        ),
        CheckConstraint(
            "qc_status IN ('accepted','degraded','rejected','unavailable')",
            name="ck_weather_station_model_residual_qc",
        ),
        CheckConstraint(
            "model_member_count >= 0",
            name="ck_weather_station_model_residual_member_count",
        ),
        Index(
            "ix_weather_station_model_residual_station_time",
            "station_id",
            "observed_at",
        ),
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


class ForecastVerificationScore(Base):
    """WP1 harness output: raw-forecast error versus gated station measurements.

    Rows are grouped by spot, model (or the ``consensus`` aggregate), a lead-time
    bucket and a 30-degree direction sector. Gated runs keep the serving baseline
    under ``raw`` for schema compatibility and encode the exact candidate version
    as ``candidate:<base36>``. Their shared context hash binds candidate
    contents, active baseline, calibration, blend and physics versions. Station
    wind never feeds the forecast; it only produces these scores.
    """

    __tablename__ = "forecast_verification_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(80), nullable=False)
    variant: Mapped[str] = mapped_column(String(16), nullable=False, server_default="raw")
    lead_bucket: Mapped[str] = mapped_column(String(12), nullable=False)
    direction_sector: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bias_ms: Mapped[float] = mapped_column(Float, nullable=False)
    mae_ms: Mapped[float] = mapped_column(Float, nullable=False)
    rmse_ms: Mapped[float] = mapped_column(Float, nullable=False)
    direction_mae_deg: Mapped[float | None] = mapped_column(Float)
    gust_mae_ms: Mapped[float | None] = mapped_column(Float)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gate_context_hash: Mapped[str | None] = mapped_column(String(64))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "spot_id", "model_id", "variant", "lead_bucket", "direction_sector",
                         name="uq_forecast_verification_score"),
        CheckConstraint("direction_sector >= 0 AND direction_sector < 12", name="ck_forecast_verification_sector"),
        CheckConstraint("sample_count >= 0", name="ck_forecast_verification_samples"),
    )


class ForecastSectorGateEvidence(Base):
    """Paired, day-blocked evidence authorising one sector candidate.

    Diagnostic verification scores stay grouped by lead bucket and direction.
    This row stores the stricter activation statistic: baseline and candidate
    are paired by forecast identity, repeated runs are collapsed by valid time,
    and uncertainty is bootstrapped over distinct UTC days.
    """

    __tablename__ = "forecast_sector_gate_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spots.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    gate_context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    training_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    matched_forecasts: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_valid_times: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_days: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_mae_ms: Mapped[float | None] = mapped_column(Float)
    candidate_mae_ms: Mapped[float | None] = mapped_column(Float)
    mae_drop_ms: Mapped[float | None] = mapped_column(Float)
    ci_lower_ms: Mapped[float | None] = mapped_column(Float)
    ci_upper_ms: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    policy: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id", "spot_id", name="uq_forecast_sector_gate_evidence_run_spot"
        ),
        CheckConstraint(
            "candidate_version >= 1", name="ck_forecast_sector_gate_version"
        ),
        CheckConstraint(
            "matched_forecasts >= 0 AND unique_valid_times >= 0 AND distinct_days >= 0",
            name="ck_forecast_sector_gate_counts",
        ),
        CheckConstraint(
            "status IN ('collecting','rejected','passed')",
            name="ck_forecast_sector_gate_status",
        ),
        Index(
            "ix_forecast_sector_gate_candidate",
            "spot_id",
            "candidate_version",
            "computed_at",
        ),
    )


class ForecastSectorBuild(Base):
    """Per-spot sector-producer build state: resumable cursor + coverage summary.

    Records the last producer run per spot (status, content hash, candidate
    version). ``built_at`` orders the resumable cron batch so every spot drains
    and none runs twice; ``content_hash`` gates idempotent re-runs. This never
    activates a sector — it only records what candidate was written.
    """

    __tablename__ = "forecast_sector_builds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    producer: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int | None] = mapped_column(Integer)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("spot_id", "producer", name="uq_forecast_sector_build"),
    )
