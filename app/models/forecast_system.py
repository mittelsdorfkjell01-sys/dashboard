"""Persistent, versioned state for the Surfwinddata forecast publisher."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Float,
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


class ForecastProvider(Base, TimestampMixin):
    __tablename__ = "forecast_providers"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    licence: Mapped[str] = mapped_column(String(120), nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    commercial_review_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    provider_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class GeodataDataset(Base, TimestampMixin):
    __tablename__ = "geodata_datasets"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    product_instance: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    licence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fallback_key: Mapped[str | None] = mapped_column(String(80))
    legal_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_geodata_dataset_version"),
    )


class GeodataAsset(Base, TimestampMixin):
    __tablename__ = "geodata_assets"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geodata_datasets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    asset_key: Mapped[str] = mapped_column(String(240), nullable=False)
    tile_id: Mapped[str | None] = mapped_column(String(40))
    bbox: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    file_type: Mapped[str] = mapped_column(String(30), nullable=False)
    crs: Mapped[str] = mapped_column(String(40), nullable=False)
    byte_range: Mapped[str | None] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    asset_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "asset_key", "byte_range", name="uq_geodata_asset_window"
        ),
        CheckConstraint(
            "status IN ('downloading','ready','invalid','evicted')",
            name="ck_geodata_asset_status",
        ),
        Index("ix_geodata_asset_lru", "status", "last_accessed_at"),
    )


class SpotGeoProfileInput(Base, TimestampMixin):
    __tablename__ = "spot_geo_profile_inputs"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spot_geo_profile_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geodata_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    quality: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "asset_id", "role", name="uq_geo_profile_asset_role"
        ),
    )


class SpotGeoShadowProfile(Base, TimestampMixin):
    __tablename__ = "spot_geo_shadow_profiles"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    profile_class: Mapped[str] = mapped_column(String(1), nullable=False)
    active_shadow: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    analysis: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    warnings: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    __table_args__ = (
        UniqueConstraint("spot_id", "input_hash", name="uq_spot_geo_shadow_input"),
        CheckConstraint(
            "profile_class IN ('A','B','C','D')", name="ck_geo_shadow_class"
        ),
        CheckConstraint(
            "status IN ('ready','blocked_credentials','blocked_license','blocked_quota','blocked_budget','failed')",
            name="ck_geo_shadow_status",
        ),
        Index("ix_geo_shadow_active", "spot_id", "active_shadow"),
    )


class SpotGeoShadowSector(Base, TimestampMixin):
    __tablename__ = "spot_geo_shadow_sectors"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    shadow_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spot_geo_shadow_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    sector_index: Mapped[int] = mapped_column(Integer, nullable=False)
    center_deg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    quality: Mapped[dict] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "shadow_profile_id", "sector_index", name="uq_geo_shadow_sector"
        ),
        CheckConstraint(
            "sector_index >= 0 AND sector_index < 16", name="ck_geo_shadow_sector_index"
        ),
        CheckConstraint(
            "status IN ('valid','degraded','unavailable','conflicted','not_applicable')",
            name="ck_geo_shadow_sector_status",
        ),
        Index("ix_geo_shadow_sector_profile", "shadow_profile_id", "sector_index"),
    )


class ForecastModelRun(Base, TimestampMixin):
    __tablename__ = "forecast_model_runs"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    provider_key: Mapped[str] = mapped_column(String(40), nullable=False)
    model_key: Mapped[str] = mapped_column(String(80), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128))
    bytes_downloaded: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    diagnostics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    __table_args__ = (
        UniqueConstraint(
            "provider_key", "model_key", "run_at", name="uq_forecast_model_run"
        ),
        CheckConstraint(
            "status IN ('detected','downloading','validating','ready','failed','expired')",
            name="ck_forecast_model_run_status",
        ),
        Index("ix_forecast_model_run_latest", "provider_key", "model_key", "run_at"),
    )


class SpotGeoProfileVersion(Base, TimestampMixin):
    __tablename__ = "spot_geo_profile_versions"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    coordinate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    quality: Mapped[str] = mapped_column(String(20), nullable=False)
    sources: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    profile: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    warnings: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    __table_args__ = (
        UniqueConstraint("spot_id", "version", name="uq_spot_geo_profile_version"),
        UniqueConstraint(
            "spot_id",
            "coordinate_hash",
            "algorithm_version",
            name="uq_spot_geo_profile_input",
        ),
        CheckConstraint(
            "status IN ('pending','processing','ready','failed','stale')",
            name="ck_spot_geo_profile_status",
        ),
        Index("ix_spot_geo_profile_active", "spot_id", "active"),
    )


class ForecastSnapshot(Base, TimestampMixin):
    __tablename__ = "forecast_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consensus_version: Mapped[str] = mapped_column(String(40), nullable=False)
    physics_version: Mapped[str] = mapped_column(String(40), nullable=False)
    geo_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spot_geo_profile_versions.id", ondelete="SET NULL"),
    )
    quality_level: Mapped[str] = mapped_column(String(32), nullable=False)
    fallback_status: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    internal: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    attributions: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    __table_args__ = (
        CheckConstraint(
            "quality_level IN ('baseline','automatic','calibrated','reviewed')",
            name="ck_forecast_snapshot_quality",
        ),
        Index("ix_forecast_snapshot_active", "spot_id", "active"),
        Index("ix_forecast_snapshot_generated", "spot_id", "generated_at"),
    )


class ForecastProcessingJob(Base, TimestampMixin):
    __tablename__ = "forecast_processing_jobs"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    spot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(160), nullable=False, unique=True
    )
    requested_by: Mapped[str | None] = mapped_column(String(160))
    progress: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    options: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    diagnostics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','processing','succeeded','failed','superseded','paused')",
            name="ck_forecast_processing_job_status",
        ),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_forecast_processing_job_progress",
        ),
        Index("ix_forecast_job_queue", "status", "created_at"),
        Index("ix_forecast_job_spot", "spot_id", "created_at"),
    )
