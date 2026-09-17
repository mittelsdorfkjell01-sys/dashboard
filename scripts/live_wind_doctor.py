"""Print the internal LiveWind operational report for worker monitoring."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.weather.live_wind_operations import build_live_wind_operations_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--no-rasters", action="store_true")
    parser.add_argument("--fail-on-alert", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        report = build_live_wind_operations_report(
            db,
            days=args.days,
            include_rasters=not args.no_rasters,
        )
    print(json.dumps(report, sort_keys=True))
    critical = [
        alert
        for doctor in report["doctors"].values()
        if isinstance(doctor, dict)
        for alert in doctor.get("alerts", [])
        if alert.get("severity") == "critical"
    ]
    if args.fail_on_alert and critical:
        raise SystemExit(2)
