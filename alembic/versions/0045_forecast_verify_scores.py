"""add forecast verification scores (WP1 validation harness)

Revision ID: 0045_forecast_verify_scores
Revises: 0044_media_gc_queue
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0045_forecast_verify_scores"
down_revision: Union[str, None] = "0044_media_gc_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_verification_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", sa.String(80), nullable=False),
        sa.Column("variant", sa.String(16), server_default="raw", nullable=False),
        sa.Column("lead_bucket", sa.String(12), nullable=False),
        sa.Column("direction_sector", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("bias_ms", sa.Float(), nullable=False),
        sa.Column("mae_ms", sa.Float(), nullable=False),
        sa.Column("rmse_ms", sa.Float(), nullable=False),
        sa.Column("direction_mae_deg", sa.Float()),
        sa.Column("window_start", sa.DateTime(timezone=True)),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("direction_sector >= 0 AND direction_sector < 12", name="ck_forecast_verification_sector"),
        sa.CheckConstraint("sample_count >= 0", name="ck_forecast_verification_samples"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "spot_id", "model_id", "variant", "lead_bucket", "direction_sector",
                            name="uq_forecast_verification_score"),
    )
    op.create_index("ix_forecast_verification_spot_run", "forecast_verification_scores", ["spot_id", "computed_at"])
    op.create_index("ix_forecast_verification_run", "forecast_verification_scores", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_forecast_verification_run", table_name="forecast_verification_scores")
    op.drop_index("ix_forecast_verification_spot_run", table_name="forecast_verification_scores")
    op.drop_table("forecast_verification_scores")
