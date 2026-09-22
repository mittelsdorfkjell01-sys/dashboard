"""Verify public emails and persist account preferences.

Revision ID: 0065_account_experience
Revises: 0064_exact_model_points
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0065_account_experience"
down_revision = "0064_exact_model_points"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column("app_users", sa.Column("pending_email", sa.String(255)))
    op.add_column("app_users", sa.Column("email_token_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("app_users", sa.Column("preferences", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    # Existing users retain access; only newly registered accounts require verification.
    op.execute("UPDATE app_users SET email_verified_at = created_at")
    op.create_index("ix_app_users_pending_email", "app_users", ["pending_email"], unique=True)
    op.drop_constraint("ck_spot_submissions_status", "spot_submissions", type_="check")
    op.create_check_constraint(
        "ck_spot_submissions_status", "spot_submissions",
        "status IN ('pending', 'approved', 'rejected', 'merged', 'withdrawn')",
    )


def downgrade() -> None:
    op.execute("UPDATE spot_submissions SET status = 'rejected' WHERE status = 'withdrawn'")
    op.drop_constraint("ck_spot_submissions_status", "spot_submissions", type_="check")
    op.create_check_constraint(
        "ck_spot_submissions_status", "spot_submissions",
        "status IN ('pending', 'approved', 'rejected', 'merged')",
    )
    op.drop_index("ix_app_users_pending_email", table_name="app_users")
    op.drop_column("app_users", "preferences")
    op.drop_column("app_users", "email_token_version")
    op.drop_column("app_users", "pending_email")
    op.drop_column("app_users", "email_verified_at")
