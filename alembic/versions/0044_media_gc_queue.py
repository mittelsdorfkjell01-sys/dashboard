"""persistent race-safe media garbage collection

Revision ID: 0044_media_gc_queue
Revises: 0043_media_storage_optimization
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0044_media_gc_queue"
down_revision = "0043_media_storage_optimization"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "media_garbage_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("reference_url", sa.Text(), nullable=False),
        sa.Column(
            "delete_set", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_media_gc_due",
        "media_garbage_candidates",
        ["not_before", "created_at"],
    )
    op.create_table(
        "media_gc_state",
        sa.Column("backend", sa.String(20), primary_key=True),
        sa.Column("cursor", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("media_gc_state")
    op.drop_index("ix_media_gc_due", table_name="media_garbage_candidates")
    op.drop_table("media_garbage_candidates")
