"""authenticated upvotes for community comments

Revision ID: 0031_community_upvotes
Revises: 0030_weather_verification
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_community_upvotes"
down_revision: Union[str, None] = "0030_weather_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "community_upvotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tip_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rating_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("app_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(tip_id IS NOT NULL)::int + (rating_id IS NOT NULL)::int = 1",
            name="ck_community_upvote_one_target",
        ),
        sa.ForeignKeyConstraint(["tip_id"], ["local_tips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rating_id"], ["spot_ratings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_community_upvote_tip_user", "community_upvotes", ["tip_id", "app_user_id"],
        unique=True, postgresql_where=sa.text("tip_id IS NOT NULL"),
    )
    op.create_index(
        "uq_community_upvote_rating_user", "community_upvotes", ["rating_id", "app_user_id"],
        unique=True, postgresql_where=sa.text("rating_id IS NOT NULL"),
    )
    op.create_index("ix_community_upvote_user", "community_upvotes", ["app_user_id"])


def downgrade() -> None:
    op.drop_index("ix_community_upvote_user", table_name="community_upvotes")
    op.drop_index("uq_community_upvote_rating_user", table_name="community_upvotes")
    op.drop_index("uq_community_upvote_tip_user", table_name="community_upvotes")
    op.drop_table("community_upvotes")
