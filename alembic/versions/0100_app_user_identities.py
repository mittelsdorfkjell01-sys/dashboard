"""Sign in with Google or Apple: external identities linked to an account.

Revision ID: 0100_app_user_identities
Revises: 0099_tip_withdraw_token

One row per (provider, subject). The provider's subject id is what identifies
the person on later sign-ins; the email is kept for support only, because it
can change and Apple may hand out a relay address. Deleting the account deletes
its identities.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0100_app_user_identities"
down_revision = "0099_tip_withdraw_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "subject", name="uq_app_user_identities_provider_subject"),
    )
    op.create_index("ix_app_user_identities_user_id", "app_user_identities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_app_user_identities_user_id", table_name="app_user_identities")
    op.drop_table("app_user_identities")
