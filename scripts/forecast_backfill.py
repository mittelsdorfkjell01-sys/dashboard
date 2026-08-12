"""Bounded, resumable enqueue for missing/stale forecast geoprofiles."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.db.session import SessionLocal
from app.forecast.publisher import enqueue
from app.models import Spot, SpotGeoProfileVersion
from geoalchemy2.shape import to_shape
from app.forecast.geodata import CopernicusDemAdapter, WorldCoverAdapter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 10:
        parser.error("--batch-size must be 1..10")
    with SessionLocal() as db:
        active = set(
            db.scalars(
                select(SpotGeoProfileVersion.spot_id).where(
                    SpotGeoProfileVersion.active.is_(True),
                    SpotGeoProfileVersion.status == "ready",
                )
            )
        )
        spots = db.scalars(
            select(Spot)
            .where(Spot.id.not_in(active))
            .order_by(Spot.updated_at)
            .limit(args.batch_size)
        ).all()
        print(f"forecast backfill candidates={len(spots)} dry_run={args.dry_run}")
        for spot in spots:
            point = to_shape(spot.location)
            print(
                f"spot={spot.id} name={spot.name} active_profile={spot.id in active} "
                f"worldcover_tile={WorldCoverAdapter.tile(point.y, point.x)} "
                f"dem_tile={CopernicusDemAdapter.tile(point.y, point.x)} "
                "sources=worldcover-2021,cop-dem-glo30 "
                "copernicus_access=requires-local-CDSE-CCM-credentials "
                f"action={'preview' if args.dry_run else 'enqueue'}"
            )
            if not args.dry_run:
                enqueue(
                    db,
                    spot.id,
                    requested_by="forecast-backfill",
                    rebuild_profile=True,
                    reason="backfill",
                )


if __name__ == "__main__":
    main()
