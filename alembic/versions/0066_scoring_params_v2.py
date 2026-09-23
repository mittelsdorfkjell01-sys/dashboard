"""Activate scoring parameter version 2 without changing version 1.

Revision ID: 0066_scoring_params_v2
Revises: 0065_account_experience
"""

from __future__ import annotations

from copy import deepcopy

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert


revision = "0066_scoring_params_v2"
down_revision = "0065_account_experience"
branch_labels = None
depends_on = None


DEFAULT_V1 = {
    "kitesurf": {
        "sport_type": "wind",
        "daylight_required": True,
        "wind": {"min_kt": 12.0, "max_kt": 35.0, "good_min_kt": 16.0, "good_max_kt": 28.0},
        "gust_ratio_downgrade": 1.4,
        "gust_delta_downgrade_kt": 8.0,
        "level_offsets": {
            "beginner": {"good_min_kt": -2.0, "good_max_kt": -8.0},
            "advanced": {"good_min_kt": 2.0, "good_max_kt": 3.0},
            "expert": {"good_min_kt": 4.0, "good_max_kt": 5.0},
        },
        "week_good_threshold": 0.4,
        "d0_km": 40.0,
    },
    "windsurf": {},
    "wing": {},
    "surf": {
        "sport_type": "wave",
        "daylight_required": True,
        "swell": {
            "min_m": 0.6,
            "max_m": 4.0,
            "good_min_m": 1.0,
            "good_max_m": 2.5,
            "period_min_s": 8.0,
        },
        "onshore_wind_max_kt": 18.0,
        "tide": {"dependence": False},
        "level_offsets": {
            "beginner": {"good_min_m": -0.4, "good_max_m": -1.0},
            "advanced": {"good_min_m": 0.3, "good_max_m": 0.5},
            "expert": {"good_min_m": 0.5, "good_max_m": 1.0},
        },
        "week_good_threshold": 0.4,
        "d0_km": 40.0,
    },
}
DEFAULT_V1["windsurf"] = deepcopy(DEFAULT_V1["kitesurf"])
DEFAULT_V1["wing"] = deepcopy(DEFAULT_V1["kitesurf"])


def _table():
    return sa.table(
        "scoring_params",
        sa.column("sport", sa.String(40)),
        sa.column("version", sa.Integer()),
        sa.column("active", sa.Boolean()),
        sa.column("params", postgresql.JSONB()),
    )


def upgrade() -> None:
    connection = op.get_bind()
    table = _table()
    for sport, fallback in DEFAULT_V1.items():
        v1 = connection.execute(
            sa.select(table.c.params).where(
                table.c.sport == sport,
                table.c.version == 1,
            )
        ).scalar_one_or_none()
        params = deepcopy(v1 or fallback)
        offsets = params.setdefault("level_offsets", {})
        if sport == "surf":
            offsets["competition"] = deepcopy(offsets.get("expert", {}))
        else:
            expert = offsets.get("expert", {})
            offsets["competition"] = {
                "good_min_kt": float(expert.get("good_min_kt", 4.0)) + 1.0,
                "good_max_kt": float(expert.get("good_max_kt", 5.0)) + 1.0,
            }
        connection.execute(
            insert(table)
            .values(sport=sport, version=2, active=False, params=params)
            .on_conflict_do_nothing(index_elements=["sport", "version"])
        )

    connection.execute(sa.update(table).values(active=False))
    connection.execute(
        sa.update(table).where(table.c.version == 2).values(active=True)
    )


def downgrade() -> None:
    connection = op.get_bind()
    table = _table()
    connection.execute(sa.delete(table).where(table.c.version == 2))
    connection.execute(sa.update(table).values(active=False))
    connection.execute(
        sa.update(table).where(table.c.version == 1).values(active=True)
    )
