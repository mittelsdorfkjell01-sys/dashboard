"""Persist compact exact-run point bundles for ephemeral capture jobs.

Revision ID: 0064_exact_model_points
Revises: 0063_spot_variant_conditions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0064_exact_model_points"
down_revision = "0063_spot_variant_conditions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_exact_model_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("target_kind", sa.String(16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("sampled_for_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_version", sa.String(64), nullable=False),
        sa.Column("loader_version", sa.String(64), nullable=False),
        sa.Column("bundle_hash", sa.String(64), nullable=False),
        sa.Column("bundle_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("dataset_bundle_hash", sa.String(64), nullable=False),
        sa.Column("dataset_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("activation_eligible", sa.Boolean(), nullable=False),
        sa.Column("member_statuses", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("target_kind", "target_id", "bundle_hash",
                            name="uq_weather_exact_bundle_target"),
        sa.CheckConstraint("target_kind IN ('station','spot')",
                           name="ck_weather_exact_bundle_target_kind"),
        sa.CheckConstraint(
            "latitude >= -90 AND latitude <= 90 AND longitude >= -180 AND longitude <= 180",
            name="ck_weather_exact_bundle_coordinate",
        ),
    )
    op.create_index(
        "ix_weather_exact_bundle_target_time", "weather_exact_model_bundles",
        ["target_kind", "target_id", "sampled_for_at"],
    )
    op.create_table(
        "weather_exact_model_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("bundle_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("weather_exact_model_bundles.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model_id", sa.String(80), nullable=False),
        sa.Column("dataset_version", sa.String(120)),
        sa.Column("model_run_id", sa.String(180), nullable=False),
        sa.Column("model_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_run_quality", sa.String(24), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("grid_distance_km", sa.Float(), nullable=False),
        sa.Column("u_ms", sa.Float(), nullable=False),
        sa.Column("v_ms", sa.Float(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("asset_hashes", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("asset_content_hashes", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("sample_hash", sa.String(64), nullable=False),
        sa.Column("sampling_version", sa.String(64), nullable=False),
        sa.Column("sampling_method", sa.String(40), nullable=False),
        sa.Column("source_cells", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("grid_definition", sa.Text()),
        sa.Column("model_height_m", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("bundle_id", "model_id", "valid_at",
                            name="uq_weather_exact_point_bundle_model_time"),
        sa.CheckConstraint("model_run_quality = 'exact'",
                           name="ck_weather_exact_point_run_quality"),
        sa.CheckConstraint(
            "grid_distance_km >= 0 AND abs(u_ms) <= 100 AND abs(v_ms) <= 100",
            name="ck_weather_exact_point_vector",
        ),
    )
    op.create_index(
        "ix_weather_exact_point_model_time", "weather_exact_model_points",
        ["model_id", "model_run_at", "valid_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_weather_exact_point_model_time",
                  table_name="weather_exact_model_points")
    op.drop_table("weather_exact_model_points")
    op.drop_index("ix_weather_exact_bundle_target_time",
                  table_name="weather_exact_model_bundles")
    op.drop_table("weather_exact_model_bundles")
