"""Bounded, resumable enqueue for missing/stale forecast geoprofiles."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db.session import SessionLocal
from app.forecast.publisher import enqueue
from app.models import ForecastSnapshot, Spot
from geoalchemy2.shape import to_shape
from app.live.weather_contract import WEATHER_CONTRACT_VERSION, marine_classification


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", choices=("batch", "canary", "validation"), default="batch")
    parser.add_argument("--offset", type=int, default=0, help="resume cursor (ordered spot offset)")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 10:
        parser.error("--batch-size must be 1..10")
    with SessionLocal() as db:
        completed = set(db.scalars(select(ForecastSnapshot.spot_id).where(
            ForecastSnapshot.active.is_(True),
            ForecastSnapshot.payload["contract_version"].as_string() == WEATHER_CONTRACT_VERSION,
        )))
        requested_limit = 3 if args.mode == "canary" else 5 if args.mode == "validation" else args.batch_size
        spots = db.scalars(
            select(Spot)
            .where(Spot.status == "published", Spot.id.not_in(completed))
            .order_by(Spot.updated_at)
            .offset(max(0, args.offset))
            .limit(requested_limit)
        ).all()
        print(f"forecast backfill contract={WEATHER_CONTRACT_VERSION} mode={args.mode} candidates={len(spots)} dry_run={args.dry_run} resume_offset={args.offset}")
        for spot in spots:
            point = to_shape(spot.location)
            marine = marine_classification(spot).value
            print(
                f"spot={spot.id} name={spot.name} atmosphere=expected solar=expected marine={marine} "
                f"coordinates={point.y:.5f},{point.x:.5f} providers=atmosphere:1,marine:{int(marine == 'available')} "
                f"action={'preview' if args.dry_run else 'enqueue'}"
            )
            if not args.dry_run:
                try:
                    enqueue(db, spot.id, requested_by="forecast-backfill", rebuild_profile=False, reason="backfill")
                except Exception as exc:
                    db.rollback()
                    print(f"spot={spot.id} error={type(exc).__name__}")
        # Completed v2 snapshots disappear from the candidate query, so the safe
        # resume cursor remains stable instead of skipping the next batch.
        print(f"next_resume_offset={args.offset}")


if __name__ == "__main__":
    main()
