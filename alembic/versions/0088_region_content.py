"""Region translations and content provenance.

Revision ID: 0088_region_content
Revises: 0087_content_governance
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0088_region_content"
down_revision = "0087_content_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regions", sa.Column("description_en", sa.Text(), nullable=True))
    op.add_column("regions", sa.Column("content_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("regions", sa.Column("content_status", sa.String(length=20), server_default=sa.text("'unreviewed'"), nullable=False))
    op.add_column("regions", sa.Column("content_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("regions", sa.Column("content_reviewed_by", sa.String(length=200), nullable=True))
    op.create_check_constraint(
        "ck_regions_content_status", "regions",
        "content_status IN ('unreviewed', 'in_review', 'verified', 'review_due', 'conflict')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_regions_content_status", "regions", type_="check")
    op.drop_column("regions", "content_reviewed_by")
    op.drop_column("regions", "content_reviewed_at")
    op.drop_column("regions", "content_status")
    op.drop_column("regions", "content_sources")
    op.drop_column("regions", "description_en")
