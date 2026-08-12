"""geodata catalogue and immutable raster inputs

Revision ID: 0033_geodata_phase1
Revises: 0032_forecast_system
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0033_geodata_phase1"
down_revision = "0032_forecast_system"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB


def _id():
    return sa.Column(
        "id", UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True
    )


def _stamps():
    return [
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
    ]


def upgrade():
    op.create_table(
        "geodata_datasets",
        _id(),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("product_instance", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("specification", JSON, nullable=False),
        sa.Column("licence", JSON, nullable=False),
        sa.Column("fallback_key", sa.String(80)),
        sa.Column("legal_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        *_stamps(),
        sa.UniqueConstraint("key", "version", name="uq_geodata_dataset_version"),
    )
    op.create_table(
        "geodata_assets",
        _id(),
        sa.Column(
            "dataset_id",
            UUID,
            sa.ForeignKey("geodata_datasets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("asset_key", sa.String(240), nullable=False),
        sa.Column("tile_id", sa.String(40)),
        sa.Column("bbox", JSON, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("file_type", sa.String(30), nullable=False),
        sa.Column("crs", sa.String(40), nullable=False),
        sa.Column("byte_range", sa.String(80)),
        sa.Column("size_bytes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata", JSON, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        *_stamps(),
        sa.UniqueConstraint(
            "dataset_id", "asset_key", "byte_range", name="uq_geodata_asset_window"
        ),
        sa.CheckConstraint(
            "status IN ('downloading','ready','invalid','evicted')",
            name="ck_geodata_asset_status",
        ),
    )
    op.create_index(
        "ix_geodata_asset_lru", "geodata_assets", ["status", "last_accessed_at"]
    )
    op.create_table(
        "spot_geo_profile_inputs",
        _id(),
        sa.Column(
            "profile_id",
            UUID,
            sa.ForeignKey("spot_geo_profile_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            UUID,
            sa.ForeignKey("geodata_assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column(
            "quality", JSON, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        *_stamps(),
        sa.UniqueConstraint(
            "profile_id", "asset_id", "role", name="uq_geo_profile_asset_role"
        ),
    )


def downgrade():
    op.drop_table("spot_geo_profile_inputs")
    op.drop_table("geodata_assets")
    op.drop_table("geodata_datasets")
