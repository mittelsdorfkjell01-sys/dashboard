"""add immutable multi-time weather-field series tiles

Revision ID: 0077_weather_field_series_tiles
Revises: 0076_app_user_consent
"""

from alembic import op


revision = "0077_weather_field_series_tiles"
down_revision = "0076_app_user_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_weather_field_asset_type", "weather_field_assets", type_="check"
    )
    op.create_check_constraint(
        "ck_weather_field_asset_type",
        "weather_field_assets",
        "asset_type IN ('manifest','asset_index','tile','series_tile','metadata')",
    )
    op.create_check_constraint(
        "ck_weather_field_series_tile_coordinates",
        "weather_field_assets",
        "(asset_type <> 'series_tile') OR "
        "(valid_time IS NULL AND source_zoom IS NOT NULL "
        "AND tile_x IS NOT NULL AND tile_y IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_weather_field_series_tile_coordinates",
        "weather_field_assets",
        type_="check",
    )
    op.drop_constraint(
        "ck_weather_field_asset_type", "weather_field_assets", type_="check"
    )
    op.create_check_constraint(
        "ck_weather_field_asset_type",
        "weather_field_assets",
        "asset_type IN ('manifest','asset_index','tile','metadata')",
    )
