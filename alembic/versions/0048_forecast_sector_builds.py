"""add forecast_sector_builds (producer runner state)

Revision ID: 0048_forecast_sector_builds
Revises: 0047_widen_sector_factor
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0048_forecast_sector_builds"
down_revision: Union[str, None] = "0047_widen_sector_factor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_sector_builds",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("producer", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(32)),
        sa.Column("version", sa.Integer()),
        sa.Column("built_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spot_id", "producer", name="uq_forecast_sector_build"),
    )
    op.create_index("ix_forecast_sector_build_cursor", "forecast_sector_builds", ["producer", "built_at"])


def downgrade() -> None:
    op.drop_index("ix_forecast_sector_build_cursor", table_name="forecast_sector_builds")
    op.drop_table("forecast_sector_builds")
