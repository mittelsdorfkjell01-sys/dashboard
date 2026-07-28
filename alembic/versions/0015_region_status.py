"""region publish status (draft | published)

Revision ID: 0015_region_status
Revises: 0014_spot_region_nullable
Create Date: 2026-07-29

Regions get a draft/published status so operators can prepare a region before it
shows publicly. Existing rows default to 'published' (stay live); new regions are
created as 'draft'. Public listings filter to published; admin sees all.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_region_status"
down_revision: Union[str, None] = "0014_spot_region_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "regions",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("regions", "status")
