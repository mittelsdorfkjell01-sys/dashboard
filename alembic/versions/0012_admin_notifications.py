"""admin_notifications: operator-facing dashboard notifications

Revision ID: 0012_admin_notifications
Revises: 0011_tip_parent
Create Date: 2026-07-28

Operator notifications (new submission, reported image, flagged tip/rating).
Distinct from the community ``notifications`` (watch alerts) table. ``read_at``
NULL = unread.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0012_admin_notifications"
down_revision: Union[str, None] = "0011_tip_parent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_admin_notifications_unread",
        "admin_notifications",
        ["read_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_notifications_unread", table_name="admin_notifications")
    op.drop_table("admin_notifications")
