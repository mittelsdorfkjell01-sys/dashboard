"""recommendation evaluation, attribution, and calibration proposals

Revision ID: 0069_scoring_evaluation
Revises: 0068_recommendation_log
"""

from __future__ import annotations

from copy import deepcopy
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0069_scoring_evaluation"
down_revision = "0068_recommendation_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendation_log",
        sa.Column("audience_segment", sa.String(32), server_default="anonymous", nullable=False),
    )
    op.add_column(
        "user_events",
        sa.Column("recommendation_log_id", postgresql.UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_user_events_recommendation_log",
        "user_events", "recommendation_log",
        ["recommendation_log_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_user_events_recommendation", "user_events", ["recommendation_log_id"]
    )
    op.create_table(
        "scoring_calibration_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("sport", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("base_params_version", sa.Integer(), nullable=False),
        sa.Column("proposed_params", postgresql.JSONB(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("reviewed_by", sa.String(160)),
        sa.Column("review_note", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("activated_params_version", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('default_rider','personal_band','social_weight')", name="ck_scoring_calibration_kind"),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_scoring_calibration_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scoring_calibration_status_created",
        "scoring_calibration_proposals", ["status", "created_at"],
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT sport, params FROM scoring_params WHERE version = 3")
    ).mappings().all()
    for row in rows:
        params = deepcopy(row["params"])
        if row["sport"] == "kitesurf":
            params["social"] = {
                "weight": 0.02,
                "min_group_size": 20,
                "validated": False,
                "similar_band": False,
            }
            params.setdefault("parameter_log", []).append({
                "version": 4,
                "kind": "social_signal",
                "weight": 0.02,
                "effective": False,
                "reason": "Initial small weight; activation requires measured improvement",
            })
        bind.execute(
            sa.text("""
                INSERT INTO scoring_params (sport, version, active, params)
                VALUES (:sport, 4, false, CAST(:params AS jsonb))
                ON CONFLICT (sport, version) DO NOTHING
            """),
            {"sport": row["sport"], "params": json.dumps(params)},
        )
    bind.execute(sa.text("UPDATE scoring_params SET active = false"))
    bind.execute(sa.text("UPDATE scoring_params SET active = true WHERE version = 4"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM scoring_params WHERE version = 4"))
    bind.execute(sa.text("UPDATE scoring_params SET active = (version = 3)"))
    op.drop_index("ix_scoring_calibration_status_created", table_name="scoring_calibration_proposals")
    op.drop_table("scoring_calibration_proposals")
    op.drop_index("ix_user_events_recommendation", table_name="user_events")
    op.drop_constraint("fk_user_events_recommendation_log", "user_events", type_="foreignkey")
    op.drop_column("user_events", "recommendation_log_id")
    op.drop_column("recommendation_log", "audience_segment")
