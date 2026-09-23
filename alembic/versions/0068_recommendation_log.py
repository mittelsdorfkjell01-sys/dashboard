"""internal recommendation component audit log

Revision ID: 0068_recommendation_log
Revises: 0067_rider_profiles_events
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0068_recommendation_log"
down_revision = "0067_rider_profiles_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("app_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("user_ref", sa.String(96), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surface", sa.String(24), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("components", postgresql.JSONB(), nullable=False),
        sa.Column("params_version", sa.Integer(), nullable=False),
        sa.Column("profile_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_ref", "spot_id", "surface", "window_start", name="uq_recommendation_log_window"),
    )
    op.create_index("ix_recommendation_log_user_created", "recommendation_log", ["app_user_id", "created_at"])
    op.create_index("ix_recommendation_log_surface_window", "recommendation_log", ["surface", "window_start"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_log_surface_window", table_name="recommendation_log")
    op.drop_index("ix_recommendation_log_user_created", table_name="recommendation_log")
    op.drop_table("recommendation_log")
