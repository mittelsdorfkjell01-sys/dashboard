"""Add immutable exact-run provenance gate to station residual evidence.

Revision ID: 0057_exact_run_baseline
Revises: 0056_live_wind_verification
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0057_exact_run_baseline"
down_revision: Union[str, None] = "0056_live_wind_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("weather_station_model_residuals", sa.Column("baseline_bundle_hash", sa.String(64), nullable=True))
    op.add_column("weather_station_model_residuals", sa.Column(
        "activation_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")
    ))
    op.create_index(
        "ix_weather_station_residual_exact_bundle",
        "weather_station_model_residuals",
        ["baseline_bundle_hash", "observed_at"],
        postgresql_where=sa.text("activation_eligible = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_weather_station_residual_exact_bundle", table_name="weather_station_model_residuals")
    op.drop_column("weather_station_model_residuals", "activation_eligible")
    op.drop_column("weather_station_model_residuals", "baseline_bundle_hash")
