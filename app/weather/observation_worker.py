"""Idempotent local observation import foundation; no scheduler activates it."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.live.cache import Cache
from app.models import Spot, WeatherObservation, WeatherStation
from app.weather.providers.common import ObservationStation, haversine_km, nearest_stations

DEFAULT_RETENTION_DAYS = 120


def catchup_window(station, *, now=None, overlap_minutes: int = 20, max_days: int = 7) -> tuple[datetime, datetime]:
    """Bounded provider interval with overlap; uniqueness makes replay idempotent."""
    end = now or datetime.now(timezone.utc)
    last = getattr(station, "last_observation_at", None)
    start = end - timedelta(days=max_days) if last is None else last - timedelta(minutes=overlap_minutes)
    return max(start, end - timedelta(days=max_days)), end


def catalog_candidates(spots: Iterable, catalog: list[ObservationStation], *, limit=3, max_km=100) -> list[dict]:
    """Pure candidate comparison used by dry-runs and the admin UI."""
    output = []
    for spot in spots:
        latitude = float(getattr(spot, "latitude"))
        longitude = float(getattr(spot, "longitude"))
        elevation = getattr(spot, "elevation_m", None)
        for candidate, distance in nearest_stations(latitude, longitude, catalog, limit=limit, max_km=max_km):
            output.append({
                "spot_id": str(spot.id), "provider": candidate.provider,
                "provider_station_id": candidate.station_id, "name": candidate.name,
                "latitude": candidate.latitude, "longitude": candidate.longitude,
                "distance_km": round(distance, 3), "elevation_m": candidate.elevation_m,
                "elevation_difference_m": (None if elevation is None or candidate.elevation_m is None
                                            else round(candidate.elevation_m - float(elevation), 1)),
                "recommended": True, "approved": False,
                "representativeness_status": "unreviewed",
            })
    return output


def sync_catalog_candidates(db, candidates: list[dict], *, dry_run=True) -> dict:
    """Batch-upsert recommendations without ever granting editorial approval."""
    report = {"received": len(candidates), "persisted": 0, "dry_run": dry_run}
    if dry_run or not candidates:
        return report
    safe = [{**row, "active": True, "approved": False, "blocked": False} for row in candidates]
    stmt = insert(WeatherStation).values(safe).on_conflict_do_update(
        constraint="uq_weather_station_spot_provider",
        set_={key: getattr(insert(WeatherStation).excluded, key) for key in (
            "name", "latitude", "longitude", "distance_km", "elevation_m",
            "elevation_difference_m", "recommended")},
    ).returning(WeatherStation.id)
    report["persisted"] = len(db.execute(stmt).scalars().all())
    db.commit()
    return report


def retention_plan(db, *, retention_days=DEFAULT_RETENTION_DAYS, now=None) -> dict:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max(30, retention_days))
    rows = db.scalars(select(WeatherObservation.id).where(WeatherObservation.observed_at < cutoff)).all()
    return {"cutoff": cutoff.isoformat(), "candidate_rows": len(rows), "deleted": 0, "requires_approval": True}


def apply_retention(db, *, approved=False, retention_days=DEFAULT_RETENTION_DAYS, now=None) -> dict:
    plan = retention_plan(db, retention_days=retention_days, now=now)
    if not approved:
        return plan
    cutoff = datetime.fromisoformat(plan["cutoff"])
    result = db.execute(delete(WeatherObservation).where(WeatherObservation.observed_at < cutoff))
    db.commit()
    plan.update({"deleted": result.rowcount or 0, "requires_approval": False})
    return plan


def persist_batch(db, station, rows, *, cache: Cache | None = None, dry_run=True):
    accepted = [row for row in rows if row.import_status == "accepted"]
    report = {"received": len(rows), "accepted": len(accepted), "persisted": 0,
              "rejected": len(rows) - len(accepted), "dry_run": dry_run}
    if dry_run or not accepted:
        return report
    values = [{
        "station_id": station.id, "observed_at": row.observed_at,
        "wind_speed_ms": row.wind_speed_ms, "wind_direction_deg": row.wind_direction_deg,
        "wind_gust_ms": row.wind_gust_ms, "provider_quality": row.provider_quality,
        "fetched_at": row.fetched_at, "import_status": row.import_status,
        "data_issues": list(row.data_issues),
    } for row in accepted]
    result = db.execute(insert(WeatherObservation).values(values).on_conflict_do_nothing(
        constraint="uq_weather_observation_time").returning(WeatherObservation.id))
    report["persisted"] = len(result.scalars().all())
    latest = max(accepted, key=lambda row: row.observed_at)
    station.last_import_at = datetime.now(timezone.utc)
    station.last_observation_at = latest.observed_at
    db.commit()
    if cache:
        cache.set(f"public:weather-v5:measurement:{station.spot_id}", {
            "provider": latest.provider, "station_id": latest.station_id,
            "observed_at": latest.observed_at.isoformat(), "wind_speed_ms": latest.wind_speed_ms,
            "wind_direction_deg": latest.wind_direction_deg, "wind_gust_ms": latest.wind_gust_ms,
            "fetched_at": latest.fetched_at.isoformat(),
        }, 1800)
    return report


def import_station(station, fetcher, db, *, cache=None, dry_run=True, attempts=2):
    last_error = None
    for _attempt in range(max(1, attempts)):
        try:
            return persist_batch(db, station, fetcher(station.provider_station_id), cache=cache, dry_run=dry_run)
        except Exception as exc:
            last_error = type(exc).__name__
    return {"received": 0, "accepted": 0, "persisted": 0, "rejected": 0,
            "dry_run": dry_run, "error_class": last_error}
