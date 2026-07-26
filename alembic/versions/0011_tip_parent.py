"""threaded replies: parent_id on local_tips

Revision ID: 0011_tip_parent
Revises: 0010_commons_images
Create Date: 2026-07-26

A reply is a local_tip that points at the comment it answers via a nullable
self-referential ``parent_id`` (top-level comments keep it NULL). CASCADE on
delete so removing a comment takes its replies with it.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0011_tip_parent"
down_revision: Union[str, None] = "0010_commons_images"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "local_tips",
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tip_parent",
        "local_tips",
        "local_tips",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_tip_parent", "local_tips", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_tip_parent", table_name="local_tips")
    op.drop_constraint("fk_tip_parent", "local_tips", type_="foreignkey")
    op.drop_column("local_tips", "parent_id")
