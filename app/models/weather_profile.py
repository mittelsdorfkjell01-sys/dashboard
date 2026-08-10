from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class SpotWeatherProfile(Base, TimestampMixin):
    """Reviewed metadata for local wind physics; never inferred from ``facing``."""

    __tablename__ = "spot_weather_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    spot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spots.id", ondelete="CASCADE"), nullable=False, unique=True)
    timezone: Mapped[str | None] = mapped_column(String(64))
    elevation_m: Mapped[float | None] = mapped_column(Float)
    coastal_normal_deg: Mapped[float | None] = mapped_column(Float)
    exposure: Mapped[str | None] = mapped_column(String(20))
    roughness_length_m: Mapped[float | None] = mapped_column(Float)
    land_reference: Mapped[dict | None] = mapped_column(JSONB)
    water_reference: Mapped[dict | None] = mapped_column(JSONB)
    quality_tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'coordinates'"))
    physics_version: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'wind-v1'"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    sectors: Mapped[list["SpotWeatherSector"]] = relationship(back_populates="profile", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("coastal_normal_deg IS NULL OR (coastal_normal_deg >= 0 AND coastal_normal_deg < 360)", name="ck_weather_profile_coastal_normal"),
        CheckConstraint("elevation_m IS NULL OR elevation_m >= -500", name="ck_weather_profile_elevation"),
        CheckConstraint("roughness_length_m IS NULL OR roughness_length_m > 0", name="ck_weather_profile_roughness"),
        CheckConstraint("quality_tier IN ('coordinates','coastal','extended','advanced')", name="ck_weather_profile_tier"),
        CheckConstraint("exposure IS NULL OR exposure IN ('sheltered','neutral','exposed')", name="ck_weather_profile_exposure"),
    )


class SpotWeatherSector(Base, TimestampMixin):
    __tablename__ = "spot_weather_sectors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spot_weather_profiles.id", ondelete="CASCADE"), nullable=False)
    start_deg: Mapped[float] = mapped_column(Float, nullable=False)
    end_deg: Mapped[float] = mapped_column(Float, nullable=False)
    speed_factor: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("1.0"))
    direction_offset_deg: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    note: Mapped[str | None] = mapped_column(String(500))

    profile: Mapped[SpotWeatherProfile] = relationship(back_populates="sectors")

    __table_args__ = (
        CheckConstraint("start_deg >= 0 AND start_deg < 360", name="ck_weather_sector_start"),
        CheckConstraint("end_deg >= 0 AND end_deg < 360", name="ck_weather_sector_end"),
        CheckConstraint("speed_factor >= 0.60 AND speed_factor <= 1.35", name="ck_weather_sector_factor"),
        CheckConstraint("direction_offset_deg >= -15 AND direction_offset_deg <= 15", name="ck_weather_sector_direction"),
        UniqueConstraint("profile_id", "start_deg", "end_deg", "version", name="uq_weather_sector_version"),
    )
