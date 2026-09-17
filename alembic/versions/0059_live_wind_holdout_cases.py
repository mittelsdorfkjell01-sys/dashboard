"""Persist immutable LiveWind shadow holdout cases.

Revision ID: 0059_live_wind_holdout_cases
Revises: 0058_exact_dataset_identity
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0059_live_wind_holdout_cases"
down_revision: Union[str, None] = "0058_exact_dataset_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weather_live_wind_holdout_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("candidate_version", sa.String(80), nullable=False),
        sa.Column("target_station_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_stations.id"), nullable=False),
        sa.Column("target_observation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_observations.id"), nullable=False),
        sa.Column("shadow_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("weather_live_wind_jobs.id"), nullable=False),
        sa.Column("analysis_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dataset_bundle_hash", sa.String(64)),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("eligibility_status", sa.String(24), nullable=False),
        sa.Column("exclusion_reasons", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "eligibility_status IN ('eligible','not_activation_eligible')",
            name="ck_live_wind_holdout_eligibility",
        ),
        sa.UniqueConstraint(
            "candidate_version", "target_observation_id", "analysis_cutoff_at", "input_hash",
            name="uq_live_wind_holdout_case_version",
        ),
    )
    op.create_index(
        "ix_live_wind_holdout_candidate_time", "weather_live_wind_holdout_cases",
        ["candidate_version", "analysis_cutoff_at"],
    )
    op.create_index(
        "ix_live_wind_holdout_eligibility", "weather_live_wind_holdout_cases",
        ["candidate_version", "eligibility_status"],
    )
    op.execute("""
        CREATE FUNCTION reject_live_wind_holdout_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'LiveWind holdout cases are immutable';
        END $$
    """)
    op.execute("""
        CREATE TRIGGER immutable_live_wind_holdout_case
        BEFORE UPDATE OR DELETE ON weather_live_wind_holdout_cases
        FOR EACH ROW EXECUTE FUNCTION reject_live_wind_holdout_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER immutable_live_wind_holdout_case ON weather_live_wind_holdout_cases")
    op.execute("DROP FUNCTION reject_live_wind_holdout_mutation()")
    op.drop_index("ix_live_wind_holdout_eligibility", table_name="weather_live_wind_holdout_cases")
    op.drop_index("ix_live_wind_holdout_candidate_time", table_name="weather_live_wind_holdout_cases")
    op.drop_table("weather_live_wind_holdout_cases")
