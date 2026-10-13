"""separate usable wind directions from forecast correction sectors

Revision ID: 0070_usable_wind_directions
Revises: 0069_scoring_evaluation
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0070_usable_wind_directions"
down_revision = "0069_scoring_evaluation"
branch_labels = None
depends_on = None

LEGACY_NOTE = "Windklimatologie V3"
LEGACY_RULE_VERSION = "legacy-v3-sector-migration-v1"


def _angle(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def _classify(rows) -> dict:
    enabled = [row for row in rows if bool(row["enabled"])]
    sectors: list[int] = []
    problems: list[str] = []
    evidence_rows: list[dict] = []
    for position, row in enumerate(enabled):
        raw = {
            "id": str(row["id"]),
            "start_deg": row["start_deg"],
            "end_deg": row["end_deg"],
            "speed_factor": row["speed_factor"],
            "direction_offset_deg": row["direction_offset_deg"],
            "version": row["version"],
        }
        evidence_rows.append(raw)
        try:
            start = float(raw["start_deg"]) % 360.0
            end = float(raw["end_deg"]) % 360.0
            index = round(start / 22.5) % 16
            neutral = (
                _angle(start, index * 22.5) <= 1e-7
                and _angle(end, ((index + 1) * 22.5) % 360.0) <= 1e-7
                and abs(float(raw["speed_factor"]) - 1.0) <= 1e-9
                and abs(float(raw["direction_offset_deg"])) <= 1e-9
                and int(raw["version"]) == 1
            )
        except (TypeError, ValueError, OverflowError):
            neutral = False
            index = -1
        if not neutral:
            problems.append(f"row[{position}]_not_canonical_neutral_v1")
        elif index in sectors:
            problems.append(f"row[{position}]_duplicate_sector")
        else:
            sectors.append(index)
    if problems:
        status, sectors = "ambiguous", []
    elif sectors:
        status = "active"
        sectors.sort()
    else:
        status = "missing"
    return {
        "status": status,
        "sectors": sectors,
        "windows": [
            {"start_deg": index * 22.5, "end_deg": ((index + 1) * 22.5) % 360.0}
            for index in sectors
        ],
        "problems": problems,
        "rows": evidence_rows,
    }


def upgrade() -> None:
    op.add_column("spot_weather_profiles", sa.Column("usable_direction_geometry", postgresql.JSONB()))
    op.add_column("spot_weather_profiles", sa.Column("usable_direction_geometry_version", sa.String(80)))
    op.add_column("spot_weather_profiles", sa.Column("usable_direction_rule_version", sa.String(80)))
    op.add_column(
        "spot_weather_profiles",
        sa.Column("usable_direction_status", sa.String(24), server_default="missing", nullable=False),
    )
    op.add_column(
        "spot_weather_profiles",
        sa.Column("usable_direction_sectors", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.add_column(
        "spot_weather_profiles",
        sa.Column("usable_direction_windows", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.add_column(
        "spot_weather_profiles",
        sa.Column("usable_direction_evidence", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column("spot_weather_profiles", sa.Column("usable_direction_calculated_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_weather_profile_usable_direction_status",
        "spot_weather_profiles",
        "usable_direction_status IN ('missing','active','blocked','ambiguous')",
    )

    bind = op.get_bind()
    profiles = bind.execute(
        sa.text(
            "SELECT DISTINCT profile_id FROM spot_weather_sectors "
            "WHERE note = :note ORDER BY profile_id"
        ),
        {"note": LEGACY_NOTE},
    ).scalars().all()
    for profile_id in profiles:
        rows = bind.execute(
            sa.text(
                "SELECT id, start_deg, end_deg, speed_factor, direction_offset_deg, "
                "version, enabled FROM spot_weather_sectors "
                "WHERE profile_id = :profile_id AND note = :note ORDER BY created_at, id"
            ),
            {"profile_id": profile_id, "note": LEGACY_NOTE},
        ).mappings().all()
        result = _classify(rows)
        evidence = {
            "origin": "legacy_sector_migration",
            "rule_version": LEGACY_RULE_VERSION,
            "source_note": LEGACY_NOTE,
            "rows": result["rows"],
            "missing": result["problems"],
            "safety_scope": "geometric_onshore_sideshore_suitability_only",
        }
        bind.execute(
            sa.text(
                "UPDATE spot_weather_profiles SET "
                "usable_direction_rule_version = :rule_version, "
                "usable_direction_status = :status, "
                "usable_direction_sectors = CAST(:sectors AS jsonb), "
                "usable_direction_windows = CAST(:windows AS jsonb), "
                "usable_direction_evidence = CAST(:evidence AS jsonb), "
                "usable_direction_calculated_at = now() WHERE id = :profile_id"
            ),
            {
                "rule_version": LEGACY_RULE_VERSION,
                "status": result["status"],
                "sectors": json.dumps(result["sectors"]),
                "windows": json.dumps(result["windows"]),
                "evidence": json.dumps(evidence),
                "profile_id": profile_id,
            },
        )
    bind.execute(
        sa.text("DELETE FROM spot_weather_sectors WHERE note = :note"),
        {"note": LEGACY_NOTE},
    )


def downgrade() -> None:
    bind = op.get_bind()
    profiles = bind.execute(
        sa.text(
            "SELECT id, usable_direction_sectors FROM spot_weather_profiles "
            "WHERE usable_direction_status = 'active'"
        )
    ).mappings().all()
    for profile in profiles:
        for index in profile["usable_direction_sectors"] or []:
            bind.execute(
                sa.text(
                    "INSERT INTO spot_weather_sectors "
                    "(id, profile_id, start_deg, end_deg, speed_factor, direction_offset_deg, "
                    "version, enabled, note, created_at, updated_at) VALUES "
                    "(gen_random_uuid(), :profile_id, :start_deg, :end_deg, 1, 0, 1, true, :note, now(), now())"
                ),
                {
                    "profile_id": profile["id"],
                    "start_deg": float(index) * 22.5,
                    "end_deg": ((float(index) + 1) * 22.5) % 360.0,
                    "note": LEGACY_NOTE,
                },
            )
    op.drop_constraint("ck_weather_profile_usable_direction_status", "spot_weather_profiles", type_="check")
    for column in (
        "usable_direction_calculated_at",
        "usable_direction_evidence",
        "usable_direction_windows",
        "usable_direction_sectors",
        "usable_direction_status",
        "usable_direction_rule_version",
        "usable_direction_geometry_version",
        "usable_direction_geometry",
    ):
        op.drop_column("spot_weather_profiles", column)
