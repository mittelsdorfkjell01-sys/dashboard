"""allow region-less spots: spots.region_id nullable

Revision ID: 0014_spot_region_nullable
Revises: 0013_drop_wind_dir_requirement
Create Date: 2026-07-29

A spot can be dragged out of every region and left unassigned — it then shows
at the top of the Übersicht (red) until a region is picked. So region_id drops
its NOT NULL. FK/ondelete unchanged (region delete is still guarded to no spots).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0014_spot_region_nullable"
down_revision: Union[str, None] = "0013_drop_wind_dir_requirement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "spots", "region_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "spots", "region_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
