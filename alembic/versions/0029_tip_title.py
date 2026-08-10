"""optional title for public comments

Revision ID: 0029_tip_title
Revises: 0028_weather_profiles
"""

from alembic import op
import sqlalchemy as sa

revision = "0029_tip_title"
down_revision = "0028_weather_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("local_tips", sa.Column("title", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("local_tips", "title")
