"""Add immutable wave forecast verification evidence.

Revision ID: 0096_wave_verification
Revises: 0095_best_wind_directions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0096_wave_verification"
down_revision = "0095_best_wind_directions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wave_observation_platforms",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_key", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(160), nullable=False),
        sa.Column("name", sa.String(240)),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("region_code", sa.String(40), nullable=False),
        sa.Column("location_class", sa.String(24), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_wave_platform_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_wave_platform_longitude"),
        sa.CheckConstraint("location_class IN ('nearshore','shelf','offshore','unknown')", name="ck_wave_platform_location_class"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key", "external_id", name="uq_wave_platform_provider_external"),
    )
    op.create_index("ix_wave_platform_active_region", "wave_observation_platforms", ["active", "region_code"])

    op.create_table(
        "wave_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("platform_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("significant_height_m", sa.Float()),
        sa.Column("period_s", sa.Float()),
        sa.Column("period_semantic", sa.String(48)),
        sa.Column("direction_from_deg", sa.Float()),
        sa.Column("direction_semantic", sa.String(48)),
        sa.Column("qc_status", sa.String(24), nullable=False),
        sa.Column("source_revision", sa.String(120), nullable=False),
        sa.Column("source_file", sa.Text()),
        sa.Column("source_sha256", sa.String(64)),
        sa.Column("raw_values", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("significant_height_m IS NULL OR (significant_height_m >= 0 AND significant_height_m <= 40)", name="ck_wave_observation_height"),
        sa.CheckConstraint("period_s IS NULL OR (period_s > 0 AND period_s <= 40)", name="ck_wave_observation_period"),
        sa.CheckConstraint("direction_from_deg IS NULL OR (direction_from_deg >= 0 AND direction_from_deg < 360)", name="ck_wave_observation_direction"),
        sa.CheckConstraint("qc_status IN ('good','probably_good','interpolated','unknown','bad')", name="ck_wave_observation_qc"),
        sa.CheckConstraint("source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'", name="ck_wave_observation_sha256"),
        sa.ForeignKeyConstraint(["platform_id"], ["wave_observation_platforms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform_id", "observed_at", "source_revision", name="uq_wave_observation_identity"),
    )
    op.create_index("ix_wave_observation_platform_time", "wave_observations", ["platform_id", "observed_at"])
    op.create_index("ix_wave_observation_qc_time", "wave_observations", ["qc_status", "observed_at"])

    op.create_table(
        "wave_forecast_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("platform_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_key", sa.String(40), nullable=False),
        sa.Column("model_key", sa.String(80), nullable=False),
        sa.Column("model_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_hours", sa.Integer(), nullable=False),
        sa.Column("processing_version", sa.String(80), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("significant_height_m", sa.Float()),
        sa.Column("period_s", sa.Float()),
        sa.Column("period_semantic", sa.String(48)),
        sa.Column("direction_from_deg", sa.Float()),
        sa.Column("direction_semantic", sa.String(48)),
        sa.Column("interpolation", sa.String(40), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("lead_hours >= 0", name="ck_wave_forecast_sample_lead"),
        sa.CheckConstraint("significant_height_m IS NULL OR (significant_height_m >= 0 AND significant_height_m <= 40)", name="ck_wave_forecast_sample_height"),
        sa.CheckConstraint("period_s IS NULL OR (period_s > 0 AND period_s <= 40)", name="ck_wave_forecast_sample_period"),
        sa.CheckConstraint("direction_from_deg IS NULL OR (direction_from_deg >= 0 AND direction_from_deg < 360)", name="ck_wave_forecast_sample_direction"),
        sa.CheckConstraint("evidence_sha256 ~ '^[0-9a-f]{64}$'", name="ck_wave_forecast_sample_sha256"),
        sa.ForeignKeyConstraint(["field_run_id"], ["weather_field_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["platform_id"], ["wave_observation_platforms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform_id", "model_key", "model_run_at", "valid_at", "processing_version", name="uq_wave_forecast_sample_identity"),
    )
    op.create_index("ix_wave_forecast_sample_model_time", "wave_forecast_samples", ["model_key", "valid_at"])
    op.create_index("ix_wave_forecast_sample_platform_time", "wave_forecast_samples", ["platform_id", "valid_at"])

    op.create_table(
        "wave_verification_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("dataset_start", sa.Date(), nullable=False),
        sa.Column("dataset_end", sa.Date(), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("artifact_uri", sa.String(500), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('completed','failed')", name="ck_wave_verification_run_status"),
        sa.CheckConstraint("dataset_end >= dataset_start", name="ck_wave_verification_run_dates"),
        sa.CheckConstraint("artifact_sha256 ~ '^[0-9a-f]{64}$'", name="ck_wave_verification_run_sha256"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wave_verification_run_period", "wave_verification_runs", ["dataset_start", "dataset_end"])

    op.create_table(
        "wave_verification_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("verification_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_key", sa.String(80), nullable=False),
        sa.Column("parameter", sa.String(32), nullable=False),
        sa.Column("lead_bucket", sa.String(24), nullable=False),
        sa.Column("region_code", sa.String(40), nullable=False),
        sa.Column("location_class", sa.String(24), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("distinct_days", sa.Integer(), nullable=False),
        sa.Column("bias", sa.Float(), nullable=False),
        sa.Column("mae", sa.Float(), nullable=False),
        sa.Column("rmse", sa.Float(), nullable=False),
        sa.Column("correlation", sa.Float()),
        sa.Column("scatter_index", sa.Float()),
        sa.Column("within_tolerance_ratio", sa.Float()),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("parameter IN ('significant_height','period','direction')", name="ck_wave_verification_score_parameter"),
        sa.CheckConstraint("sample_count >= 0 AND distinct_days >= 0", name="ck_wave_verification_score_counts"),
        sa.CheckConstraint("within_tolerance_ratio IS NULL OR (within_tolerance_ratio >= 0 AND within_tolerance_ratio <= 1)", name="ck_wave_verification_score_tolerance"),
        sa.ForeignKeyConstraint(["verification_run_id"], ["wave_verification_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("verification_run_id", "model_key", "parameter", "lead_bucket", "region_code", "location_class", name="uq_wave_verification_score_scope"),
    )
    op.create_index("ix_wave_verification_score_lookup", "wave_verification_scores", ["model_key", "parameter", "lead_bucket", "region_code"])


def downgrade() -> None:
    op.drop_index("ix_wave_verification_score_lookup", table_name="wave_verification_scores")
    op.drop_table("wave_verification_scores")
    op.drop_index("ix_wave_verification_run_period", table_name="wave_verification_runs")
    op.drop_table("wave_verification_runs")
    op.drop_index("ix_wave_forecast_sample_platform_time", table_name="wave_forecast_samples")
    op.drop_index("ix_wave_forecast_sample_model_time", table_name="wave_forecast_samples")
    op.drop_table("wave_forecast_samples")
    op.drop_index("ix_wave_observation_qc_time", table_name="wave_observations")
    op.drop_index("ix_wave_observation_platform_time", table_name="wave_observations")
    op.drop_table("wave_observations")
    op.drop_index("ix_wave_platform_active_region", table_name="wave_observation_platforms")
    op.drop_table("wave_observation_platforms")
