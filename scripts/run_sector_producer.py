"""Run a sector producer over spots, writing CANDIDATE sectors (never activated).

Usage:
    python -m scripts.run_sector_producer --all
    python -m scripts.run_sector_producer --spot <UUID> --producer gwa
    python -m scripts.run_sector_producer --limit 5 --dry-run

Writes enabled=False candidates only. Activation is a separate, WP1-gated step
(scripts/activate_sectors.py or the admin endpoint). Without a mounted GWA raster
the run just records gwa_not_mounted per spot and changes nothing.
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
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true", help="Every published spot.")
    scope.add_argument("--spot", action="append", help="One or more spot ids.")
    scope.add_argument("--limit", type=int, help="Least-recently-built N published spots.")
    parser.add_argument("--producer", choices=("gwa", "microscale"), default="gwa")
    parser.add_argument("--dry-run", action="store_true", help="Compute and report; write nothing.")
    args = parser.parse_args()

    spot_ids = [uuid.UUID(value) for value in args.spot] if args.spot else None
    with SessionLocal() as db:
        summary = run_sector_producer(
            db, producer=args.producer, spot_ids=spot_ids,
            limit=args.limit, dry_run=args.dry_run,
        )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
