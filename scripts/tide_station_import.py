"""Import the free PEGELONLINE tide/water-level station catalogue and readings."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import TideStation, TideStationAlias
from app.tides.station_import import persist_observations, sync_catalog
from app.tides.stations import PegelOnlineProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--observations-hours", type=int, default=0,
        help="Also import this many hours of measurements for every station (0: catalogue only).",
    )
    args = parser.parse_args()
    if args.observations_hours < 0 or args.observations_hours > 24 * 31:
        parser.error("--observations-hours must be between 0 and 744")

    provider = PegelOnlineProvider()
    with SessionLocal() as db:
        stations = sync_catalog(db, provider)
        inserted = 0
        if args.observations_hours:
            start = datetime.now(timezone.utc) - timedelta(hours=args.observations_hours)
            for station in stations:
                alias = db.scalar(select(TideStationAlias).where(
                    TideStationAlias.station_id == station.id,
                    TideStationAlias.provider == provider.key,
                ))
                if alias is None:
                    continue
                observations = provider.observations(alias.provider_station_id, start=start)
                inserted += persist_observations(db, station, observations)
        active = db.scalar(select(TideStation.id).where(TideStation.status == "active"))
        print(f"provider={provider.key} catalog={len(stations)} observations_inserted={inserted} active={bool(active)}")


if __name__ == "__main__":
    main()
