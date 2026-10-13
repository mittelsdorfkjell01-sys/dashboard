"""add independent Europe wind measurement stations

Revision ID: 0078_europe_wind_campaign
Revises: 0077_weather_field_series_tiles
"""

from alembic import op
import sqlalchemy as sa


revision = "0078_europe_wind_campaign"
down_revision = "0077_weather_field_series_tiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("weather_stations", "spot_id", nullable=True)
    op.add_column(
        "weather_stations", sa.Column("campaign_key", sa.String(length=80))
    )
    op.create_check_constraint(
        "ck_weather_station_owner",
        "weather_stations",
        "spot_id IS NOT NULL OR campaign_key IS NOT NULL",
    )
    op.create_index(
        "uq_weather_station_campaign_provider",
        "weather_stations",
        ["campaign_key", "provider", "provider_station_id"],
        unique=True,
        postgresql_where=sa.text("campaign_key IS NOT NULL"),
    )
    op.create_index(
        "ix_weather_station_campaign_active",
        "weather_stations",
        ["campaign_key", "active"],
    )


def downgrade() -> None:
    op.drop_index("ix_weather_station_campaign_active", table_name="weather_stations")
    op.drop_index("uq_weather_station_campaign_provider", table_name="weather_stations")
    op.drop_constraint("ck_weather_station_owner", "weather_stations", type_="check")
    op.drop_column("weather_stations", "campaign_key")
    op.alter_column("weather_stations", "spot_id", nullable=False)
