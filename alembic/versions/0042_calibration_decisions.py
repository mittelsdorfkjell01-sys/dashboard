"""audit-ready calibration decisions

Revision ID: 0042_calibration_decisions
Revises: 0041_station_observations
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0042_calibration_decisions"
down_revision = "0041_station_observations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("weather_model_calibrations", sa.Column(
        "decision_status", sa.String(24), nullable=False, server_default="legacy_active"))
    op.add_column("weather_model_calibrations", sa.Column("decision_version", sa.String(32)))
    op.add_column("weather_model_calibrations", sa.Column("decision_reason", sa.Text()))
    op.add_column("weather_model_calibrations", sa.Column("decision_metrics", postgresql.JSONB(), nullable=False,
                                                          server_default=sa.text("'{}'::jsonb")))
    op.add_column("weather_model_calibrations", sa.Column("decided_at", sa.DateTime(timezone=True)))


def downgrade():
    for name in ("decided_at", "decision_metrics", "decision_reason", "decision_version", "decision_status"):
        op.drop_column("weather_model_calibrations", name)
