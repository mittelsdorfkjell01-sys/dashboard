"""add field-level spot content governance

Revision ID: 0087_content_governance
Revises: 0086_spot_safety_notices
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0087_content_governance"
down_revision = "0086_spot_safety_notices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spots",
        sa.Column(
            "content_status",
            sa.String(length=20),
            server_default=sa.text("'unreviewed'"),
            nullable=False,
        ),
    )
    op.add_column("spots", sa.Column("content_reviewed_at", sa.DateTime(timezone=True)))
    op.add_column("spots", sa.Column("content_reviewed_by", sa.String(length=120)))
    op.add_column("spots", sa.Column("content_review_due_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_spots_content_status",
        "spots",
        "content_status IN ('unreviewed', 'in_review', 'verified', 'review_due', 'conflict')",
    )
    op.create_index("ix_spots_content_status", "spots", ["content_status"])

    op.create_table(
        "spot_content_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_path", sa.String(length=160), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("publisher", sa.String(length=200)),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "verification_status",
            sa.String(length=20),
            server_default=sa.text("'unreviewed'"),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=1000)),
        sa.Column("created_by", sa.String(length=120)),
        sa.Column("reviewed_by", sa.String(length=120)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "verification_status IN ('unreviewed', 'verified', 'rejected', 'conflict')",
            name="ck_spot_content_sources_verification_status",
        ),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "spot_id", "field_path", "url", name="uq_spot_content_sources_field_url"
        ),
    )
    op.create_index(
        "ix_spot_content_sources_spot_field",
        "spot_content_sources",
        ["spot_id", "field_path"],
    )
    op.create_index(
        "ix_spot_content_sources_status",
        "spot_content_sources",
        ["verification_status"],
    )


def downgrade() -> None:
    op.drop_table("spot_content_sources")
    op.drop_index("ix_spots_content_status", table_name="spots")
    op.drop_constraint("ck_spots_content_status", "spots", type_="check")
    op.drop_column("spots", "content_review_due_at")
    op.drop_column("spots", "content_reviewed_by")
    op.drop_column("spots", "content_reviewed_at")
    op.drop_column("spots", "content_status")
