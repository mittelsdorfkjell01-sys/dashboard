"""rider profiles, gear, events, and scoring parameters v3

Revision ID: 0067_rider_profiles_events
Revises: 0066_scoring_params_v2
"""

from __future__ import annotations

from copy import deepcopy

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0067_rider_profiles_events"
down_revision = "0066_scoring_params_v2"
branch_labels = None
depends_on = None


RIDER_MODEL = {
    "k_board": {
        "twintip": 2.2,
        "surfboard": 2.0,
        "foil": 1.4,
        "bigair_twintip": 2.35,
    },
    "f_lo": 0.8,
    "f_hi": 1.35,
    "levels": {
        "beginner": {"max_kt": 24.0, "gust_tolerance_kt": 5.0},
        "advanced": {"max_kt": 34.0, "gust_tolerance_kt": 8.0},
        "expert": {"max_kt": 42.0, "gust_tolerance_kt": 12.0},
        "competition": {"max_kt": 50.0, "gust_tolerance_kt": 15.0},
    },
}

DEFAULT_RIDER = {
    "weight_kg": 78.0,
    "level": "advanced",
    "quiver": [
        {"kind": "kite", "size": 9.0},
        {"kind": "kite", "size": 12.0},
        {"kind": "board", "board_type": "twintip"},
    ],
    "style_weights": {
        "freeride": 2,
        "freestyle": 1,
        "big_air": 1,
        "wave_riding": 0,
        "wavekite": 0,
    },
    "travel_mode": "day_trip",
}


def _geography() -> geoalchemy2.types.Geography:
    return geoalchemy2.types.Geography(
        geometry_type="POINT", srid=4326, spatial_index=False
    )


def upgrade() -> None:
    op.create_table(
        "rider_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("app_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 2)),
        sa.Column("home_location", _geography()),
        sa.Column("max_travel_km", sa.Numeric(7, 2)),
        sa.Column("travel_mode", sa.String(20), server_default="day_trip", nullable=False),
        sa.Column("availability", postgresql.ARRAY(sa.SmallInteger()), server_default=sa.text("'{}'::smallint[]"), nullable=False),
        sa.Column("min_water_temp_c", sa.Numeric(4, 1)),
        sa.Column("excluded_bottoms", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'::varchar[]"), nullable=False),
        sa.Column("profile_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("weight_kg IS NULL OR (weight_kg >= 30 AND weight_kg <= 160)", name="ck_rider_profiles_weight"),
        sa.CheckConstraint("max_travel_km IS NULL OR (max_travel_km >= 0 AND max_travel_km <= 20000)", name="ck_rider_profiles_travel_distance"),
        sa.CheckConstraint("travel_mode IN ('day_trip','weekend','trip','camper')", name="ck_rider_profiles_travel_mode"),
        sa.CheckConstraint("availability <@ ARRAY[0,1,2,3,4,5,6]::smallint[]", name="ck_rider_profiles_availability"),
        sa.CheckConstraint("min_water_temp_c IS NULL OR (min_water_temp_c >= -5 AND min_water_temp_c <= 40)", name="ck_rider_profiles_water_temp"),
        sa.CheckConstraint("excluded_bottoms <@ ARRAY['sand','rock','reef','mixed']::varchar[]", name="ck_rider_profiles_excluded_bottoms"),
        sa.CheckConstraint("profile_version >= 1", name="ck_rider_profiles_version"),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("app_user_id"),
    )
    op.create_index("ix_rider_profiles_home_location", "rider_profiles", ["home_location"], postgresql_using="gist")

    op.create_table(
        "rider_sport_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("rider_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sport", sa.String(40), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("style_weights", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("preferred_water_character", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'::varchar[]"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sport IN ('kitesurf','windsurf','wing','surf')", name="ck_rider_sport_profiles_sport"),
        sa.CheckConstraint("level IN ('beginner','advanced','expert','competition')", name="ck_rider_sport_profiles_level"),
        sa.CheckConstraint("jsonb_typeof(style_weights) = 'object'", name="ck_rider_sport_profiles_style_weights"),
        sa.CheckConstraint("style_weights - ARRAY['freeride','freestyle','big_air','wave_riding','wavekite']::text[] = '{}'::jsonb", name="ck_rider_sport_profiles_style_keys"),
        sa.CheckConstraint("NOT jsonb_path_exists(style_weights, '$.* ? (@ != 0 && @ != 1 && @ != 2 && @ != 3)')", name="ck_rider_sport_profiles_style_values"),
        sa.CheckConstraint("preferred_water_character <@ ARRAY['flach','chop','welle_klein','welle_gross','tiefes_wasser']::varchar[]", name="ck_rider_sport_profiles_water_character"),
        sa.ForeignKeyConstraint(["rider_profile_id"], ["rider_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rider_profile_id", "sport", name="uq_rider_sport_profile"),
    )

    op.create_table(
        "gear_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("rider_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sport", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("size", sa.Numeric(6, 2)),
        sa.Column("board_type", sa.String(30)),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sport IN ('kitesurf','windsurf','wing','surf')", name="ck_gear_items_sport"),
        sa.CheckConstraint("kind IN ('kite','board','foil')", name="ck_gear_items_kind"),
        sa.CheckConstraint("size IS NULL OR size > 0", name="ck_gear_items_size"),
        sa.CheckConstraint("kind <> 'kite' OR size IS NOT NULL", name="ck_gear_items_kite_size"),
        sa.CheckConstraint("board_type IS NULL OR board_type IN ('twintip','surfboard','foil','bigair_twintip')", name="ck_gear_items_board_type"),
        sa.CheckConstraint("sort_order >= 0", name="ck_gear_items_sort_order"),
        sa.ForeignKeyConstraint(["rider_profile_id"], ["rider_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gear_items_profile_sport", "gear_items", ["rider_profile_id", "sport", "sort_order"])

    op.create_table(
        "user_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("app_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("anon_id", sa.String(64)),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True)),
        sa.Column("surface", sa.String(40)),
        sa.Column("context", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("(app_user_id IS NOT NULL) <> (anon_id IS NOT NULL)", name="ck_user_events_one_actor"),
        sa.CheckConstraint("type IN ('impression','click','favorite_add','favorite_remove','dismiss','search','session_checkin','notification_sent','notification_opened','notification_dismissed')", name="ck_user_events_type"),
        sa.CheckConstraint("jsonb_typeof(context) = 'object'", name="ck_user_events_context"),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_events_type_created", "user_events", ["type", "created_at"])
    op.create_index("ix_user_events_spot_created", "user_events", ["spot_id", "created_at"])
    op.create_index("ix_user_events_account", "user_events", ["app_user_id"])

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT sport, params FROM scoring_params WHERE version = 2")).mappings().all()
    for row in rows:
        params = deepcopy(row["params"])
        if row["sport"] == "kitesurf":
            params["rider_model"] = {"kitesurf": deepcopy(RIDER_MODEL)}
            params["default_rider"] = {"kitesurf": deepcopy(DEFAULT_RIDER)}
        bind.execute(
            sa.text("""
                INSERT INTO scoring_params (sport, version, active, params)
                VALUES (:sport, 3, false, CAST(:params AS jsonb))
                ON CONFLICT (sport, version) DO NOTHING
            """),
            {"sport": row["sport"], "params": __import__("json").dumps(params)},
        )
    bind.execute(sa.text("UPDATE scoring_params SET active = false"))
    bind.execute(sa.text("UPDATE scoring_params SET active = true WHERE version = 3"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM scoring_params WHERE version = 3"))
    bind.execute(sa.text("UPDATE scoring_params SET active = (version = 2)"))

    op.drop_index("ix_user_events_account", table_name="user_events")
    op.drop_index("ix_user_events_spot_created", table_name="user_events")
    op.drop_index("ix_user_events_type_created", table_name="user_events")
    op.drop_table("user_events")
    op.drop_index("ix_gear_items_profile_sport", table_name="gear_items")
    op.drop_table("gear_items")
    op.drop_table("rider_sport_profiles")
    op.drop_index("ix_rider_profiles_home_location", table_name="rider_profiles")
    op.drop_table("rider_profiles")
