"""Dry-run report for legacy V3 direction-sector migration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.session import SessionLocal
from app.weather.profiles import WIND_CLIMATOLOGY_V3_NOTE
from app.weather.usable_directions import classify_legacy_v3_sectors


def build_report() -> dict:
    with SessionLocal() as db:
        profiles = db.execute(text(
            "SELECT DISTINCT p.id AS profile_id, p.spot_id, s.name AS spot_name "
            "FROM spot_weather_profiles p "
            "JOIN spot_weather_sectors ws ON ws.profile_id = p.id "
            "LEFT JOIN spots s ON s.id = p.spot_id "
            "WHERE ws.note = :note ORDER BY p.id"
        ), {"note": WIND_CLIMATOLOGY_V3_NOTE}).mappings().all()
        items = []
        for profile in profiles:
            rows = db.execute(text(
                "SELECT id, start_deg, end_deg, speed_factor, direction_offset_deg, "
                "version, enabled FROM spot_weather_sectors "
                "WHERE profile_id = :profile_id AND note = :note ORDER BY created_at, id"
            ), {"profile_id": profile["profile_id"], "note": WIND_CLIMATOLOGY_V3_NOTE}).mappings().all()
            result = classify_legacy_v3_sectors(list(rows))
            items.append({
                "profile_id": str(profile["profile_id"]),
                "spot_id": str(profile["spot_id"]),
                "spot_name": profile["spot_name"],
                "classification": result["status"],
                "sectors": result["sectors"],
                "problems": result["problems"],
                "legacy_rows": len(rows),
            })
        counts = {status: sum(item["classification"] == status for item in items) for status in ("active", "ambiguous", "missing")}
        return {"mode": "dry_run", "writes": 0, "profiles": items, "counts": counts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build_report(), indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
