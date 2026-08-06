import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


QUALITY_LEVELS = (
    "unavailable",
    "model_only",
    "reviewed_anchor",
    "manual_calibrated",
    "gauge_calibrated",
)


class TideProfile(Base, TimestampMixin):
    """Active tide configuration for one spot.

    Every effective change first creates a :class:`TideProfileRevision`. The
    astronomical model remains immutable; offsets form a separate calibration
    layer and advance ``version``.
    """

    __tablename__ = "tide_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    spot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    public_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    timezone: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'FES2022b'"))
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'2022b'"))
    automatic_anchor: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    manual_anchor: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    anchor_distance_m: Mapped[float | None] = mapped_column(Float)
    anchor_kind: Mapped[str | None] = mapped_column(String(30))
    anchor_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'needs_review'")
    )
    anchor_determined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anchor_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anchor_warnings: Mapped[list | None] = mapped_column(JSONB)
    global_offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    high_offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    low_offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    constituent_adjustments: Mapped[dict | None] = mapped_column(JSONB)
    manual_uncertainty_minutes: Mapped[int | None] = mapped_column(Integer)
    estimated_uncertainty_minutes: Mapped[int | None] = mapped_column(Integer)
    uncertainty_source: Mapped[str | None] = mapped_column(String(80))
    quality_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'unavailable'")
    )
    note: Mapped[str | None] = mapped_column(Text)
    correction_reason: Mapped[str | None] = mapped_column(Text)
    correction_source: Mapped[str | None] = mapped_column(Text)
    edited_by: Mapped[str | None] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calculation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'not_configured'")
    )
    calculation_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("version > 0", name="ck_tide_profiles_version"),
        CheckConstraint(
            "anchor_status IN ('needs_review','auto_selected','reviewed','invalid')",
            name="ck_tide_profiles_anchor_status",
        ),
        CheckConstraint(
            "quality_status IN ('unavailable','model_only','reviewed_anchor','manual_calibrated','gauge_calibrated')",
            name="ck_tide_profiles_quality",
        ),
        CheckConstraint(
            "calculation_status IN ('not_configured','queued','running','ready','failed','stale')",
            name="ck_tide_profiles_calculation_status",
        ),
        CheckConstraint("anchor_distance_m IS NULL OR anchor_distance_m >= 0", name="ck_tide_profiles_anchor_distance"),
        CheckConstraint("manual_uncertainty_minutes IS NULL OR manual_uncertainty_minutes >= 0", name="ck_tide_profiles_manual_uncertainty"),
        CheckConstraint("estimated_uncertainty_minutes IS NULL OR estimated_uncertainty_minutes >= 0", name="ck_tide_profiles_estimated_uncertainty"),
        Index("ix_tide_profiles_due", "enabled", "calculation_status", "last_calculated_at"),
        Index("ix_tide_profiles_automatic_anchor", "automatic_anchor", postgresql_using="gist"),
        Index("ix_tide_profiles_manual_anchor", "manual_anchor", postgresql_using="gist"),
    )


class TideProfileRevision(Base):
    __tablename__ = "tide_profile_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tide_profiles.id", ondelete="CASCADE"), nullable=False)
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("profile_id", "version", name="uq_tide_profile_revision_version"),
        Index("ix_tide_profile_revisions_spot", "spot_id", "created_at"),
    )


class TideEvent(Base):
    __tablename__ = "tide_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_key: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(8), nullable=False)
    raw_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    corrected_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    relative_height: Mapped[float | None] = mapped_column(Float)
    uncertainty_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_name: Mapped[str] = mapped_column(String(40), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'valid'"))

    __table_args__ = (
        CheckConstraint("event_type IN ('high','low')", name="ck_tide_events_type"),
        CheckConstraint("status IN ('valid','superseded')", name="ck_tide_events_status"),
        CheckConstraint("uncertainty_minutes >= 0", name="ck_tide_events_uncertainty"),
        UniqueConstraint("spot_id", "profile_version", "cycle_key", name="uq_tide_events_cycle"),
        Index("ix_tide_events_public", "spot_id", "corrected_time", "status"),
    )


class TideEventOverride(Base, TimestampMixin):
    __tablename__ = "tide_event_overrides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(8), nullable=False)
    raw_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_model_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    manual_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    difference_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'single'"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        CheckConstraint("event_type IN ('high','low')", name="ck_tide_event_overrides_type"),
        CheckConstraint("scope IN ('single','high_profile','low_profile','calibration_input')", name="ck_tide_event_overrides_scope"),
        Index("ix_tide_event_overrides_match", "spot_id", "event_type", "raw_time", "active"),
    )


class TideCalculationRun(Base):
    __tablename__ = "tide_calculation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    spot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'queued'"))
    requested_by: Mapped[str | None] = mapped_column(String(120))
    model_name: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'FES2022b'"))
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'2022b'"))
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    profile_version: Mapped[int | None] = mapped_column(Integer)
    processed_spots: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failed_spots: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    details: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("status IN ('queued','running','succeeded','partial','failed')", name="ck_tide_calculation_runs_status"),
        Index("ix_tide_calculation_runs_queue", "status", "created_at"),
        Index("ix_tide_calculation_runs_spot", "spot_id", "created_at"),
    )
