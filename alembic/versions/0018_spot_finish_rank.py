"""spot finish rank override (traffic light for "Fertigstellen")

Revision ID: 0018_spot_finish_rank
Revises: 0017_admin_last_seen
Create Date: 2026-08-01

Adds ``spots.finish_rank`` — an optional manual override (red|yellow|green) for
the "Fertigstellen" traffic-light rank. NULL means the rank is derived
automatically from the spot's readiness gaps.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_spot_finish_rank"
down_revision: Union[str, None] = "0017_admin_last_seen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "spots",
        sa.Column("finish_rank", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("spots", "finish_rank")
