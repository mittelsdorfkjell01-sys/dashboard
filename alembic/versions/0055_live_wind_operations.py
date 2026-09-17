"""add durable shadow LiveWind jobs and observation retry scheduling

Revision ID: 0055_live_wind_operations
Revises: 0054_station_model_residuals

All changes are additive. Public product data, observations, and forecasts are
untouched; existing import states become immediately due (NULL next_attempt_at).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0055_live_wind_operations"
down_revision: Union[str, None] = "0054_station_model_residuals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "weather_observation_import_states",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_weather_observation_import_state_next_attempt",
        "weather_observation_import_states",
        ["next_attempt_at"],
    )

    op.create_table(
        "weather_live_wind_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=True)),
        sa.Column("region_key", sa.String(length=120), server_default="unassigned", nullable=False),
        sa.Column("terrain_class", sa.String(length=48), server_default="unknown", nullable=False),
        sa.Column("cycle_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rollout_stage", sa.String(length=16), nullable=False),
        sa.Column("analysis_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("worker_token", postgresql.UUID(as_uuid=True)),
        sa.Column("error_class", sa.String(length=120)),
        sa.Column("product_status", sa.String(length=24)),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)),
        sa.Column("valid_at", sa.DateTime(timezone=True)),
        sa.Column("station_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("correction_magnitude_ms", sa.Float()),
        sa.Column("conflict_index", sa.Float()),
        sa.Column("uncertainty_ms", sa.Float()),
        sa.Column("confidence", sa.Float()),
        sa.Column("fallback_reason", sa.String(length=160)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("baseline_cache_hit", sa.Boolean()),
        sa.Column(
            "exclusion_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "diagnostics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "rollout_stage IN ('shadow','internal','pilot','regional','global')",
            name="ck_weather_live_wind_job_rollout",
        ),
        sa.CheckConstraint(
            "status IN ('queued','processing','retry_wait','succeeded','failed')",
            name="ck_weather_live_wind_job_status",
        ),
        sa.CheckConstraint(
            "product_status IS NULL OR product_status IN ('baseline','station_adjusted','unavailable')",
            name="ck_weather_live_wind_job_product_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND station_count >= 0",
            name="ck_weather_live_wind_job_counts",
        ),
        sa.CheckConstraint(
            "conflict_index IS NULL OR (conflict_index >= 0 AND conflict_index <= 1)",
            name="ck_weather_live_wind_job_conflict",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_weather_live_wind_job_confidence",
        ),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "spot_id", "cycle_at", "analysis_version",
            name="uq_weather_live_wind_job_cycle",
        ),
    )
    op.create_index(
        "ix_weather_live_wind_jobs_claim",
        "weather_live_wind_jobs",
        ["status", "available_at", "created_at"],
    )
    op.create_index(
        "ix_weather_live_wind_jobs_spot_cycle",
        "weather_live_wind_jobs",
        ["spot_id", "cycle_at"],
    )
    op.create_index(
        "ix_weather_live_wind_jobs_region_cycle",
        "weather_live_wind_jobs",
        ["region_key", "cycle_at"],
    )
    op.create_index(
        "uq_weather_live_wind_jobs_active_spot",
        "weather_live_wind_jobs",
        ["spot_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','processing','retry_wait')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_weather_live_wind_jobs_active_spot",
        table_name="weather_live_wind_jobs",
    )
    op.drop_index(
        "ix_weather_live_wind_jobs_region_cycle",
        table_name="weather_live_wind_jobs",
    )
    op.drop_index(
        "ix_weather_live_wind_jobs_spot_cycle",
        table_name="weather_live_wind_jobs",
    )
    op.drop_index(
        "ix_weather_live_wind_jobs_claim",
        table_name="weather_live_wind_jobs",
    )
    op.drop_table("weather_live_wind_jobs")
    op.drop_index(
        "ix_weather_observation_import_state_next_attempt",
        table_name="weather_observation_import_states",
    )
    op.drop_column("weather_observation_import_states", "next_attempt_at")
