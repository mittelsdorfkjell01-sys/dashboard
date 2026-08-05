"""add encrypted TOTP state for admin MFA

Revision ID: 0023_admin_totp
Revises: 0022_catalog_integrity
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_admin_totp"
down_revision: Union[str, None] = "0022_catalog_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_users", sa.Column("totp_secret_encrypted", sa.String(512)))
    op.add_column("admin_users", sa.Column("totp_enabled_at", sa.DateTime(timezone=True)))
    op.add_column("admin_users", sa.Column("totp_last_step", sa.Integer()))


def downgrade() -> None:
    op.drop_column("admin_users", "totp_last_step")
    op.drop_column("admin_users", "totp_enabled_at")
    op.drop_column("admin_users", "totp_secret_encrypted")
