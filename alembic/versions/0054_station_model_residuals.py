"""add reproducible station model-residual evidence

Revision ID: 0054_station_model_residuals
Revises: 0053_observation_import_state

Both tables are additive. Existing observations and forecasts are untouched.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0054_station_model_residuals"
down_revision: Union[str, None] = "0053_observation_import_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weather_station_physics_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "quality_tier",
            sa.String(length=24),
            server_default="coordinates",
            nullable=False,
        ),
        sa.Column("coastal_normal_deg", sa.Float()),
        sa.Column("physics_version", sa.String(length=80), nullable=False),
        sa.Column(
            "profile",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft','reviewed','retired')",
            name="ck_weather_station_physics_profile_status",
        ),
        sa.CheckConstraint(
            "version >= 1", name="ck_weather_station_physics_profile_version"
        ),
        sa.CheckConstraint(
            "coastal_normal_deg IS NULL OR "
            "(coastal_normal_deg >= 0 AND coastal_normal_deg < 360)",
            name="ck_weather_station_physics_profile_coastal_normal",
        ),
        sa.CheckConstraint(
            "NOT active OR (status = 'reviewed' AND reviewed_at IS NOT NULL)",
            name="ck_weather_station_physics_profile_active_reviewed",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["weather_stations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "station_id",
            "version",
            name="uq_weather_station_physics_profile_version",
        ),
    )
    op.create_index(
        "uq_weather_station_physics_profile_active",
        "weather_station_physics_profiles",
        ["station_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )

    op.create_table(
        "weather_station_model_residuals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("station_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("station_profile_id", postgresql.UUID(as_uuid=True)),
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("calculation_version", sa.String(length=64), nullable=False),
        sa.Column("baseline_version", sa.String(length=64), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "model_runs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "model_members",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "raw_model_vector",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "expected_station_vector",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "measurement_vector",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "residual_vector",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "gust_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("station_profile_version", sa.Integer()),
        sa.Column("physics_version", sa.String(length=80), nullable=False),
        sa.Column("physics_applied", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("model_member_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("representativeness_uncertainty", sa.String(length=48), nullable=False),
        sa.Column("qc_status", sa.String(length=16), nullable=False),
        sa.Column(
            "qc_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "qc_status IN ('accepted','degraded','rejected','unavailable')",
            name="ck_weather_station_model_residual_qc",
        ),
        sa.CheckConstraint(
            "model_member_count >= 0",
            name="ck_weather_station_model_residual_member_count",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["weather_stations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["weather_observations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["station_profile_id"],
            ["weather_station_physics_profiles.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_id",
            "analysis_id",
            "calculation_version",
            name="uq_weather_station_model_residual_evidence",
        ),
    )
    op.create_index(
        "ix_weather_station_model_residual_station_time",
        "weather_station_model_residuals",
        ["station_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weather_station_model_residual_station_time",
        table_name="weather_station_model_residuals",
    )
    op.drop_table("weather_station_model_residuals")
    op.drop_index(
        "uq_weather_station_physics_profile_active",
        table_name="weather_station_physics_profiles",
    )
    op.drop_table("weather_station_physics_profiles")
