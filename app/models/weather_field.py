"""Control-plane records for immutable weather-field assets and publications."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
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


class WeatherFieldModel(Base, TimestampMixin):
    __tablename__ = "weather_field_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    model_key: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    coverage: Mapped[dict] = mapped_column(JSONB, nullable=False)
    native_grid: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cadence_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_step_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    max_horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    licence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    attribution: Mapped[list] = mapped_column(JSONB, nullable=False)
    model_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        UniqueConstraint("provider_key", "model_key", name="uq_weather_field_model"),
        CheckConstraint(
            "status IN ('active','disabled','blocked_license','retired')",
            name="ck_weather_field_model_status",
        ),
        CheckConstraint(
            "cadence_hours > 0 AND forecast_step_hours > 0 "
            "AND max_horizon_hours >= forecast_step_hours",
            name="ck_weather_field_model_schedule",
        ),
        CheckConstraint("priority >= 0", name="ck_weather_field_model_priority"),
        Index("ix_weather_field_model_active", "status", "priority"),
    )


class WeatherFieldRun(Base, TimestampMixin):
    __tablename__ = "weather_field_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_models.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    model_key: Mapped[str] = mapped_column(String(80), nullable=False)
    model_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(40), nullable=False)
    processing_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    coverage: Mapped[dict] = mapped_column(JSONB, nullable=False)
    native_grid: Mapped[dict] = mapped_column(JSONB, nullable=False)
    valid_times: Mapped[list] = mapped_column(JSONB, nullable=False)
    source_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    diagnostics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    bytes_downloaded: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "provider_key",
            "model_key",
            "model_run_at",
            "processing_version",
            name="uq_weather_field_run_identity",
        ),
        CheckConstraint(
            "status IN ('discovered','downloading','processing','quality_pending',"
            "'ready','rejected','failed','expired')",
            name="ck_weather_field_run_status",
        ),
        CheckConstraint("bytes_downloaded >= 0", name="ck_weather_field_run_bytes"),
        Index(
            "ix_weather_field_run_latest",
            "model_id",
            "model_run_at",
        ),
    )


class WeatherFieldAsset(Base, TimestampMixin):
    __tablename__ = "weather_field_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    valid_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_zoom: Mapped[int | None] = mapped_column(Integer)
    tile_x: Mapped[int | None] = mapped_column(Integer)
    tile_y: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    compression: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        UniqueConstraint("object_key", name="uq_weather_field_asset_object_key"),
        CheckConstraint(
            "asset_type IN ('manifest','asset_index','tile','series_tile','metadata')",
            name="ck_weather_field_asset_type",
        ),
        CheckConstraint(
            "status IN ('staged','verified','invalid','deleted')",
            name="ck_weather_field_asset_status",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_weather_field_asset_size"),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name="ck_weather_field_asset_sha256"
        ),
        CheckConstraint(
            "(asset_type <> 'tile') OR "
            "(valid_time IS NOT NULL AND source_zoom IS NOT NULL "
            "AND tile_x IS NOT NULL AND tile_y IS NOT NULL)",
            name="ck_weather_field_tile_coordinates",
        ),
        CheckConstraint(
            "(asset_type <> 'series_tile') OR "
            "(valid_time IS NULL AND source_zoom IS NOT NULL "
            "AND tile_x IS NOT NULL AND tile_y IS NOT NULL)",
            name="ck_weather_field_series_tile_coordinates",
        ),
        Index("ix_weather_field_asset_run_status", "run_id", "status"),
        Index(
            "ix_weather_field_asset_tile",
            "run_id",
            "valid_time",
            "source_zoom",
            "tile_x",
            "tile_y",
        ),
    )


class WeatherFieldQualityEvent(Base, TimestampMixin):
    __tablename__ = "weather_field_quality_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    gate_key: Mapped[str] = mapped_column(String(80), nullable=False)
    hard_gate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("run_id", "gate_key", name="uq_weather_field_quality_gate"),
        Index("ix_weather_field_quality_run", "run_id", "hard_gate", "passed"),
    )


class WeatherFieldPublication(Base, TimestampMixin):
    __tablename__ = "weather_field_publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    manifest_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_publication_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_publications.id", ondelete="SET NULL"),
    )
    actor: Mapped[str | None] = mapped_column(String(160))
    reason: Mapped[str | None] = mapped_column(Text)
    generation: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('staged','active','superseded','rolled_back','rejected')",
            name="ck_weather_field_publication_status",
        ),
        CheckConstraint("generation >= 0", name="ck_weather_field_publication_generation"),
        Index(
            "uq_weather_field_publication_active_scope",
            "scope_key",
            unique=True,
            postgresql_where=text("active IS TRUE"),
        ),
        Index("ix_weather_field_publication_history", "scope_key", "generation"),
    )


class WeatherFieldJob(Base, TimestampMixin):
    __tablename__ = "weather_field_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_field_runs.id", ondelete="CASCADE"),
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    options: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    diagnostics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('discover','process','retention')",
            name="ck_weather_field_job_kind",
        ),
        CheckConstraint(
            "status IN ('queued','processing','succeeded','failed','superseded')",
            name="ck_weather_field_job_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_weather_field_job_attempts"),
        Index("ix_weather_field_job_queue", "status", "scheduled_at"),
        Index("ix_weather_field_job_run", "run_id", "created_at"),
    )
