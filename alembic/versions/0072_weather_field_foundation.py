"""add weather-field control plane

Revision ID: 0072_weather_field_foundation
Revises: 0071_retention_indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0072_weather_field_foundation"
down_revision = "0071_retention_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_field_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("model_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("native_grid", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cadence_hours", sa.Integer(), nullable=False),
        sa.Column("forecast_step_hours", sa.Integer(), nullable=False),
        sa.Column("max_horizon_hours", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("licence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attribution", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active','disabled','blocked_license','retired')", name="ck_weather_field_model_status"),
        sa.CheckConstraint("cadence_hours > 0 AND forecast_step_hours > 0 AND max_horizon_hours >= forecast_step_hours", name="ck_weather_field_model_schedule"),
        sa.CheckConstraint("priority >= 0", name="ck_weather_field_model_priority"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key", "model_key", name="uq_weather_field_model"),
    )
    op.create_index("ix_weather_field_model_active", "weather_field_models", ["status", "priority"])

    op.create_table(
        "weather_field_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_key", sa.String(length=40), nullable=False),
        sa.Column("model_key", sa.String(length=80), nullable=False),
        sa.Column("model_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contract_version", sa.String(length=40), nullable=False),
        sa.Column("processing_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("native_grid", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("valid_times", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("bytes_downloaded", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('discovered','downloading','processing','quality_pending','ready','rejected','failed','expired')", name="ck_weather_field_run_status"),
        sa.CheckConstraint("bytes_downloaded >= 0", name="ck_weather_field_run_bytes"),
        sa.ForeignKeyConstraint(["model_id"], ["weather_field_models.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key", "model_key", "model_run_at", "processing_version", name="uq_weather_field_run_identity"),
    )
    op.create_index("ix_weather_field_run_latest", "weather_field_runs", ["model_id", "model_run_at"])

    op.create_table(
        "weather_field_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_type", sa.String(length=20), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("valid_time", sa.DateTime(timezone=True)),
        sa.Column("source_zoom", sa.Integer()),
        sa.Column("tile_x", sa.Integer()),
        sa.Column("tile_y", sa.Integer()),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("compression", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("asset_type IN ('manifest','asset_index','tile','metadata')", name="ck_weather_field_asset_type"),
        sa.CheckConstraint("status IN ('staged','verified','invalid','deleted')", name="ck_weather_field_asset_status"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_weather_field_asset_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_weather_field_asset_sha256"),
        sa.CheckConstraint("(asset_type <> 'tile') OR (valid_time IS NOT NULL AND source_zoom IS NOT NULL AND tile_x IS NOT NULL AND tile_y IS NOT NULL)", name="ck_weather_field_tile_coordinates"),
        sa.ForeignKeyConstraint(["run_id"], ["weather_field_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_weather_field_asset_object_key"),
    )
    op.create_index("ix_weather_field_asset_run_status", "weather_field_assets", ["run_id", "status"])
    op.create_index("ix_weather_field_asset_tile", "weather_field_assets", ["run_id", "valid_time", "source_zoom", "tile_x", "tile_y"])

    op.create_table(
        "weather_field_quality_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gate_key", sa.String(length=80), nullable=False),
        sa.Column("hard_gate", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["weather_field_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "gate_key", name="uq_weather_field_quality_gate"),
    )
    op.create_index("ix_weather_field_quality_run", "weather_field_quality_events", ["run_id", "hard_gate", "passed"])

    op.create_table(
        "weather_field_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scope_key", sa.String(length=80), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manifest_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("deactivated_at", sa.DateTime(timezone=True)),
        sa.Column("supersedes_publication_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor", sa.String(length=160)),
        sa.Column("reason", sa.Text()),
        sa.Column("generation", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('staged','active','superseded','rolled_back','rejected')", name="ck_weather_field_publication_status"),
        sa.CheckConstraint("generation >= 0", name="ck_weather_field_publication_generation"),
        sa.ForeignKeyConstraint(["manifest_asset_id"], ["weather_field_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["weather_field_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_publication_id"], ["weather_field_publications.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_weather_field_publication_active_scope", "weather_field_publications", ["scope_key"], unique=True, postgresql_where=sa.text("active IS TRUE"))
    op.create_index("ix_weather_field_publication_history", "weather_field_publications", ["scope_key", "generation"])


def downgrade() -> None:
    op.drop_index("ix_weather_field_publication_history", table_name="weather_field_publications")
    op.drop_index("uq_weather_field_publication_active_scope", table_name="weather_field_publications")
    op.drop_table("weather_field_publications")
    op.drop_index("ix_weather_field_quality_run", table_name="weather_field_quality_events")
    op.drop_table("weather_field_quality_events")
    op.drop_index("ix_weather_field_asset_tile", table_name="weather_field_assets")
    op.drop_index("ix_weather_field_asset_run_status", table_name="weather_field_assets")
    op.drop_table("weather_field_assets")
    op.drop_index("ix_weather_field_run_latest", table_name="weather_field_runs")
    op.drop_table("weather_field_runs")
    op.drop_index("ix_weather_field_model_active", table_name="weather_field_models")
    op.drop_table("weather_field_models")
