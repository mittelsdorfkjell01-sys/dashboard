"""Durable, shadow-first execution evidence for LiveWind."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class WeatherLiveWindJob(Base):
    """One idempotent analysis attempt for one spot and analysis cycle.

    PostgreSQL row locks and the worker token form the distributed lease.  The
    result is retained as internal shadow evidence; public serving never reads
    this payload directly.
    """

    __tablename__ = "weather_live_wind_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spots.id", ondelete="CASCADE"),
        nullable=False,
    )
    region_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regions.id", ondelete="SET NULL"),
    )
    region_key: Mapped[str] = mapped_column(
        String(120), nullable=False, server_default="unassigned"
    )
    terrain_class: Mapped[str] = mapped_column(
        String(48), nullable=False, server_default="unknown"
    )
    cycle_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rollout_stage: Mapped[str] = mapped_column(String(16), nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="queued"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    error_class: Mapped[str | None] = mapped_column(String(120))

    product_status: Mapped[str | None] = mapped_column(String(24))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    station_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    correction_magnitude_ms: Mapped[float | None] = mapped_column(Float)
    conflict_index: Mapped[float | None] = mapped_column(Float)
    uncertainty_ms: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    fallback_reason: Mapped[str | None] = mapped_column(String(160))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    baseline_cache_hit: Mapped[bool | None] = mapped_column(Boolean)
    exclusion_reasons: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    result_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    diagnostics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "spot_id",
            "cycle_at",
            "analysis_version",
            name="uq_weather_live_wind_job_cycle",
        ),
        CheckConstraint(
            "rollout_stage IN ('shadow','internal','pilot','regional','global')",
            name="ck_weather_live_wind_job_rollout",
        ),
        CheckConstraint(
            "status IN ('queued','processing','retry_wait','succeeded','failed')",
            name="ck_weather_live_wind_job_status",
        ),
        CheckConstraint(
            "product_status IS NULL OR "
            "product_status IN ('baseline','station_adjusted','unavailable')",
            name="ck_weather_live_wind_job_product_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND station_count >= 0",
            name="ck_weather_live_wind_job_counts",
        ),
        CheckConstraint(
            "conflict_index IS NULL OR "
            "(conflict_index >= 0 AND conflict_index <= 1)",
            name="ck_weather_live_wind_job_conflict",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_weather_live_wind_job_confidence",
        ),
        Index(
            "ix_weather_live_wind_jobs_claim",
            "status",
            "available_at",
            "created_at",
        ),
        Index(
            "ix_weather_live_wind_jobs_spot_cycle",
            "spot_id",
            "cycle_at",
        ),
        Index(
            "ix_weather_live_wind_jobs_region_cycle",
            "region_key",
            "cycle_at",
        ),
        Index(
            "uq_weather_live_wind_jobs_active_spot",
            "spot_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued','processing','retry_wait')"
            ),
        ),
    )
