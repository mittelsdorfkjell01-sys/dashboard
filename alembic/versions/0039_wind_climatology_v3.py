"""add shadow-only wind climatology v3 runs

Revision ID: 0039_wind_climatology_v3
Revises: 0038_wind_climatology_v2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0039_wind_climatology_v3"
down_revision = "0038_wind_climatology_v2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wind_climatology_v3_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("spots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cell_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wind_climatology_cells.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("start_year", sa.Integer(), nullable=False), sa.Column("end_year", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(40), nullable=False), sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("timezone", sa.String(64)), sa.Column("grid_lat", sa.Float()), sa.Column("grid_lon", sa.Float()),
        sa.Column("direction_windows", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("quality_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("variant_count", sa.Integer()), sa.Column("artifact_bytes", sa.Integer()),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_wind_clim_v3_spot_status", "wind_climatology_v3_runs", ["spot_id", "status"])
    op.create_index("uq_wind_clim_v3_active_spot", "wind_climatology_v3_runs", ["spot_id"], unique=True, postgresql_where=sa.text("is_active"))
    op.create_index("uq_wind_clim_v3_inflight_config", "wind_climatology_v3_runs", ["spot_id", "config_hash"], unique=True, postgresql_where=sa.text("status IN ('pending','processing')"))
    op.create_table(
        "wind_climatology_v3_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wind_climatology_v3_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("min_wind_kn", sa.Integer(), nullable=False), sa.Column("max_wind_kn", sa.Integer()),
        sa.Column("direction_mode", sa.String(12), nullable=False), sa.Column("payload_blob", sa.LargeBinary(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("payload_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("uq_wind_clim_v3_variant", "wind_climatology_v3_variants", ["run_id", "min_wind_kn", "max_wind_kn", "direction_mode"], unique=True, postgresql_nulls_not_distinct=True)
    op.create_index("ix_wind_clim_v3_variant_lookup", "wind_climatology_v3_variants", ["run_id", "direction_mode", "min_wind_kn", "max_wind_kn"])


def downgrade():
    op.drop_table("wind_climatology_v3_variants")
    op.drop_table("wind_climatology_v3_runs")
