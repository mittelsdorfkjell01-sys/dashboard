"""remove admin TOTP state

Revision ID: 0026_remove_admin_totp
Revises: 0025_tides
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_remove_admin_totp"
down_revision: Union[str, None] = "0025_tides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("admin_users", "totp_last_step")
    op.drop_column("admin_users", "totp_enabled_at")
    op.drop_column("admin_users", "totp_secret_encrypted")


def downgrade() -> None:
    op.add_column("admin_users", sa.Column("totp_secret_encrypted", sa.String(512)))
    op.add_column("admin_users", sa.Column("totp_enabled_at", sa.DateTime(timezone=True)))
    op.add_column("admin_users", sa.Column("totp_last_step", sa.Integer()))
