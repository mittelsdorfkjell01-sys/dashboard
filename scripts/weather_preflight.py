"""Read-only coverage report for every canonical spot; performs no HTTP calls."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.live.service import InvalidSpotCoordinates, _spot_coords
from app.models import Spot, SpotWeatherProfile


def coverage_report() -> dict:
    with SessionLocal() as db:
        spots = list(db.scalars(select(Spot).order_by(Spot.id)))
        profile_ids = set(db.scalars(select(SpotWeatherProfile.spot_id)))
        valid, invalid, public = [], [], []
        for spot in spots:
            if spot.status == "published":
                public.append(str(spot.id))
            try:
                _spot_coords(spot)
                valid.append(str(spot.id))
            except (InvalidSpotCoordinates, TypeError, ValueError):
                invalid.append(str(spot.id))
        return {
            "total": len(spots), "public": len(public), "valid_coordinates": len(valid),
            "invalid_coordinates": len(invalid), "with_profile": len(profile_ids),
            "without_profile": len(spots) - len(profile_ids), "invalid_spot_ids": invalid,
        }


if __name__ == "__main__":
    report = coverage_report()
    print("WEATHER PREFLIGHT (read-only, no provider calls)")
    for key in ("total", "public", "valid_coordinates", "invalid_coordinates", "with_profile", "without_profile"):
        print(f"{key}={report[key]}")
    for spot_id in report["invalid_spot_ids"]:
        print(f"INVALID spot_id={spot_id} reason=coordinates")
