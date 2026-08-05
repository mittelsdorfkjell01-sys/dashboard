"""add revocable session versions

Revision ID: 0021_session_versions
Revises: 0020_drop_tide_requirement
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_session_versions"
down_revision: Union[str, None] = "0020_drop_tide_requirement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("session_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "app_users",
        sa.Column("session_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("app_users", "session_version")
    op.drop_column("admin_users", "session_version")
