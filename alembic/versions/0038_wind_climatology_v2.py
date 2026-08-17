"""wind climatology v2

Revision ID: 0038_wind_climatology_v2
Revises: 0037_wavekite_riding_style
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0038_wind_climatology_v2"
down_revision = "0037_wavekite_riding_style"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wind_climatology_cells",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("spots.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("selection_mode", sa.String(16), nullable=False, server_default="automatic"),
        sa.Column("spot_lat", sa.Float(), nullable=False), sa.Column("spot_lon", sa.Float(), nullable=False),
        sa.Column("requested_lat", sa.Float(), nullable=False), sa.Column("requested_lon", sa.Float(), nullable=False),
        sa.Column("actual_lat", sa.Float()), sa.Column("actual_lon", sa.Float()), sa.Column("distance_km", sa.Float()),
        sa.Column("model", sa.String(32), nullable=False, server_default="ERA5"),
        sa.Column("resolution_deg", sa.Float(), nullable=False, server_default="0.25"),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "wind_climatology_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("spots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cell_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wind_climatology_cells.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("start_year", sa.Integer(), nullable=False), sa.Column("end_year", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(120), nullable=False, server_default="Open-Meteo Historical Weather API"),
        sa.Column("model", sa.String(32), nullable=False, server_default="ERA5"),
        sa.Column("unit", sa.String(16), nullable=False, server_default="kn"), sa.Column("timezone", sa.String(64)),
        sa.Column("grid_lat", sa.Float()), sa.Column("grid_lon", sa.Float()),
        sa.Column("algorithm_version", sa.String(40), nullable=False), sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("annual_aggregates", postgresql.JSONB()), sa.Column("public_data", postgresql.JSONB()),
        sa.Column("quality_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_wind_clim_runs_spot_status", "wind_climatology_runs", ["spot_id", "status"])
    op.create_index("uq_wind_clim_active_spot", "wind_climatology_runs", ["spot_id"], unique=True, postgresql_where=sa.text("is_active"))
    op.create_index("uq_wind_clim_inflight_config", "wind_climatology_runs", ["spot_id", "config_hash"], unique=True, postgresql_where=sa.text("status IN ('pending','processing')"))


def downgrade():
    op.drop_table("wind_climatology_runs")
    op.drop_table("wind_climatology_cells")
