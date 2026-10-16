"""Public weather-field manifest, sample and health endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import threading
import time
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.community.ratelimit import RateLimiter, enforce, get_rate_limiter
from app.spatial_fields.contracts import FieldAvailability
from app.spatial_fields.contracts_v2 import classify_freshness
from app.spatial_fields.monitoring import (
    WIND_FIELD_MODELS,
    wave_field_health as build_wave_field_health,
    weather_field_health as build_weather_field_health,
)
from app.spatial_fields.serving import (
    FieldSampleUnavailable,
    load_active_manifest,
    sample_active_field,
    sample_active_field_series,
)
from app.spatial_fields.storage import configured_field_storage
from app.spatial_fields.scopes import model_scope
from app.spatial_fields.selection import HEALTHY_FRESHNESS, rank_model_candidates
from app.models.weather_field import WeatherFieldModel, WeatherFieldPublication, WeatherFieldRun
from app.models.weather_verification import WeatherObservation, WeatherStation
from sqlalchemy import or_, select

router = APIRouter(prefix="/weather-fields", tags=["weather-fields"])

_MANIFEST_RESPONSE_TTL_SECONDS = 15
_MANIFEST_RESPONSE_CACHE_MAX = 512
_manifest_response_cache: dict[str, tuple[float, dict]] = {}
_manifest_response_inflight: dict[str, threading.Event] = {}
_manifest_response_lock = threading.Lock()


def _cached_manifest_response(key: str, builder: Callable[[], dict]) -> dict:
    """Collapse concurrent cold-manifest reads into one database query."""
    while True:
        now = time.monotonic()
        with _manifest_response_lock:
            for cached_key, (expires_at, _payload) in list(
                _manifest_response_cache.items()
            ):
                if expires_at <= now:
                    _manifest_response_cache.pop(cached_key, None)
            cached = _manifest_response_cache.get(key)
            if cached is not None and cached[0] > now:
                return cached[1]
            event = _manifest_response_inflight.get(key)
            if event is None:
                event = threading.Event()
                _manifest_response_inflight[key] = event
                owner = True
            else:
                owner = False
        if owner:
            break
        event.wait(timeout=15)

    try:
        payload = builder()
    except BaseException:
        with _manifest_response_lock:
            _manifest_response_inflight.pop(key, None)
            event.set()
        raise
    with _manifest_response_lock:
        while len(_manifest_response_cache) >= _MANIFEST_RESPONSE_CACHE_MAX:
            _manifest_response_cache.pop(next(iter(_manifest_response_cache)))
        _manifest_response_cache[key] = (
            time.monotonic() + _MANIFEST_RESPONSE_TTL_SECONDS,
            payload,
        )
        _manifest_response_inflight.pop(key, None)
        event.set()
    return payload


def summarize_model_spread(samples: list[dict]) -> dict:
    speeds = [float(sample["speed_ms"]) for sample in samples]
    gusts = [float(sample["gust_ms"]) for sample in samples if sample.get("gust_ms") is not None]
    return {
        "model_count": len(samples),
        "speed_min_ms": min(speeds) if speeds else None,
        "speed_max_ms": max(speeds) if speeds else None,
        "speed_spread_ms": max(speeds) - min(speeds) if len(speeds) >= 2 else None,
        "gust_min_ms": min(gusts) if gusts else None,
        "gust_max_ms": max(gusts) if gusts else None,
        "gust_spread_ms": max(gusts) - min(gusts) if len(gusts) >= 2 else None,
    }


def _public_models(
    db: Session,
    *,
    settings,
    latitude: float | None = None,
    longitude: float | None = None,
    bounds: dict | None = None,
    base_scope: str | None = None,
    primary_model: str | None = None,
) -> list[dict]:
    base_scope = base_scope or settings.weather_field_scope_key
    primary_model = primary_model or settings.weather_field_primary_model
    rows = db.execute(
        select(WeatherFieldPublication, WeatherFieldRun, WeatherFieldModel)
        .join(WeatherFieldRun, WeatherFieldRun.id == WeatherFieldPublication.run_id)
        .join(WeatherFieldModel, WeatherFieldModel.id == WeatherFieldRun.model_id)
        .where(
            WeatherFieldPublication.active.is_(True),
            or_(
                WeatherFieldPublication.scope_key == base_scope,
                WeatherFieldPublication.scope_key.like(
                    f"{base_scope}:%"
                ),
            ),
        )
        .order_by(WeatherFieldModel.priority)
    ).all()
    now = datetime.now(timezone.utc)
    models = [
        {
            "key": model.model_key,
            "name": model.display_name,
            "provider": model.provider_key,
            "coverage": run.coverage,
            "model_run": run.model_run_at,
            "primary": model.model_key == primary_model,
            "priority": model.priority,
            "freshness": classify_freshness(
                max(0, int((now - run.model_run_at).total_seconds()))
            ),
            "valid_from": run.valid_times[0] if run.valid_times else None,
            "valid_to": run.valid_times[-1] if run.valid_times else None,
        }
        for _publication, run, model in rows
    ]
    return rank_model_candidates(
        models,
        latitude=latitude,
        longitude=longitude,
        requested_model=None,
        primary_model=primary_model,
        bounds=bounds,
    )


def _resolve_field_selection(
    db: Session,
    *,
    settings,
    requested_model: str | None,
    latitude: float | None,
    longitude: float | None,
    bounds: dict | None = None,
    valid_at: datetime | None = None,
    base_scope: str | None = None,
    primary_model: str | None = None,
):
    base_scope = base_scope or settings.weather_field_scope_key
    primary_model = primary_model or settings.weather_field_primary_model
    models = _public_models(
        db,
        settings=settings,
        latitude=latitude,
        longitude=longitude,
        bounds=bounds,
        base_scope=base_scope,
        primary_model=primary_model,
    )
    if valid_at is not None:
        instant = (
            valid_at.replace(tzinfo=timezone.utc)
            if valid_at.tzinfo is None
            else valid_at.astimezone(timezone.utc)
        )
        for item in models:
            start = item.get("valid_from")
            end = item.get("valid_to")
            item["covers_time"] = bool(
                start
                and end
                and datetime.fromisoformat(str(start).replace("Z", "+00:00"))
                <= instant
                <= datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            )
        eligible = [item for item in models if item["covers_time"]]
    else:
        eligible = models
    ranked = rank_model_candidates(
        eligible,
        latitude=latitude,
        longitude=longitude,
        requested_model=requested_model,
        primary_model=primary_model,
        bounds=bounds,
    )
    if bounds is not None:
        ranked = [
            item
            for item in ranked
            if item["covers_viewport"] or item["key"] == requested_model
        ]
    elif latitude is not None and longitude is not None:
        ranked = [
            item
            for item in ranked
            if item["covers_point"] or item["key"] == requested_model
        ]
    if not ranked:
        raise HTTPException(status_code=404, detail="No weather field covers this coordinate.")

    storage = configured_field_storage()
    healthy = [item for item in ranked if item["freshness"] in HEALTHY_FRESHNESS]
    degraded = [item for item in ranked if item["freshness"] not in HEALTHY_FRESHNESS]
    # A manual choice remains pinned even when stale; only an unreadable or
    # missing publication triggers fallback. Automatic mode prefers healthy data.
    if requested_model and ranked[0]["key"] == requested_model:
        ordered = [ranked[0], *healthy, *degraded]
    else:
        ordered = [*healthy, *degraded]
    seen: set[str] = set()
    for item in ordered:
        if item["key"] in seen:
            continue
        seen.add(item["key"])
        scope_key = model_scope(
            base_scope,
            item["key"],
            primary_model=primary_model,
        )
        try:
            active = load_active_manifest(db, storage=storage, scope_key=scope_key)
        except (OSError, RuntimeError, ValueError):
            continue
        if active is None:
            continue
        fallback = requested_model is not None and item["key"] != requested_model
        degraded_selection = item["freshness"] not in HEALTHY_FRESHNESS
        selection = {
            "mode": "fallback" if fallback or degraded_selection else "manual" if requested_model else "auto",
            "requested_model": requested_model,
            "selected_model": item["key"],
            "reason": (
                "requested_model_unavailable"
                if fallback
                else "manual_override"
                if requested_model
                else "degraded_coverage_fallback"
                if degraded_selection
                else "forecast_horizon"
                if valid_at is not None
                else "coverage_priority"
            ),
            "latitude": latitude,
            "longitude": longitude,
            "valid_at": valid_at,
        }
        return active, item, models, selection
    raise HTTPException(status_code=503, detail="No healthy weather field publication is readable.")


def _series_manifests(db, *, settings, models: list[dict], base_scope: str, primary_model: str) -> list[dict]:
    storage = configured_field_storage()
    manifests = []
    for item in models:
        if not item.get("covers_point", True):
            continue
        scope_key = model_scope(base_scope, item["key"], primary_model=primary_model)
        try:
            active = load_active_manifest(db, storage=storage, scope_key=scope_key)
        except (OSError, RuntimeError, ValueError):
            continue
        if active is not None and active.manifest.series_template:
            manifests.append(active.manifest.model_dump(mode="json"))
    return manifests


@router.get("/wind")
def wind_field_manifest(
    request: Request,
    response: Response,
    model: str | None = Query(default=None),
    lat: float | None = Query(default=None, ge=-85.05112878, le=85.05112878),
    lon: float | None = Query(default=None, ge=-180, le=180),
    west: float | None = Query(default=None, ge=-180, le=180),
    south: float | None = Query(default=None, ge=-85.05112878, le=85.05112878),
    east: float | None = Query(default=None, ge=-180, le=180),
    north: float | None = Query(default=None, ge=-85.05112878, le=85.05112878),
    valid_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Return the current atomic manifest pointer, never partially built data.

    `valid_at` asks for the moment the viewer is looking at: the short-range
    model wins near the present, but it only publishes two days, so a request
    for day four selects a model whose horizon reaches it (the same rule the
    wave endpoint already applies). Without it the map's clock would run out
    of days wherever ICON-D2 covers the viewport.
    """
    settings = get_settings()
    if not settings.weather_field_public_enabled:
        return FieldAvailability(
            reason=(
                "European wind fields are in shadow processing; point forecasts "
                "remain the public source until activation gates pass."
            )
        ).model_dump(mode="json")
    if (lat is None) != (lon is None):
        raise HTTPException(status_code=422, detail="lat and lon must be provided together.")
    viewport_values = (west, south, east, north)
    if any(value is not None for value in viewport_values) and not all(
        value is not None for value in viewport_values
    ):
        raise HTTPException(
            status_code=422,
            detail="west, south, east and north must be provided together.",
        )
    bounds = None
    if all(value is not None for value in viewport_values):
        if west >= east or south >= north:
            raise HTTPException(status_code=422, detail="Invalid viewport bounds.")
        bounds = {"west": west, "south": south, "east": east, "north": north}
    cache_key = f"{id(db.get_bind())}:wind:{model}:{lat}:{lon}:{bounds}:{valid_at}"

    def build_payload() -> dict:
        active, selected, available_models, selection = _resolve_field_selection(
            db,
            settings=settings,
            requested_model=model,
            latitude=lat,
            longitude=lon,
            bounds=bounds,
            valid_at=valid_at,
        )
        return {
            "enabled": True,
            "public": True,
            "status": selected["freshness"],
            "publication_id": active.publication_id,
            "generation": active.generation,
            "manifest_url": configured_field_storage().public_url(active.object_key),
            "manifest": active.manifest.model_dump(mode="json"),
            "series_manifests": _series_manifests(
                db,
                settings=settings,
                models=available_models,
                base_scope=settings.weather_field_scope_key,
                primary_model=settings.weather_field_primary_model,
            ),
            "available_models": available_models,
            "selection": selection,
            "_manifest_sha256": active.sha256,
        }

    payload = _cached_manifest_response(cache_key, build_payload)
    # `valid_at` belongs in the tag: two instants can resolve to different
    # models, and without it the second one would be answered with a 304 for
    # the first one's payload.
    etag_key = (
        f"{payload['_manifest_sha256']}:{payload['selection']['mode']}:"
        f"{payload['selection']['selected_model']}:{lat}:{lon}:{bounds}:{valid_at}"
    )
    etag = f'"{hashlib.sha256(etag_key.encode()).hexdigest()}"'
    response.headers["Cache-Control"] = (
        f"public, max-age={_MANIFEST_RESPONSE_TTL_SECONDS}, stale-while-revalidate=45"
    )
    response.headers["ETag"] = etag
    if request.headers.get("if-none-match") == etag:
        response.status_code = 304
        return {}
    return {key: value for key, value in payload.items() if not key.startswith("_")}


@router.get("/wind/sample")
def wind_field_sample(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    valid_at: datetime = Query(),
    model: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Sample the exact immutable publication currently used by the map."""
    settings = get_settings()
    if not settings.weather_field_public_enabled:
        raise HTTPException(status_code=503, detail="Wind fields are not public yet.")
    _active, selected, _models, _selection = _resolve_field_selection(
        db,
        settings=settings,
        requested_model=model,
        latitude=lat,
        longitude=lon,
    )
    selected_model = selected["key"]
    scope_key = model_scope(
        settings.weather_field_scope_key,
        selected_model,
        primary_model=settings.weather_field_primary_model,
    )
    try:
        return sample_active_field(
            db,
            storage=configured_field_storage(),
            scope_key=scope_key,
            latitude=lat,
            longitude=lon,
            valid_at=valid_at,
            model_key=selected_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FieldSampleUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Published wind field is unhealthy.") from exc


@router.get("/wind/sample/series")
def wind_field_sample_series(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    model: str | None = Query(default=None),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    """Sample one point across every published valid time, for the point forecast strip.

    The point inspector needs an hourly series at the tapped coordinate; issuing one
    ``/wind/sample`` per valid time would be dozens of requests. We resolve the active
    publication once and interpolate each published instant from the same immutable run.
    """
    settings = get_settings()
    enforce(
        limiter,
        request,
        "weather-field-wind-series",
        limit=getattr(settings, "weather_field_series_rate_limit_per_minute", 30),
        window=60,
    )
    if not settings.weather_field_public_enabled:
        raise HTTPException(status_code=503, detail="Wind fields are not public yet.")
    active, selected, _models, _selection = _resolve_field_selection(
        db,
        settings=settings,
        requested_model=model,
        latitude=lat,
        longitude=lon,
    )
    selected_model = selected["key"]
    scope_key = model_scope(
        settings.weather_field_scope_key,
        selected_model,
        primary_model=settings.weather_field_primary_model,
    )
    try:
        samples = sample_active_field_series(
            db,
            storage=configured_field_storage(),
            scope_key=scope_key,
            latitude=lat,
            longitude=lon,
            valid_times=active.manifest.valid_times,
            model_key=selected_model,
        )
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Published wind field is unhealthy.") from exc
    if not samples:
        raise HTTPException(status_code=404, detail="No field samples available at this point.")
    return {"samples": samples}


@router.get("/wind/compare")
def wind_field_comparison(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    valid_at: datetime = Query(),
    db: Session = Depends(get_db),
) -> dict:
    """Compare independent active model fields at one point and valid time."""
    settings = get_settings()
    if not settings.weather_field_public_enabled:
        raise HTTPException(status_code=503, detail="Wind fields are not public yet.")
    storage = configured_field_storage()
    samples: list[dict] = []
    for item in _public_models(db, settings=settings):
        scope_key = model_scope(
            settings.weather_field_scope_key,
            item["key"],
            primary_model=settings.weather_field_primary_model,
        )
        try:
            samples.append(
                sample_active_field(
                    db,
                    storage=storage,
                    scope_key=scope_key,
                    latitude=lat,
                    longitude=lon,
                    valid_at=valid_at,
                    model_key=item["key"],
                )
            )
        except (FieldSampleUnavailable, ValueError):
            continue
    if not samples:
        raise HTTPException(status_code=404, detail="No comparable model field is available.")
    return {
        "product": "model_wind_comparison",
        "valid_at": valid_at,
        "latitude": lat,
        "longitude": lon,
        "samples": samples,
        "spread": summarize_model_spread(samples),
    }


@router.get("/wind/health")
def wind_field_health(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    return build_weather_field_health(
        db,
        storage=configured_field_storage(),
        settings=settings,
        model_keys=WIND_FIELD_MODELS,
    )


@router.get("/wind/observations")
def wind_field_observations(
    max_age_hours: int = Query(default=3, ge=1, le=24),
    limit: int = Query(default=250, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    """Latest approved station observations for an optional map overlay."""
    if not get_settings().weather_field_public_enabled:
        raise HTTPException(status_code=503, detail="Wind fields are not public yet.")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    latest = (
        select(WeatherObservation)
        .where(
            WeatherObservation.import_status == "accepted",
            WeatherObservation.observed_at >= cutoff,
        )
        .distinct(WeatherObservation.station_id)
        .order_by(WeatherObservation.station_id, WeatherObservation.observed_at.desc())
        .subquery()
    )
    rows = db.execute(
        select(WeatherStation, latest)
        .join(latest, latest.c.station_id == WeatherStation.id)
        .where(
            WeatherStation.active.is_(True),
            WeatherStation.approved.is_(True),
            WeatherStation.blocked.is_(False),
        )
        .order_by(latest.c.observed_at.desc())
        .limit(limit)
    ).all()
    return {
        "observations": [
            {
                "station_id": str(station.id),
                "name": station.name,
                "provider": station.provider,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "observed_at": row["observed_at"],
                "wind_speed_ms": row["wind_speed_ms"],
                "wind_gust_ms": row["wind_gust_ms"],
                "wind_direction_from_deg": row["wind_direction_deg"],
                "quality": row["quality"],
            }
            for mapping in rows
            for station in [mapping[WeatherStation]]
            for row in [mapping]
        ]
    }


@router.get("/waves")
def wave_field_manifest(
    request: Request,
    response: Response,
    model: str | None = Query(default=None),
    lat: float | None = Query(default=None, ge=-85.05112878, le=85.05112878),
    lon: float | None = Query(default=None, ge=-180, le=180),
    west: float | None = Query(default=None, ge=-180, le=180),
    south: float | None = Query(default=None, ge=-85.05112878, le=85.05112878),
    east: float | None = Query(default=None, ge=-180, le=180),
    north: float | None = Query(default=None, ge=-85.05112878, le=85.05112878),
    valid_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Return the active free DWD EWAM/GWAM wave publication."""
    settings = get_settings()
    if not settings.wave_field_public_enabled:
        return FieldAvailability(
            reason="Wave fields are waiting for their first validated DWD publication."
        ).model_dump(mode="json")
    if (lat is None) != (lon is None):
        raise HTTPException(status_code=422, detail="lat and lon must be provided together.")
    viewport_values = (west, south, east, north)
    if any(value is not None for value in viewport_values) and not all(
        value is not None for value in viewport_values
    ):
        raise HTTPException(status_code=422, detail="west, south, east and north must be provided together.")
    bounds = None
    if all(value is not None for value in viewport_values):
        if west >= east or south >= north:
            raise HTTPException(status_code=422, detail="Invalid viewport bounds.")
        bounds = {"west": west, "south": south, "east": east, "north": north}
    cache_key = f"{id(db.get_bind())}:waves:{model}:{lat}:{lon}:{bounds}:{valid_at}"

    def build_payload() -> dict:
        active, selected, available_models, selection = _resolve_field_selection(
            db,
            settings=settings,
            requested_model=model,
            latitude=lat,
            longitude=lon,
            bounds=bounds,
            valid_at=valid_at,
            base_scope=settings.wave_field_scope_key,
            primary_model=settings.wave_field_primary_model,
        )
        return {
            "enabled": True,
            "public": True,
            "status": selected["freshness"],
            "publication_id": active.publication_id,
            "generation": active.generation,
            "manifest_url": configured_field_storage().public_url(active.object_key),
            "manifest": active.manifest.model_dump(mode="json"),
            "series_manifests": _series_manifests(
                db,
                settings=settings,
                models=available_models,
                base_scope=settings.wave_field_scope_key,
                primary_model=settings.wave_field_primary_model,
            ),
            "available_models": available_models,
            "selection": selection,
            "_manifest_sha256": active.sha256,
        }

    payload = _cached_manifest_response(cache_key, build_payload)
    etag_key = f"{payload['_manifest_sha256']}:{payload['selection']['mode']}:{lat}:{lon}:{bounds}:{valid_at}"
    etag = f'"{hashlib.sha256(etag_key.encode()).hexdigest()}"'
    response.headers["Cache-Control"] = (
        f"public, max-age={_MANIFEST_RESPONSE_TTL_SECONDS}, stale-while-revalidate=45"
    )
    response.headers["ETag"] = etag
    if request.headers.get("if-none-match") == etag:
        response.status_code = 304
        return {}
    return {key: value for key, value in payload.items() if not key.startswith("_")}


@router.get("/waves/health")
def wave_field_health(db: Session = Depends(get_db)) -> dict:
    return build_wave_field_health(
        db,
        storage=configured_field_storage(),
        settings=get_settings(),
    )


@router.get("/waves/sample")
def wave_field_sample(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    valid_at: datetime = Query(),
    model: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not settings.wave_field_public_enabled:
        raise HTTPException(status_code=503, detail="Wave fields are not public yet.")
    _active, selected, _models, _selection = _resolve_field_selection(
        db,
        settings=settings,
        requested_model=model,
        latitude=lat,
        longitude=lon,
        valid_at=valid_at,
        base_scope=settings.wave_field_scope_key,
        primary_model=settings.wave_field_primary_model,
    )
    selected_model = selected["key"]
    scope_key = model_scope(
        settings.wave_field_scope_key,
        selected_model,
        primary_model=settings.wave_field_primary_model,
    )
    try:
        return sample_active_field(
            db,
            storage=configured_field_storage(),
            scope_key=scope_key,
            latitude=lat,
            longitude=lon,
            valid_at=valid_at,
            model_key=selected_model,
            nearest_valid_radius_pixels=6,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FieldSampleUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Published wave field is unhealthy.") from exc


@router.get("/waves/sample/series")
def wave_field_sample_series(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    model: str | None = Query(default=None),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> dict:
    settings = get_settings()
    enforce(
        limiter,
        request,
        "weather-field-wave-series",
        limit=getattr(settings, "weather_field_series_rate_limit_per_minute", 30),
        window=60,
    )
    if not settings.wave_field_public_enabled:
        raise HTTPException(status_code=503, detail="Wave fields are not public yet.")
    candidates = _public_models(
        db,
        settings=settings,
        latitude=lat,
        longitude=lon,
        base_scope=settings.wave_field_scope_key,
        primary_model=settings.wave_field_primary_model,
    )
    if model is not None:
        candidates = [item for item in candidates if item["key"] == model]
    storage = configured_field_storage()
    merged: dict[str, dict] = {}
    sources: list[dict] = []
    for candidate in candidates:
        if not candidate.get("covers_point", True):
            continue
        selected_model = candidate["key"]
        scope_key = model_scope(
            settings.wave_field_scope_key,
            selected_model,
            primary_model=settings.wave_field_primary_model,
        )
        try:
            active = load_active_manifest(db, storage=storage, scope_key=scope_key)
            if active is None:
                continue
            model_samples = sample_active_field_series(
                db,
                storage=storage,
                scope_key=scope_key,
                latitude=lat,
                longitude=lon,
                valid_times=active.manifest.valid_times,
                model_key=selected_model,
                nearest_valid_radius_pixels=6,
            )
        except (OSError, RuntimeError, ValueError):
            continue
        for sample in model_samples:
            merged.setdefault(str(sample["valid_at"]), sample)
        sources.append(
            {
                "model": selected_model,
                "publication_id": str(active.publication_id),
                "model_run": candidate.get("model_run"),
                "valid_from": candidate.get("valid_from"),
                "valid_to": candidate.get("valid_to"),
            }
        )
    samples = [merged[key] for key in sorted(merged)]
    if not samples:
        raise HTTPException(status_code=404, detail="No wave samples available at this point.")
    return {"samples": samples, "sources": sources}


@router.get("/nearshore", response_model=FieldAvailability)
def nearshore_field_manifest() -> FieldAvailability:
    return FieldAvailability(
        reason="Nearshore publication is disabled until bathymetry, model and holdout validation gates pass."
    )
