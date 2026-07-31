"""team note priority (normal | important)

Revision ID: 0016_team_note_priority
Revises: 0015_region_status
Create Date: 2026-07-31

Team notes on the admin overview board gain a priority. "important" notes get a
red stroke and sort to the top; existing rows default to "normal".
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_team_note_priority"
down_revision: Union[str, None] = "0015_region_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_notes",
        sa.Column(
            "priority",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("team_notes", "priority")
