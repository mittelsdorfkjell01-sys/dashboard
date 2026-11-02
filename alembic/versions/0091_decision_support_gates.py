"""Scoped evidence for forecast decision support.

Revision ID: 0091_decision_support_gates
Revises: 0090_spot_visits
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0091_decision_support_gates"
down_revision = "0090_spot_visits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_support_gates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("data_kind", sa.String(16), nullable=False), sa.Column("sport", sa.String(24), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("horizon_bucket", sa.String(32), nullable=False),
        sa.Column("source_model", sa.String(120), nullable=False), sa.Column("status", sa.String(20), server_default=sa.text("'pending_review'"), nullable=False),
        sa.Column("artifact_uri", sa.String(500), nullable=False), sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("dataset_start", sa.Date(), nullable=False), sa.Column("dataset_end", sa.Date(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False), sa.Column("distinct_days", sa.Integer(), nullable=False),
        sa.Column("coverage_ratio", sa.Float(), nullable=False), sa.Column("quality_ratio", sa.Float(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False), sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("monitor_fresh_at", sa.DateTime(timezone=True), nullable=False), sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("data_kind IN ('wind','wave','tide')", name="ck_decision_gates_kind"),
        sa.CheckConstraint("status IN ('pending_review','accepted','rejected','expired')", name="ck_decision_gates_status"),
        sa.CheckConstraint("dataset_end >= dataset_start", name="ck_decision_gates_dataset_order"),
        sa.CheckConstraint("observation_count >= 0 AND distinct_days >= 0", name="ck_decision_gates_counts"),
        sa.CheckConstraint("coverage_ratio >= 0 AND coverage_ratio <= 1", name="ck_decision_gates_coverage"),
        sa.CheckConstraint("quality_ratio >= 0 AND quality_ratio <= 1", name="ck_decision_gates_quality"),
        sa.CheckConstraint("artifact_sha256 ~ '^[0-9a-f]{64}$'", name="ck_decision_gates_sha256"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decision_gates_scope", "decision_support_gates", ["data_kind", "sport", "region_id", "horizon_bucket", "status"])


def downgrade() -> None:
    op.drop_index("ix_decision_gates_scope", table_name="decision_support_gates")
    op.drop_table("decision_support_gates")
