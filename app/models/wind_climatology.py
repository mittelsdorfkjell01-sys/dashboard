import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WindClimatologyCell(Base, TimestampMixin):
    __tablename__ = "wind_climatology_cells"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False, unique=True)
    selection_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'automatic'"))
    spot_lat: Mapped[float] = mapped_column(Float, nullable=False)
    spot_lon: Mapped[float] = mapped_column(Float, nullable=False)
    requested_lat: Mapped[float] = mapped_column(Float, nullable=False)
    requested_lon: Mapped[float] = mapped_column(Float, nullable=False)
    actual_lat: Mapped[float | None] = mapped_column(Float)
    actual_lon: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'ERA5'"))
    resolution_deg: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.25"))
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))


class WindClimatologyRun(Base, TimestampMixin):
    __tablename__ = "wind_climatology_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    cell_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wind_climatology_cells.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False, server_default=text("'Open-Meteo Historical Weather API'"))
    model: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'ERA5'"))
    unit: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'kn'"))
    timezone: Mapped[str | None] = mapped_column(String(64))
    grid_lat: Mapped[float | None] = mapped_column(Float)
    grid_lon: Mapped[float | None] = mapped_column(Float)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    annual_aggregates: Mapped[list | None] = mapped_column(JSONB)
    public_data: Mapped[dict | None] = mapped_column(JSONB)
    quality_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        Index("ix_wind_clim_runs_spot_status", "spot_id", "status"),
        Index("uq_wind_clim_active_spot", "spot_id", unique=True, postgresql_where=text("is_active")),
        Index("uq_wind_clim_inflight_config", "spot_id", "config_hash", unique=True, postgresql_where=text("status IN ('pending','processing')")),
    )
