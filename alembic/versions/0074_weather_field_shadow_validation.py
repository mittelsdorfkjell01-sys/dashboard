"""add weather-field shadow validation evidence

Revision ID: 0074_field_shadow_validation
Revises: 0073_weather_field_jobs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0074_field_shadow_validation"
down_revision = "0073_weather_field_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_weather_field_job_kind", "weather_field_jobs", type_="check"
    )
    op.create_check_constraint(
        "ck_weather_field_job_kind",
        "weather_field_jobs",
        "kind IN ('discover','process','retention','shadow_validate')",
    )
    op.create_table(
        "weather_field_shadow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('processing','succeeded','no_data','failed')", name="ck_weather_field_shadow_run_status"),
        sa.ForeignKeyConstraint(["job_id"], ["weather_field_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["publication_id"], ["weather_field_publications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["field_run_id"], ["weather_field_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_weather_field_shadow_run_publication", "weather_field_shadow_runs", ["publication_id", "created_at"])
    op.create_table(
        "weather_field_shadow_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("shadow_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_hours", sa.Integer(), nullable=False),
        sa.Column("field_lead_hours", sa.Integer(), nullable=False),
        sa.Column("horizon_bucket", sa.String(length=24), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("legacy_u_ms", sa.Float()),
        sa.Column("legacy_v_ms", sa.Float()),
        sa.Column("legacy_speed_ms", sa.Float(), nullable=False),
        sa.Column("legacy_direction_deg", sa.Float()),
        sa.Column("legacy_gust_ms", sa.Float()),
        sa.Column("field_u_ms", sa.Float(), nullable=False),
        sa.Column("field_v_ms", sa.Float(), nullable=False),
        sa.Column("field_speed_ms", sa.Float(), nullable=False),
        sa.Column("field_direction_deg", sa.Float()),
        sa.Column("field_gust_ms", sa.Float()),
        sa.Column("speed_delta_ms", sa.Float(), nullable=False),
        sa.Column("direction_delta_deg", sa.Float()),
        sa.Column("gust_delta_ms", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("lead_hours >= 0", name="ck_weather_field_shadow_lead"),
        sa.CheckConstraint("field_lead_hours >= 0", name="ck_weather_field_shadow_field_lead"),
        sa.ForeignKeyConstraint(["shadow_run_id"], ["weather_field_shadow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["forecast_snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shadow_run_id", "spot_id", "snapshot_id", "valid_at", name="uq_weather_field_shadow_sample"),
    )
    op.create_index("ix_weather_field_shadow_sample_dimensions", "weather_field_shadow_samples", ["shadow_run_id", "horizon_bucket"])
    op.create_index("ix_weather_field_shadow_sample_spot", "weather_field_shadow_samples", ["spot_id", "valid_at"])
    op.create_table(
        "weather_field_shadow_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("shadow_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension_hash", sa.String(length=64), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sample_count > 0", name="ck_weather_field_shadow_metric_samples"),
        sa.ForeignKeyConstraint(["shadow_run_id"], ["weather_field_shadow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shadow_run_id", "dimension_hash", name="uq_weather_field_shadow_metric_dimension"),
    )
    op.create_index("ix_weather_field_shadow_metric_run", "weather_field_shadow_metrics", ["shadow_run_id"])


def downgrade() -> None:
    op.drop_index("ix_weather_field_shadow_metric_run", table_name="weather_field_shadow_metrics")
    op.drop_table("weather_field_shadow_metrics")
    op.drop_index("ix_weather_field_shadow_sample_spot", table_name="weather_field_shadow_samples")
    op.drop_index("ix_weather_field_shadow_sample_dimensions", table_name="weather_field_shadow_samples")
    op.drop_table("weather_field_shadow_samples")
    op.drop_index("ix_weather_field_shadow_run_publication", table_name="weather_field_shadow_runs")
    op.drop_table("weather_field_shadow_runs")
    # Shadow jobs have no meaning once their evidence tables are removed and
    # cannot satisfy the previous revision's narrower kind constraint.
    op.execute("DELETE FROM weather_field_jobs WHERE kind = 'shadow_validate'")
    op.drop_constraint("ck_weather_field_job_kind", "weather_field_jobs", type_="check")
    op.create_check_constraint(
        "ck_weather_field_job_kind",
        "weather_field_jobs",
        "kind IN ('discover','process','retention')",
    )
