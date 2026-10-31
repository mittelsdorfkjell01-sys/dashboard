"""Record Europe measurement campaign scheduler evidence.

Revision ID: 0094_campaign_run_evidence
Revises: 0093_trip_planner_v2
"""

from alembic import op


revision = "0094_campaign_run_evidence"
down_revision = "0093_trip_planner_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_station_cycle_job_type",
        "weather_station_capture_cycles",
        type_="check",
    )
    op.create_check_constraint(
        "ck_station_cycle_job_type",
        "weather_station_capture_cycles",
        "job_type IN ('observations','catalog','campaign')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_station_cycle_job_type",
        "weather_station_capture_cycles",
        type_="check",
    )
    op.create_check_constraint(
        "ck_station_cycle_job_type",
        "weather_station_capture_cycles",
        "job_type IN ('observations','catalog')",
    )
