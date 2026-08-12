"""Bounded five-spot phase-2 access gate; downloads nothing when blocked."""

from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from geoalchemy2.shape import to_shape
from app.db.session import SessionLocal
from app.models import Spot
from app.forecast.copernicus_gate import preflight_gate
from app.forecast.geodata import CopernicusDemAdapter, WorldCoverAdapter, analysis_crs

NAMES = ("Baleal", "Brouwersdam", "Mundaka", "Lo Stagnone", "Pozo Izquierdo")


def main():
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "swd-shadow-v2-sectors16-rays9",
        "limits": {
            "spots": 5,
            "parallel_downloads": 2,
            "parallel_profiles": 2,
            "requests": 200,
            "asset_bytes": 268435456,
            "run_bytes": 1073741824,
            "daily_bytes": 2147483648,
            "cache_bytes": 10737418240,
        },
        "spots": [],
        "metrics": {
            "requests": 0,
            "bytes": 0,
            "retries": 0,
            "cache_hits": 0,
            "peak_temporary_bytes": 0,
        },
    }
    with SessionLocal() as db:
        spots = {
            s.name: s
            for s in db.scalars(
                select(Spot).where(Spot.name.in_(NAMES), Spot.status == "published")
            ).all()
        }
        if len(spots) != 5:
            raise RuntimeError("pilot requires exactly five published spots")
        gate = preflight_gate([])
        for name in NAMES:
            p = to_shape(spots[name].location)
            result["spots"].append(
                {
                    "spot_id": str(spots[name].id),
                    "name": name,
                    "coordinates": [p.y, p.x],
                    "analysis_crs": analysis_crs(p.y, p.x),
                    "assets": {
                        "cop_dem_tile": CopernicusDemAdapter.tile(p.y, p.x),
                        "worldcover_tile": WorldCoverAdapter.tile(p.y, p.x),
                    },
                    "status": gate.status,
                    "reason": gate.reason,
                    "sectors": None,
                    "profile_class": "D",
                    "components": {
                        "dem": "unavailable",
                        "wbm": "unavailable",
                        "quality_layers": "unavailable",
                        "worldcover": "cached_phase1_only",
                    },
                }
            )
    result["status"] = gate.status
    out = Path("reports/geodata-phase2-pilot.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    Path("reports/geodata-phase2-pilot.md").write_text(
        f"# Phase-2 pilot gate\n\nStatus: `{gate.status}`. {gate.reason}.\n\nNo metadata or data request was sent; requests=0, bytes=0, retries=0. No Shadow profile was activated and no public forecast changed. Lo Stagnone remains classified as a lagoon, not an inland-lake validation.\n",
        encoding="utf-8",
    )
    print(json.dumps(result["metrics"]))


if __name__ == "__main__":
    main()
