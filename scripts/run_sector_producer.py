"""Run a sector producer over spots, writing CANDIDATE sectors (never activated).

Usage:
    python -m scripts.run_sector_producer --all
    python -m scripts.run_sector_producer --spot <UUID> --producer gwa
    python -m scripts.run_sector_producer --limit 5 --dry-run

Writes enabled=False candidates only. Activation is a separate, WP1-gated step
(scripts/activate_sectors.py or the admin endpoint). Without all rasters required
by the selected producer, the run records an unavailable status per spot and
changes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.forecast.sector_runner import run_sector_producer


def main() -> None:
    parser = argparse.ArgumentParser(description="Build candidate sector factors.")
    scope = parser.add_mutually_exclusive_group(required=False)
    scope.add_argument("--all", action="store_true", help="Every published spot.")
    scope.add_argument("--spot", action="append", help="One or more spot ids.")
    scope.add_argument("--limit", type=int, help="Least-recently-built N published spots.")
    parser.add_argument(
        "--producer",
        choices=("gwa", "microscale", "combined"),
        default="combined",
    )
    parser.add_argument("--dry-run", action="store_true", help="Compute and report; write nothing.")
    parser.add_argument("--check-rasters", action="store_true",
                        help="Run the raster preflight doctor for --producer and exit.")
    parser.add_argument("--lat", type=float, help="Probe latitude for the microscale raster doctor.")
    parser.add_argument("--lon", type=float, help="Probe longitude for the microscale raster doctor.")
    args = parser.parse_args()

    if args.check_rasters:
        if args.producer == "combined":
            from app.forecast.gwa_producer import gwa_raster_doctor
            from app.forecast.microscale import microscale_raster_doctor

            probe = (args.lat, args.lon) if args.lat is not None and args.lon is not None else None
            gwa = gwa_raster_doctor()
            microscale = microscale_raster_doctor(probe=probe)
            report = {
                "ok": bool(gwa.get("ok") and microscale.get("ok")),
                "gwa": gwa,
                "microscale": microscale,
            }
        elif args.producer == "microscale":
            from app.forecast.microscale import microscale_raster_doctor

            probe = (args.lat, args.lon) if args.lat is not None and args.lon is not None else None
            report = microscale_raster_doctor(probe=probe)
        else:
            from app.forecast.gwa_producer import gwa_raster_doctor

            report = gwa_raster_doctor()
        print(json.dumps(report, indent=2, default=str))
        raise SystemExit(0 if report.get("ok") else 1)
    if not (args.all or args.spot or args.limit):
        parser.error("one of --all / --spot / --limit is required (or --check-rasters)")

    spot_ids = [uuid.UUID(value) for value in args.spot] if args.spot else None
    with SessionLocal() as db:
        summary = run_sector_producer(
            db, producer=args.producer, spot_ids=spot_ids,
            limit=args.limit, dry_run=args.dry_run,
        )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
