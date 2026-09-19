"""Bounded, provider-isolated refresh of the configured station catalog."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from geoalchemy2 import Geometry
from sqlalchemy import func, select, text

from app.config import get_settings
from app.models import (
    Spot, WeatherStation, WeatherStationCaptureCycle, WeatherStationCatalogState,
)
from app.weather.observation_worker import (
    catalog_candidates,
    retry_delay_seconds,
    sync_catalog_candidates,
)
from app.weather.providers import dmi, dwd
from app.weather.providers.common import nearest_stations


def _pilot_spots(db, *, bounds: tuple[float, float, float, float], limit: int):
    south, north, west, east = bounds
    return [
        SimpleNamespace(id=identifier, latitude=latitude, longitude=longitude,
                        elevation_m=None)
        for identifier, latitude, longitude in db.execute(
            select(
                Spot.id,
                func.ST_Y(Spot.location.cast(Geometry)),
                func.ST_X(Spot.location.cast(Geometry)),
            )
            .where(
                Spot.status == "published",
                func.ST_Y(Spot.location.cast(Geometry)).between(south, north),
                func.ST_X(Spot.location.cast(Geometry)).between(west, east),
            )
            .order_by(Spot.id)
            .limit(max(1, limit))
        ).all()
    ]


def _record_state(db, provider: str, *, error_class: str | None,
                  counts: dict | None = None, started_at: datetime | None = None,
                  cycle_status: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    state = db.get(WeatherStationCatalogState, provider)
    if state is None:
        state = WeatherStationCatalogState(provider=provider)
        db.add(state)
    if cycle_status == "overlap_skipped":
        db.add(WeatherStationCaptureCycle(
            job_type="catalog", provider=provider,
            started_at=started_at or now, finished_at=now,
            status="overlap_skipped", counts=counts or {},
        ))
        db.commit()
        return
    failures = (state.consecutive_failures or 0) + 1 if error_class else 0
    state.last_attempt_at = now
    state.last_error_class = error_class
    state.last_error_at = now if error_class else None
    state.consecutive_failures = failures
    state.last_counts = counts or {}
    if error_class:
        settings = get_settings()
        delay = retry_delay_seconds(
            failures,
            initial_seconds=settings.weather_station_catalog_retry_initial_seconds,
            maximum_seconds=settings.weather_station_catalog_retry_max_seconds,
        )
        state.next_attempt_at = now + timedelta(seconds=delay)
    else:
        state.last_success_at = now
        state.next_attempt_at = None
    db.add(WeatherStationCaptureCycle(
        job_type="catalog",
        provider=provider,
        started_at=started_at or now,
        finished_at=now,
        status=cycle_status or ("error" if error_class else "success"),
        counts=counts or {},
    ))
    db.commit()


def _refresh_provider(
    db,
    provider: str,
    spots: list,
    *,
    bounds: tuple[float, float, float, float],
    candidate_limit: int,
    max_km: float,
    dry_run: bool,
) -> dict:
    if not dry_run:
        locked = db.scalar(text(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"
        ), {"key": f"station-catalog:{provider}"})
        if not locked:
            return {"provider": provider, "status": "overlap_skipped"}

    if provider == "dwd":
        items = dwd.fetch_stations(
            include_inactive=True, db=None if dry_run else db
        )
    elif provider == "dmi":
        items = dmi.fetch_stations()
    else:
        raise ValueError("station_catalog_provider_unsupported")

    south, north, west, east = bounds
    regional = [
        item for item in items
        if south <= item.latitude <= north and west <= item.longitude <= east
    ]
    selected_ids = {
        item.station_id
        for spot in spots
        for item, _distance in nearest_stations(
            spot.latitude,
            spot.longitude,
            [entry for entry in regional if entry.active],
            limit=candidate_limit,
            max_km=max_km,
        )
    }
    metadata_errors = 0
    if provider == "dwd":
        enriched = []
        for item in regional:
            if item.station_id not in selected_ids:
                enriched.append(item)
                continue
            try:
                enriched.append(dwd.fetch_station_metadata(
                    item, db=None if dry_run else db
                ))
            except Exception:
                metadata_errors += 1
                enriched.append(item)
        regional = enriched

    candidates = catalog_candidates(
        spots,
        [item for item in regional if item.active],
        limit=candidate_limit,
        max_km=max_km,
    )
    existing = db.scalars(select(WeatherStation).where(
        WeatherStation.provider == provider
    )).all()
    by_provider_id = {
        (item.provider, item.provider_station_id): item for item in existing
    }
    retirements = []
    for item in regional:
        if item.active:
            continue
        previous = by_provider_id.get((provider, item.station_id))
        if previous is None:
            continue
        target = SimpleNamespace(
            id=previous.spot_id,
            latitude=previous.latitude,
            longitude=previous.longitude,
            elevation_m=None,
        )
        retirements.extend(catalog_candidates(
            [target], [item], limit=1, max_km=max(max_km, 500)
        ))
    candidates.extend(retirements)
    persistence = sync_catalog_candidates(db, candidates, dry_run=dry_run)
    return {
        "provider": provider,
        "status": "success",
        "catalog_records": len(regional),
        "active_records": sum(item.active for item in regional),
        "inactive_records": sum(not item.active for item in regional),
        "selected_candidates": len(candidates) - len(retirements),
        "retirements": len(retirements),
        "metadata_errors": metadata_errors,
        "persistence": persistence,
    }


def run_station_catalog_refresh(
    db,
    *,
    providers: tuple[str, ...] = ("dwd", "dmi"),
    dry_run: bool = True,
    force: bool = False,
    bounds: tuple[float, float, float, float] | None = None,
    spot_limit: int | None = None,
    candidate_limit: int | None = None,
    max_km: float | None = None,
) -> dict:
    """Refresh each provider independently; never creates an approval."""
    settings = get_settings()
    selected_bounds = bounds or settings.weather_station_catalog_bounds
    spots = _pilot_spots(
        db,
        bounds=selected_bounds,
        limit=spot_limit or settings.weather_station_catalog_spot_limit,
    )
    report = {"dry_run": dry_run, "pilot_spots": len(spots), "providers": {}}
    now = datetime.now(timezone.utc)
    for provider in providers:
        started_at = datetime.now(timezone.utc)
        state = db.get(WeatherStationCatalogState, provider)
        if not force and state is not None and state.next_attempt_at is not None \
                and state.next_attempt_at > now:
            report["providers"][provider] = {
                "provider": provider, "status": "backoff"
            }
            continue
        try:
            result = _refresh_provider(
                db,
                provider,
                spots,
                bounds=selected_bounds,
                candidate_limit=(candidate_limit
                                 or settings.weather_station_catalog_candidate_limit),
                max_km=max_km or settings.weather_station_catalog_max_km,
                dry_run=dry_run,
            )
            report["providers"][provider] = result
            if not dry_run and result["status"] == "success":
                _record_state(db, provider, error_class=None, counts={
                    "catalog_records": result["catalog_records"],
                    "selected_candidates": result["selected_candidates"],
                    "metadata_errors": result["metadata_errors"],
                    **result["persistence"],
                }, started_at=started_at)
            elif not dry_run and result["status"] == "overlap_skipped":
                _record_state(
                    db, provider, error_class=None, counts={},
                    started_at=started_at, cycle_status="overlap_skipped",
                )
        except Exception as exc:
            db.rollback()
            error_class = type(exc).__name__
            report["providers"][provider] = {
                "provider": provider, "status": "error",
                "error_class": error_class,
            }
            if not dry_run:
                _record_state(
                    db, provider, error_class=error_class,
                    started_at=started_at,
                )
    return report
