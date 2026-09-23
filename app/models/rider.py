"""Private rider setup and first-party interaction events."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RiderProfile(Base, TimestampMixin):
    __tablename__ = "rider_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    app_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    home_location: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    max_travel_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    travel_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'day_trip'")
    )
    availability: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False, server_default=text("'{}'::smallint[]")
    )
    min_water_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    excluded_bottoms: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::varchar[]")
    )
    profile_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )

    __table_args__ = (
        CheckConstraint(
            "weight_kg IS NULL OR (weight_kg >= 30 AND weight_kg <= 160)",
            name="ck_rider_profiles_weight",
        ),
        CheckConstraint(
            "max_travel_km IS NULL OR (max_travel_km >= 0 AND max_travel_km <= 20000)",
            name="ck_rider_profiles_travel_distance",
        ),
        CheckConstraint(
            "travel_mode IN ('day_trip','weekend','trip','camper')",
            name="ck_rider_profiles_travel_mode",
        ),
        CheckConstraint(
            "availability <@ ARRAY[0,1,2,3,4,5,6]::smallint[]",
            name="ck_rider_profiles_availability",
        ),
        CheckConstraint(
            "min_water_temp_c IS NULL OR (min_water_temp_c >= -5 AND min_water_temp_c <= 40)",
            name="ck_rider_profiles_water_temp",
        ),
        CheckConstraint(
            "excluded_bottoms <@ ARRAY['sand','rock','reef','mixed']::varchar[]",
            name="ck_rider_profiles_excluded_bottoms",
        ),
        CheckConstraint("profile_version >= 1", name="ck_rider_profiles_version"),
        Index("ix_rider_profiles_home_location", "home_location", postgresql_using="gist"),
    )


class RiderSportProfile(Base, TimestampMixin):
    __tablename__ = "rider_sport_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    rider_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rider_profiles.id", ondelete="CASCADE"), nullable=False
    )
    sport: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    style_weights: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    preferred_water_character: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::varchar[]")
    )

    __table_args__ = (
        UniqueConstraint("rider_profile_id", "sport", name="uq_rider_sport_profile"),
        CheckConstraint(
            "sport IN ('kitesurf','windsurf','wing','surf')",
            name="ck_rider_sport_profiles_sport",
        ),
        CheckConstraint(
            "level IN ('beginner','advanced','expert','competition')",
            name="ck_rider_sport_profiles_level",
        ),
        CheckConstraint(
            "jsonb_typeof(style_weights) = 'object'",
            name="ck_rider_sport_profiles_style_weights",
        ),
        CheckConstraint(
            "style_weights - ARRAY['freeride','freestyle','big_air','wave_riding','wavekite']::text[] = '{}'::jsonb",
            name="ck_rider_sport_profiles_style_keys",
        ),
        CheckConstraint(
            "NOT jsonb_path_exists(style_weights, '$.* ? (@ != 0 && @ != 1 && @ != 2 && @ != 3)')",
            name="ck_rider_sport_profiles_style_values",
        ),
        CheckConstraint(
            "preferred_water_character <@ ARRAY['flach','chop','welle_klein','welle_gross','tiefes_wasser']::varchar[]",
            name="ck_rider_sport_profiles_water_character",
        ),
    )


class GearItem(Base, TimestampMixin):
    __tablename__ = "gear_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    rider_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rider_profiles.id", ondelete="CASCADE"), nullable=False
    )
    sport: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    size: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    board_type: Mapped[str | None] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        CheckConstraint(
            "sport IN ('kitesurf','windsurf','wing','surf')", name="ck_gear_items_sport"
        ),
        CheckConstraint("kind IN ('kite','board','foil')", name="ck_gear_items_kind"),
        CheckConstraint("size IS NULL OR size > 0", name="ck_gear_items_size"),
        CheckConstraint(
            "kind <> 'kite' OR size IS NOT NULL", name="ck_gear_items_kite_size"
        ),
        CheckConstraint(
            "board_type IS NULL OR board_type IN ('twintip','surfboard','foil','bigair_twintip')",
            name="ck_gear_items_board_type",
        ),
        CheckConstraint("sort_order >= 0", name="ck_gear_items_sort_order"),
        Index("ix_gear_items_profile_sport", "rider_profile_id", "sport", "sort_order"),
    )


class UserEvent(Base):
    __tablename__ = "user_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE")
    )
    anon_id: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    spot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spots.id", ondelete="SET NULL")
    )
    surface: Mapped[str | None] = mapped_column(String(40))
    recommendation_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_log.id", ondelete="SET NULL"),
    )
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "(app_user_id IS NOT NULL) <> (anon_id IS NOT NULL)",
            name="ck_user_events_one_actor",
        ),
        CheckConstraint(
            "type IN ('impression','click','favorite_add','favorite_remove','dismiss','search','session_checkin','notification_sent','notification_opened','notification_dismissed')",
            name="ck_user_events_type",
        ),
        CheckConstraint("jsonb_typeof(context) = 'object'", name="ck_user_events_context"),
        Index("ix_user_events_type_created", "type", "created_at"),
        Index("ix_user_events_spot_created", "spot_id", "created_at"),
        Index("ix_user_events_account", "app_user_id"),
        Index("ix_user_events_recommendation", "recommendation_log_id"),
    )
