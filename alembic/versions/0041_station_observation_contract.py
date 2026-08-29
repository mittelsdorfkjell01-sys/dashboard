"""station approval and normalized observation metadata

Revision ID: 0041_station_observation_contract
Revises: 0040_backfill_image_fields
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0041_station_observations"
down_revision = "0040_backfill_image_fields"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("elevation_m", "elevation_difference_m"):
        op.add_column("weather_stations", sa.Column(name, sa.Float()))
    op.add_column("weather_stations", sa.Column("setting_class", sa.String(20), nullable=False, server_default="unknown"))
    op.add_column("weather_stations", sa.Column("exposure_status", sa.String(24), nullable=False, server_default="unknown"))
    op.add_column("weather_stations", sa.Column("representativeness_status", sa.String(24), nullable=False, server_default="unreviewed"))
    for name in ("recommended", "approved", "blocked"):
        op.add_column("weather_stations", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("weather_stations", sa.Column("decision_reason", sa.Text()))
    op.add_column("weather_stations", sa.Column("last_import_at", sa.DateTime(timezone=True)))
    op.add_column("weather_stations", sa.Column("last_observation_at", sa.DateTime(timezone=True)))
    op.add_column("weather_observations", sa.Column("provider_quality", sa.String(80)))
    op.add_column("weather_observations", sa.Column("fetched_at", sa.DateTime(timezone=True)))
    op.add_column("weather_observations", sa.Column("import_status", sa.String(24), nullable=False, server_default="accepted"))
    op.add_column("weather_observations", sa.Column("data_issues", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))


def downgrade():
    for name in ("data_issues", "import_status", "fetched_at", "provider_quality"):
        op.drop_column("weather_observations", name)
    for name in ("last_observation_at", "last_import_at", "decision_reason", "blocked", "approved", "recommended", "representativeness_status", "exposure_status", "setting_class", "elevation_difference_m", "elevation_m"):
        op.drop_column("weather_stations", name)
