"""phase 2 shadow geoprofiles and sectors

Revision ID: 0034_geodata_shadow_phase2
Revises: 0033_geodata_phase1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0034_geodata_shadow_phase2"
down_revision = "0033_geodata_phase1"
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
        "spot_geo_shadow_profiles",
        _id(),
        sa.Column(
            "spot_id",
            UUID,
            sa.ForeignKey("spots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("algorithm_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("profile_class", sa.String(1), nullable=False),
        sa.Column(
            "active_shadow",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("analysis", JSON, nullable=False),
        sa.Column(
            "metrics", JSON, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "warnings", JSON, server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        *_stamps(),
        sa.UniqueConstraint("spot_id", "input_hash", name="uq_spot_geo_shadow_input"),
        sa.CheckConstraint(
            "profile_class IN ('A','B','C','D')", name="ck_geo_shadow_class"
        ),
        sa.CheckConstraint(
            "status IN ('ready','blocked_credentials','blocked_license','blocked_quota','blocked_budget','failed')",
            name="ck_geo_shadow_status",
        ),
    )
    op.create_index(
        "ix_geo_shadow_active", "spot_geo_shadow_profiles", ["spot_id", "active_shadow"]
    )
    op.create_table(
        "spot_geo_shadow_sectors",
        _id(),
        sa.Column(
            "shadow_profile_id",
            UUID,
            sa.ForeignKey("spot_geo_shadow_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sector_index", sa.Integer(), nullable=False),
        sa.Column("center_deg", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("features", JSON, nullable=False),
        sa.Column("quality", JSON, nullable=False),
        *_stamps(),
        sa.UniqueConstraint(
            "shadow_profile_id", "sector_index", name="uq_geo_shadow_sector"
        ),
        sa.CheckConstraint(
            "sector_index >= 0 AND sector_index < 16", name="ck_geo_shadow_sector_index"
        ),
        sa.CheckConstraint(
            "status IN ('valid','degraded','unavailable','conflicted','not_applicable')",
            name="ck_geo_shadow_sector_status",
        ),
    )
    op.create_index(
        "ix_geo_shadow_sector_profile",
        "spot_geo_shadow_sectors",
        ["shadow_profile_id", "sector_index"],
    )


def downgrade():
    op.drop_table("spot_geo_shadow_sectors")
    op.drop_table("spot_geo_shadow_profiles")
