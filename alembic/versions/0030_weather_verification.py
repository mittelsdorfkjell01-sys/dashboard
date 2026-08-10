"""add weather observations, forecast samples and calibration

Revision ID: 0030_weather_verification
Revises: 0029_tip_title
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_weather_verification"
down_revision: Union[str, None] = "0029_tip_title"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "weather_stations", _id(),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_station_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160)), sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False), sa.Column("distance_km", sa.Float()),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_weather_station_lat"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_weather_station_lon"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spot_id", "provider", "provider_station_id", name="uq_weather_station_spot_provider"),
    )
    op.create_table(
        "weather_observations", _id(),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wind_speed_ms", sa.Float(), nullable=False), sa.Column("wind_gust_ms", sa.Float()),
        sa.Column("wind_direction_deg", sa.Float()), sa.Column("quality", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("wind_speed_ms >= 0 AND wind_speed_ms <= 100", name="ck_weather_observation_speed"),
        sa.CheckConstraint("wind_direction_deg IS NULL OR (wind_direction_deg >= 0 AND wind_direction_deg < 360)", name="ck_weather_observation_dir"),
        sa.ForeignKeyConstraint(["station_id"], ["weather_stations.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("station_id", "observed_at", name="uq_weather_observation_time"),
    )
    op.create_table(
        "weather_forecast_samples", _id(),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("model_id", sa.String(80), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False), sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_hours", sa.Integer(), nullable=False), sa.Column("wind_speed_ms", sa.Float(), nullable=False),
        sa.Column("wind_gust_ms", sa.Float()), sa.Column("wind_direction_deg", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("lead_hours >= 0 AND lead_hours <= 300", name="ck_weather_sample_lead"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spot_id", "model_id", "issued_at", "valid_at", name="uq_weather_forecast_sample"),
    )
    op.create_table(
        "weather_model_calibrations", _id(),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("model_id", sa.String(80), nullable=False),
        sa.Column("lead_bucket", sa.String(12), nullable=False), sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("bias_ms", sa.Float(), nullable=False), sa.Column("mae_ms", sa.Float(), nullable=False),
        sa.Column("weight_multiplier", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sample_count >= 0", name="ck_weather_calibration_samples"),
        sa.CheckConstraint("weight_multiplier >= 0.5 AND weight_multiplier <= 2.0", name="ck_weather_calibration_weight"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spot_id", "model_id", "lead_bucket", name="uq_weather_calibration"),
    )
    op.create_index("ix_weather_observation_time", "weather_observations", ["observed_at"])
    op.create_index("ix_weather_sample_match", "weather_forecast_samples", ["spot_id", "valid_at", "model_id"])


def downgrade() -> None:
    op.drop_index("ix_weather_sample_match", table_name="weather_forecast_samples")
    op.drop_index("ix_weather_observation_time", table_name="weather_observations")
    op.drop_table("weather_model_calibrations")
    op.drop_table("weather_forecast_samples")
    op.drop_table("weather_observations")
    op.drop_table("weather_stations")
