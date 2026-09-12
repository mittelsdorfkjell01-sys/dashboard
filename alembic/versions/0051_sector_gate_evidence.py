"""add statistically independent sector gate evidence

Revision ID: 0051_sector_gate_evidence
Revises: 0050_verification_gate_context
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0051_sector_gate_evidence"
down_revision: Union[str, None] = "0050_verification_gate_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_sector_gate_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_version", sa.Integer(), nullable=False),
        sa.Column("gate_context_hash", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matched_forecasts", sa.Integer(), nullable=False),
        sa.Column("unique_valid_times", sa.Integer(), nullable=False),
        sa.Column("distinct_days", sa.Integer(), nullable=False),
        sa.Column("baseline_mae_ms", sa.Float(), nullable=True),
        sa.Column("candidate_mae_ms", sa.Float(), nullable=True),
        sa.Column("mae_drop_ms", sa.Float(), nullable=True),
        sa.Column("ci_lower_ms", sa.Float(), nullable=True),
        sa.Column("ci_upper_ms", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column(
            "policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "candidate_version >= 1", name="ck_forecast_sector_gate_version"
        ),
        sa.CheckConstraint(
            "matched_forecasts >= 0 AND unique_valid_times >= 0 AND distinct_days >= 0",
            name="ck_forecast_sector_gate_counts",
        ),
        sa.CheckConstraint(
            "status IN ('collecting','rejected','passed')",
            name="ck_forecast_sector_gate_status",
        ),
        sa.ForeignKeyConstraint(["spot_id"], ["spots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "spot_id", name="uq_forecast_sector_gate_evidence_run_spot"
        ),
    )
    op.create_index(
        "ix_forecast_sector_gate_candidate",
        "forecast_sector_gate_evidence",
        ["spot_id", "candidate_version", "computed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_forecast_sector_gate_candidate",
        table_name="forecast_sector_gate_evidence",
    )
    op.drop_table("forecast_sector_gate_evidence")
