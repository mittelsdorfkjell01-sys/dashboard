"""Durable visited spots.

Revision ID: 0090_spot_visits
Revises: 0089_trip_planner
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0090_spot_visits"
down_revision = "0089_trip_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spot_visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("app_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visited_at", sa.Date(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("outcome IS NULL OR outcome IN ('worthwhile','neutral','not_worthwhile')", name="ck_spot_visits_outcome"),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("app_user_id", "spot_id", name="uq_spot_visits_user_spot"),
    )
    op.create_index("ix_spot_visits_user_date", "spot_visits", ["app_user_id", "visited_at"])


def downgrade() -> None:
    op.drop_index("ix_spot_visits_user_date", table_name="spot_visits")
    op.drop_table("spot_visits")
