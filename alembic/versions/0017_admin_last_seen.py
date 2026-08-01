"""admin presence heartbeat (last_seen_at)

Revision ID: 0017_admin_last_seen
Revises: 0016_team_note_priority
Create Date: 2026-08-01

Adds ``admin_users.last_seen_at`` — refreshed (throttled) on every authenticated
request so the user table can show a real online/offline indicator instead of
the account-active flag.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_admin_last_seen"
down_revision: Union[str, None] = "0016_team_note_priority"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("admin_users", "last_seen_at")
