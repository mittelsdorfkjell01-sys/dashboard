"""add retention-oriented operational indexes

Revision ID: 0071_retention_indexes
Revises: 0070_usable_wind_directions
"""

from alembic import op
import sqlalchemy as sa


revision = "0071_retention_indexes"
down_revision = "0070_usable_wind_directions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_weather_forecast_sample_valid_at",
        "weather_forecast_samples",
        ["valid_at"],
    )
    op.create_index(
        "ix_forecast_snapshot_inactive_generated",
        "forecast_snapshots",
        ["generated_at"],
        postgresql_where=sa.text("active IS FALSE"),
    )
    op.create_index(
        "ix_forecast_job_terminal_finished",
        "forecast_processing_jobs",
        ["finished_at"],
        postgresql_where=sa.text(
            "status IN ('succeeded','failed','superseded') AND finished_at IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_recommendation_log_created",
        "recommendation_log",
        ["created_at"],
    )
    op.create_index(
        "ix_live_wind_job_terminal_finished",
        "weather_live_wind_jobs",
        ["finished_at"],
        postgresql_where=sa.text(
            "status IN ('succeeded','failed') AND finished_at IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_wind_job_terminal_finished", table_name="weather_live_wind_jobs"
    )
    op.drop_index("ix_recommendation_log_created", table_name="recommendation_log")
    op.drop_index(
        "ix_forecast_job_terminal_finished", table_name="forecast_processing_jobs"
    )
    op.drop_index(
        "ix_forecast_snapshot_inactive_generated", table_name="forecast_snapshots"
    )
    op.drop_index(
        "ix_weather_forecast_sample_valid_at", table_name="weather_forecast_samples"
    )
