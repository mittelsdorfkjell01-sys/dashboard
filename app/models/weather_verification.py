"""Persistent observations and forecast verification used for wind calibration."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func, text
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
    country_code: Mapped[str | None] = mapped_column(String(3))
    operator: Mapped[str | None] = mapped_column(String(160))
    station_type: Mapped[str | None] = mapped_column(String(80))
    sensor_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    active_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(Text)
    metadata_payload_hash: Mapped[str | None] = mapped_column(String(64))
    physical_station_group: Mapped[str | None] = mapped_column(String(100))
    correlation_group: Mapped[str | None] = mapped_column(String(100))
    identity_review_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unreviewed")
    monitoring_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    residual_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    holdout_target_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    holdout_input_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    current_epoch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_station_epochs.id"))

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
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    measurement_period_seconds: Mapped[int | None] = mapped_column(Integer)
    averaging_period_seconds: Mapped[int | None] = mapped_column(Integer)
    qc_version: Mapped[str | None] = mapped_column(String(80))
    qc_stage: Mapped[str | None] = mapped_column(String(40))
    qc_flags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    raw_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_observation_revisions.id"))
    epoch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_station_epochs.id"))
    availability_class: Mapped[str] = mapped_column(String(32), nullable=False, server_default="availability_unproven")
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("station_id", "observed_at", name="uq_weather_observation_time"),
        Index("ix_observation_epoch_time", "epoch_id", "observed_at"),
        CheckConstraint("wind_speed_ms >= 0 AND wind_speed_ms <= 100", name="ck_weather_observation_speed"),
        CheckConstraint("wind_direction_deg IS NULL OR (wind_direction_deg >= 0 AND wind_direction_deg < 360)", name="ck_weather_observation_dir"),
        CheckConstraint(
            "availability_class IN ('captured_operationally','historical_backfill','availability_unproven')",
            name="ck_weather_observation_availability",
        ),
        CheckConstraint(
            "gust_period_seconds IS NULL OR "
            "(gust_period_seconds >= 1 AND gust_period_seconds <= 86400)",
            name="ck_weather_observation_gust_period",
        ),
    )


class WeatherStationMetadataRevision(Base):
    """Immutable source metadata snapshot for a configured provider station."""

    __tablename__ = "weather_station_metadata_revisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(String(160))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("station_id", "payload_hash", name="uq_weather_station_metadata_revision"),)


class WeatherStationEpoch(Base):
    __tablename__ = "weather_station_epochs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False)
    epoch_number: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metadata_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_station_metadata_revisions.id"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending_review")
    reviewer: Mapped[str | None] = mapped_column(String(160))
    review_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("station_id", "epoch_number", name="uq_station_epoch_number"),
        UniqueConstraint("station_id", "configuration_hash", name="uq_station_epoch_configuration"),
        CheckConstraint("status IN ('pending_review','reviewed','superseded')", name="ck_station_epoch_status"),
        Index("ix_station_epoch_status", "station_id", "status"),
    )


class WeatherStationDossier(Base):
    __tablename__ = "weather_station_dossiers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    epoch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_station_epochs.id", ondelete="CASCADE"), nullable=False)
    dossier_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ready_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_dossier_epoch_generated", "epoch_id", "generated_at"),)


class WeatherStationGroupDecision(Base):
    __tablename__ = "weather_station_group_decisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    epoch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_station_epochs.id", ondelete="CASCADE"), nullable=False)
    group_type: Mapped[str] = mapped_column(String(24), nullable=False)
    group_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actor: Mapped[str | None] = mapped_column(String(160))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("group_type IN ('physical','sensor','correlation')", name="ck_station_group_type"),
        CheckConstraint("status IN ('proposed','confirmed','rejected')", name="ck_station_group_status"),
        Index("ix_group_decision_epoch_type_time", "epoch_id", "group_type", "decided_at"),
        Index("uq_station_group_proposal", "epoch_id", "group_type", "group_key",
              unique=True, postgresql_where=text("status = 'proposed'")),
    )


class WeatherStationProviderCursor(Base):
    __tablename__ = "weather_station_provider_cursors"
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    watermark_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_cycle_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_class: Mapped[str | None] = mapped_column(String(120))


class WeatherProviderHttpResource(Base):
    """Validated provider representation plus its RFC 9110 validators."""

    __tablename__ = "weather_provider_http_resources"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_variant_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_variant: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    response_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_not_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "provider", "resource_url", "request_variant_hash",
            name="uq_weather_provider_http_resource",
        ),
        CheckConstraint("payload_size_bytes >= 0", name="ck_provider_http_payload_size"),
        CheckConstraint("last_status_code IN (200, 304)", name="ck_provider_http_status"),
        Index("ix_provider_http_checked", "provider", "last_checked_at"),
    )


class WeatherStationCatalogState(Base):
    """Sanitized scheduler state for one provider's metadata catalog."""

    __tablename__ = "weather_station_catalog_states"
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_class: Mapped[str | None] = mapped_column(String(120))
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_counts: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        CheckConstraint(
            "consecutive_failures >= 0", name="ck_station_catalog_failures"
        ),
    )


class WeatherStationCaptureCycle(Base):
    """Append-only provider-cycle evidence for daily operations reporting."""

    __tablename__ = "weather_station_capture_cycles"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    counts: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('observations','catalog')", name="ck_station_cycle_job_type"
        ),
        CheckConstraint(
            "status IN ('success','partial','error','no_work','overlap_skipped')",
            name="ck_station_cycle_status",
        ),
        Index(
            "ix_station_capture_cycle_provider_time",
            "job_type", "provider", "started_at",
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


class WeatherObservationRevision(Base):
    """Insert-only provider state. A changed value awaits explicit review."""

    __tablename__ = "weather_observation_revisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_station_id: Mapped[str] = mapped_column(String(80), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(String(160))
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    qc_version: Mapped[str] = mapped_column(String(80), nullable=False)
    qc_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    qc_flags: Mapped[list] = mapped_column(JSONB, nullable=False)
    revision_status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    epoch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_station_epochs.id"))
    availability_class: Mapped[str] = mapped_column(String(32), nullable=False, server_default="availability_unproven")
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("station_id", "fingerprint", name="uq_weather_revision_station_fingerprint"),
        Index("uq_weather_revision_current", "station_id", "observed_at", unique=True,
              postgresql_where=text("revision_status = 'current'")),
        Index("ix_weather_revision_station_time", "station_id", "observed_at"),
        Index("ix_revision_epoch_time", "epoch_id", "observed_at"),
        CheckConstraint("revision_status IN ('current','pending_review','rejected','quarantined')", name="ck_weather_revision_status"),
        CheckConstraint(
            "availability_class IN ('captured_operationally','historical_backfill','availability_unproven')",
            name="ck_weather_revision_availability",
        ),
    )


class WeatherStationApprovalAudit(Base):
    __tablename__ = "weather_station_approval_audit"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_stations.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    epoch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("weather_station_epochs.id"))
    dossier_hash: Mapped[str | None] = mapped_column(String(64))
    policy_version: Mapped[str | None] = mapped_column(String(80))
    group_version: Mapped[str | None] = mapped_column(String(80))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_station_approval_epoch_scope_time", "epoch_id", "scope", "decided_at"),)


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
