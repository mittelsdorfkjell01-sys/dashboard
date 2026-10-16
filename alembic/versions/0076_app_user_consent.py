"""record registration consent on app_users

Adds nullable columns that capture the consent declared at registration: the
accepted terms version and timestamp, and the self-declared minimum-age (DSGVO
Art. 8) confirmation timestamp. Nullable and additive so existing accounts stay
valid without a back-filled claim of consent.

Revision ID: 0076_app_user_consent
Revises: 0075_activate_d2_global_gfs
"""

from alembic import op
import sqlalchemy as sa


revision = "0076_app_user_consent"
down_revision = "0075_activate_d2_global_gfs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_users", sa.Column("terms_accepted_version", sa.String(length=32), nullable=True))
    op.add_column("app_users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("app_users", sa.Column("age_confirmed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("app_users", "age_confirmed_at")
    op.drop_column("app_users", "terms_accepted_at")
    op.drop_column("app_users", "terms_accepted_version")
