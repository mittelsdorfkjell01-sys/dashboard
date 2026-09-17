"""add immutable LiveWind holdout verification evidence

Revision ID: 0056_live_wind_verification
Revises: 0055_live_wind_operations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0056_live_wind_verification"
down_revision: Union[str, None] = "0055_live_wind_operations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weather_live_wind_verification_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_version", sa.String(length=80), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("training_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("matched_samples", sa.Integer(), nullable=False),
        sa.Column("distinct_stations", sa.Integer(), nullable=False),
        sa.Column("distinct_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("stratified_metrics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("policy", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('collecting','rejected','passed')", name="ck_live_wind_verification_status"),
        sa.CheckConstraint("matched_samples >= 0 AND distinct_stations >= 0 AND distinct_days >= 0", name="ck_live_wind_verification_counts"),
        sa.CheckConstraint("training_window_end < window_start AND window_start <= window_end", name="ck_live_wind_verification_windows"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_version", "context_hash", "training_window_end", name="uq_live_wind_verification_context"),
    )
    op.create_index(
        "ix_live_wind_verification_candidate",
        "weather_live_wind_verification_evidence",
        ["candidate_version", "status", "computed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_wind_verification_candidate",
        table_name="weather_live_wind_verification_evidence",
    )
    op.drop_table("weather_live_wind_verification_evidence")
