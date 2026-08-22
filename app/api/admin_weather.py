"""Authenticated weather-profile management and volatile diagnostics."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.deps import require_role
from app.db.session import get_db
from app.live import service as live_service
from app.models import (
    ForecastProcessingJob,
    ForecastSnapshot,
    Region,
    Spot,
    SpotGeoProfileVersion,
    SpotGeoShadowProfile,
    SpotGeoShadowSector,
    SpotWeatherProfile,
    SpotWeatherSector,
    WeatherModelCalibration,
    WeatherStation,
    WeatherShadowForecast,
    WeatherShadowRun,
    WeatherShadowStudy,
    WindClimatologyCell,
    WindClimatologyRun,
)

router = APIRouter(
    prefix="/admin/weather",
    tags=["admin-weather"],
    dependencies=[Depends(require_role("admin", "curator"))],
)


class WindCellSelection(BaseModel):
    mode: Literal["automatic", "manual"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


@router.get("/spots/{spot_id}/wind-climatology")
def wind_climatology_status(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    cell = db.scalar(select(WindClimatologyCell).where(WindClimatologyCell.spot_id == spot_id))
    latest = db.scalar(select(WindClimatologyRun).where(WindClimatologyRun.spot_id == spot_id).order_by(WindClimatologyRun.created_at.desc()))
    active = db.scalar(select(WindClimatologyRun).where(WindClimatologyRun.spot_id == spot_id, WindClimatologyRun.is_active.is_(True)))
    return {
        "cell": None if cell is None else {"mode": cell.selection_mode, "spot": [cell.spot_lat, cell.spot_lon], "requested": [cell.requested_lat, cell.requested_lon], "actual": [cell.actual_lat, cell.actual_lon] if cell.actual_lat is not None else None, "distance_km": cell.distance_km, "model": cell.model, "resolution_degrees": cell.resolution_deg, "status": cell.status, "warnings": cell.warnings},
        "active": None if active is None else {"id": str(active.id), "period": [active.start_year, active.end_year], "activated_at": active.activated_at},
        "latest": None if latest is None else {"id": str(latest.id), "status": latest.status, "error": latest.error, "started_at": latest.started_at, "completed_at": latest.completed_at},
    }


@router.put("/spots/{spot_id}/wind-climatology/cell", status_code=202)
def update_wind_cell(spot_id: uuid.UUID, body: WindCellSelection, db: Session = Depends(get_db)) -> dict:
    from app.wind_climatology.service import set_cell
    try:
        run = set_cell(db, spot_id, mode=body.mode, lat=body.latitude, lon=body.longitude)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 422, detail=str(exc))
    return {"run_id": str(run.id), "status": run.status}


@router.post("/spots/{spot_id}/wind-climatology/recalculate", status_code=202)
def recalculate_wind_climatology(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    from app.wind_climatology.service import enqueue
    try:
        run, created = enqueue(db, spot_id, force=True)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"run_id": str(run.id), "status": run.status, "created": created}


@router.post("/spots/{spot_id}/wind-climatology-v3/runs", status_code=202)
def create_wind_climatology_v3_run(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Create a shadow-only run; processing is an explicit worker action."""
    from app.wind_climatology.v3_service import enqueue
    try:
        run, created = enqueue(db, spot_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"run_id": str(run.id), "status": run.status, "created": created, "public_effect": "none"}


@router.get("/spots/{spot_id}/wind-climatology-v3/status")
def wind_climatology_v3_status(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    from app.wind_climatology.v3_service import status
    if db.get(Spot, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    return status(db, spot_id)


@router.get("/spots/{spot_id}/wind-climatology-v3/variant")
def wind_climatology_v3_variant(spot_id: uuid.UUID, min_wind_kn: int = Query(15, ge=5, le=40), max_wind_kn: int = Query(20, ge=6, le=40), open_upper: bool = False, direction_mode: Literal["all", "usable"] = "all", db: Session = Depends(get_db)) -> dict:
    from app.wind_climatology.v3_service import variant
    try:
        return variant(db, spot_id, min_wind_kn=min_wind_kn, max_wind_kn=None if open_upper else max_wind_kn, direction_mode=direction_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/spots/{spot_id}/wind-climatology-v3/compare")
def compare_wind_climatology_v2_v3(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Structural pilot comparison without changing or ranking public V2."""
    from app.wind_climatology.v3_service import status as v3_status, variant
    v2 = db.scalar(select(WindClimatologyRun).where(WindClimatologyRun.spot_id == spot_id, WindClimatologyRun.is_active.is_(True)))
    try:
        v3 = variant(db, spot_id, min_wind_kn=15, max_wind_kn=20, direction_mode="all")
    except LookupError:
        v3 = None
    return {"v2": None if v2 is None else {"run_id": str(v2.id), "method": "pooled_daylight_hours", "sections": len((v2.public_data or {}).get("sections", []))}, "v3": None if v3 is None else {"run_id": v3["run_id"], "method": "yearly_session_reliability", "weeks": len(v3["variant"]["weeks"])}, "status": v3_status(db, spot_id), "public_effect": "none"}


@router.get("/shadow-study/status")
def shadow_study_status(db: Session = Depends(get_db)) -> dict:
    """Sanitized internal diagnostics; no provider payloads or weights."""
    study = db.scalar(
        select(WeatherShadowStudy).order_by(WeatherShadowStudy.started_at.desc())
    )
    if study is None:
        return {"status": "not_started"}
    run = db.scalar(
        select(WeatherShadowRun)
        .where(WeatherShadowRun.study_id == study.id)
        .order_by(WeatherShadowRun.issued_at.desc())
    )
    points = (
        db.scalar(
            select(func.count())
            .select_from(WeatherShadowForecast)
            .where(WeatherShadowForecast.run_id == run.id)
        )
        if run
        else 0
    )
    variants = (
        db.execute(
            select(WeatherShadowForecast.variant, func.count())
            .where(WeatherShadowForecast.run_id == run.id)
            .group_by(WeatherShadowForecast.variant)
        ).all()
        if run
        else []
    )
    diagnostics = run.diagnostics if run else {}
    shadow_job = db.scalar(
        select(ForecastProcessingJob)
        .where(ForecastProcessingJob.kind == "weather_shadow_cycle")
        .order_by(ForecastProcessingJob.created_at.desc())
    )
    return {
        "study_version": study.version,
        "status": study.status,
        "last_run": run.finished_at if run else None,
        "forecast_points": points,
        "variants": {key: count for key, count in variants},
        "provider_status": {
            "gfs": "collected" if run else "pending",
            "icon_eu": diagnostics.get("icon_eu", "pending"),
        },
        "observation_status": "blocked_observation_source",
        "requests": diagnostics.get("requests", 0),
        "bytes": diagnostics.get("bytes", 0),
        "scheduler_job": {
            "id": str(shadow_job.id),
            "status": shadow_job.status,
            "attempt_count": shadow_job.attempt_count,
            "retries": max(shadow_job.attempt_count - 1, 0),
            "model_run": shadow_job.options.get("model_run"),
            "event": shadow_job.diagnostics.get("event"),
            "reference_spots": shadow_job.diagnostics.get("reference_spots", 5),
            "forecast_points": shadow_job.diagnostics.get("forecast_points", 0),
            "provider_requests": shadow_job.diagnostics.get("provider_requests", 0),
            "provider_bytes": shadow_job.diagnostics.get("provider_bytes", 0),
            "observation_points": shadow_job.diagnostics.get("observation_points", 0),
            "station_blocker": "blocked_observation_source",
            "started_at": shadow_job.started_at,
            "finished_at": shadow_job.finished_at,
            "duration_seconds": (
                shadow_job.finished_at - shadow_job.started_at
            ).total_seconds()
            if shadow_job.started_at and shadow_job.finished_at
            else None,
            "next_model_run": (
                datetime.fromisoformat(shadow_job.options["model_run"])
                + timedelta(hours=6)
            ).isoformat()
            if shadow_job.options.get("model_run")
            else None,
            "public_effect": "none",
        }
        if shadow_job
        else None,
    }


class SectorIn(BaseModel):
    start_deg: float = Field(ge=0, lt=360)
    end_deg: float = Field(ge=0, lt=360)
    speed_factor: float = Field(ge=0.60, le=1.35)
    direction_offset_deg: float = Field(default=0, ge=-15, le=15)
    version: int = Field(default=1, ge=1)
    enabled: bool = True
    note: str | None = Field(default=None, max_length=500)


class ReferencePointIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    source: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=500)


class WeatherProfileIn(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    elevation_m: float | None = Field(default=None, ge=-500)
    coastal_normal_deg: float | None = Field(default=None, ge=0, lt=360)
    exposure: Literal["sheltered", "neutral", "exposed"] | None = None
    roughness_length_m: float | None = Field(default=None, gt=0)
    land_reference: ReferencePointIn | None = None
    water_reference: ReferencePointIn | None = None
    quality_tier: Literal["coordinates", "coastal", "extended", "advanced"] = (
        "coordinates"
    )
    physics_version: str = Field(default="wind-v1", max_length=40)
    reviewed: bool = False
    active: bool = True
    sectors: list[SectorIn] = Field(default_factory=list)
    expected_updated_at: datetime | None = None


class WeatherStationIn(BaseModel):
    provider: Literal["dwd", "dmi", "knmi"]
    provider_station_id: str = Field(min_length=1, max_length=80)
    name: str | None = Field(default=None, max_length=160)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    distance_km: float | None = Field(default=None, ge=0, le=100)
    active: bool = True


def _missing(body: WeatherProfileIn) -> list[str]:
    required = {
        "timezone": body.timezone,
        "elevation_m": body.elevation_m,
        "coastal_normal_deg": body.coastal_normal_deg,
    }
    return [name for name, value in required.items() if value is None or value == ""]


def _intervals(sector: SectorIn) -> list[tuple[float, float]]:
    if sector.start_deg <= sector.end_deg:
        return [(sector.start_deg, sector.end_deg)]
    return [(sector.start_deg, 360.0), (0.0, sector.end_deg)]


def _overlap(left: SectorIn, right: SectorIn) -> bool:
    return any(
        max(a, c) < min(b, d) or max(a, c) == min(b, d)
        for a, b in _intervals(left)
        for c, d in _intervals(right)
    )


def _view(profile: SpotWeatherProfile) -> dict:
    return {
        "id": str(profile.id),
        "spot_id": str(profile.spot_id),
        "timezone": profile.timezone,
        "elevation_m": profile.elevation_m,
        "coastal_normal_deg": profile.coastal_normal_deg,
        "exposure": profile.exposure,
        "roughness_length_m": profile.roughness_length_m,
        "land_reference": profile.land_reference,
        "water_reference": profile.water_reference,
        "quality_tier": profile.quality_tier,
        "physics_version": profile.physics_version,
        "reviewed_at": profile.reviewed_at.isoformat() if profile.reviewed_at else None,
        "updated_at": profile.updated_at.isoformat(),
        "active": profile.active,
        "sectors": [
            {
                "id": str(s.id),
                "start_deg": s.start_deg,
                "end_deg": s.end_deg,
                "speed_factor": s.speed_factor,
                "direction_offset_deg": s.direction_offset_deg,
                "version": s.version,
                "enabled": s.enabled,
                "note": s.note,
            }
            for s in profile.sectors
        ],
    }


def _load(db: Session, spot_id: uuid.UUID) -> SpotWeatherProfile | None:
    return db.scalar(
        select(SpotWeatherProfile)
        .where(SpotWeatherProfile.spot_id == spot_id)
        .options(selectinload(SpotWeatherProfile.sectors))
    )


@router.get("/profiles")
def list_profiles(
    country: str | None = None, state: str | None = None, db: Session = Depends(get_db)
) -> dict:
    stmt = (
        select(Spot, Region, SpotWeatherProfile)
        .outerjoin(Region, Spot.region_id == Region.id)
        .outerjoin(SpotWeatherProfile, SpotWeatherProfile.spot_id == Spot.id)
        .order_by(Spot.name)
    )
    if country:
        stmt = stmt.where(Region.country == country.upper())
    items = []
    for spot, region, profile in db.execute(stmt):
        missing = (
            []
            if profile and profile.quality_tier == "coordinates"
            else [
                name
                for name, value in {
                    "timezone": profile.timezone if profile else None,
                    "elevation_m": profile.elevation_m if profile else None,
                    "coastal_normal_deg": profile.coastal_normal_deg
                    if profile
                    else None,
                }.items()
                if value is None
            ]
        )
        profile_state = (
            "none"
            if profile is None
            else (
                "coordinates"
                if profile.quality_tier == "coordinates"
                else "advanced_released"
                if profile.quality_tier == "advanced" and profile.reviewed_at
                else "advanced_draft"
                if profile.quality_tier == "advanced"
                else "complete"
                if not missing
                else "incomplete"
            )
        )
        if state and profile_state != state:
            continue
        items.append(
            {
                "spot_id": str(spot.id),
                "spot_name": spot.name,
                "region": region.name if region else None,
                "country": region.country if region else None,
                "quality_tier": profile.quality_tier if profile else None,
                "profile_state": profile_state,
                "missing": missing,
                "active": profile.active if profile else False,
                "reviewed_at": profile.reviewed_at.isoformat()
                if profile and profile.reviewed_at
                else None,
                "updated_at": profile.updated_at.isoformat() if profile else None,
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/spots/{spot_id}/profile")
def get_profile(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    profile = _load(db, spot_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Weather profile not found")
    return _view(profile)


@router.put("/spots/{spot_id}/profile")
def put_profile(
    spot_id: uuid.UUID, body: WeatherProfileIn, db: Session = Depends(get_db)
) -> dict:
    if db.get(Spot, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    if body.timezone:
        try:
            ZoneInfo(body.timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(
                status_code=422, detail={"timezone": "Ungültige IANA-Zeitzone."}
            )
    missing = _missing(body)
    if body.quality_tier != "coordinates" and missing:
        raise HTTPException(
            status_code=422,
            detail={name: "Pflichtfeld für diese Qualitätsstufe." for name in missing},
        )
    enabled = [sector for sector in body.sectors if sector.enabled]
    for index, left in enumerate(enabled):
        if any(_overlap(left, right) for right in enabled[index + 1 :]):
            raise HTTPException(
                status_code=422,
                detail={
                    "sectors": "Aktive Windsektoren dürfen sich nicht überschneiden."
                },
            )
    if body.quality_tier == "advanced":
        raise HTTPException(
            status_code=422,
            detail={
                "quality_tier": "Advanced bleibt bis zur fachlichen Validierung deaktiviert."
            },
        )
    profile = _load(db, spot_id) or SpotWeatherProfile(spot_id=spot_id)
    if profile.id and body.expected_updated_at:
        loaded = (
            profile.updated_at
            if profile.updated_at.tzinfo
            else profile.updated_at.replace(tzinfo=timezone.utc)
        )
        expected = (
            body.expected_updated_at
            if body.expected_updated_at.tzinfo
            else body.expected_updated_at.replace(tzinfo=timezone.utc)
        )
        if loaded != expected:
            raise HTTPException(
                status_code=409,
                detail="Das Wetterprofil wurde zwischenzeitlich geändert.",
            )
    db.add(profile)
    for field in (
        "timezone",
        "elevation_m",
        "coastal_normal_deg",
        "exposure",
        "roughness_length_m",
        "land_reference",
        "water_reference",
        "quality_tier",
        "physics_version",
        "active",
    ):
        value = getattr(body, field)
        setattr(
            profile,
            field,
            value.model_dump() if isinstance(value, ReferencePointIn) else value,
        )
    profile.reviewed_at = datetime.now(timezone.utc) if body.reviewed else None
    profile.sectors.clear()
    profile.sectors.extend(
        SpotWeatherSector(**sector.model_dump()) for sector in body.sectors
    )
    db.flush()
    return _view(profile)


@router.get("/spots/{spot_id}/diagnostics")
def diagnostics(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        data = live_service.get_forecast_series(spot_id, 10, db=db)
        for day in data.get("days", []):
            for hour in day.get("hours", []):
                hour.pop("_weights", None)
        profile = db.scalar(
            select(SpotGeoProfileVersion).where(
                SpotGeoProfileVersion.spot_id == spot_id,
                SpotGeoProfileVersion.active.is_(True),
            )
        )
        snapshot = db.scalar(
            select(ForecastSnapshot).where(
                ForecastSnapshot.spot_id == spot_id, ForecastSnapshot.active.is_(True)
            )
        )
        latest_job = db.scalar(
            select(ForecastProcessingJob)
            .where(ForecastProcessingJob.spot_id == spot_id)
            .order_by(ForecastProcessingJob.created_at.desc())
        )
        shadow = db.scalar(
            select(SpotGeoShadowProfile).where(
                SpotGeoShadowProfile.spot_id == spot_id,
                SpotGeoShadowProfile.active_shadow.is_(True),
            )
        )
        shadow_sectors = (
            []
            if shadow is None
            else db.scalars(
                select(SpotGeoShadowSector)
                .where(SpotGeoShadowSector.shadow_profile_id == shadow.id)
                .order_by(SpotGeoShadowSector.sector_index)
            ).all()
        )
        data["publisher"] = {
            "geo_profile": None
            if profile is None
            else {
                "status": profile.status,
                "version": profile.version,
                "algorithm_version": profile.algorithm_version,
                "quality": profile.quality,
                "sources": profile.sources,
                "warnings": profile.warnings,
                "profile": profile.profile,
                "last_successful_at": profile.updated_at.isoformat(),
            },
            "snapshot": None
            if snapshot is None
            else {
                "id": str(snapshot.id),
                "generated_at": snapshot.generated_at.isoformat(),
                "valid_until": snapshot.valid_until.isoformat(),
                "quality_level": snapshot.quality_level,
                "fallback_status": snapshot.fallback_status,
                "internal": snapshot.internal,
            },
            "job": None if latest_job is None else _job_view(latest_job),
            "shadow_profile": None
            if shadow is None
            else {
                "id": str(shadow.id),
                "status": shadow.status,
                "profile_class": shadow.profile_class,
                "algorithm_version": shadow.algorithm_version,
                "analysis": shadow.analysis,
                "metrics": shadow.metrics,
                "warnings": shadow.warnings,
                "sectors": [
                    {
                        "index": s.sector_index,
                        "center_deg": s.center_deg,
                        "status": s.status,
                        "features": s.features,
                        "quality": s.quality,
                    }
                    for s in shadow_sectors
                ],
            },
        }
        return data
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")


def _job_view(job: ForecastProcessingJob) -> dict:
    return {
        "id": str(job.id),
        "spot_id": str(job.spot_id) if job.spot_id else None,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "options": job.options,
        "diagnostics": job.diagnostics,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def _run_job_in_new_session(job_id: uuid.UUID) -> None:
    from app.db.session import SessionLocal
    from app.forecast.publisher import run_job

    with SessionLocal() as session:
        run_job(session, job_id)


@router.post("/spots/{spot_id}/recalculate")
def recalculate(
    spot_id: uuid.UUID,
    background: BackgroundTasks,
    rebuild_profile: bool = False,
    db: Session = Depends(get_db),
    actor=Depends(require_role("admin", "curator")),
) -> dict:
    if db.get(Spot, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    from app.forecast.publisher import enqueue

    job = enqueue(
        db,
        spot_id,
        requested_by=getattr(actor, "email", None) or str(actor),
        rebuild_profile=rebuild_profile,
        reason="manual",
    )
    if job.status == "queued":
        background.add_task(_run_job_in_new_session, job.id)
    return _job_view(job)


@router.get("/jobs/{job_id}")
def job_status(job_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    job = db.get(ForecastProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Forecast job not found")
    return _job_view(job)


@router.get("/batch/preview")
def batch_preview(
    stale_only: bool = True,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    from app.forecast.geodata import CopernicusDemAdapter, WorldCoverAdapter
    from geoalchemy2.shape import to_shape

    spots = db.scalars(select(Spot).order_by(Spot.name).limit(limit)).all()
    items = []
    for spot in spots:
        profile = db.scalar(
            select(SpotGeoProfileVersion).where(
                SpotGeoProfileVersion.spot_id == spot.id,
                SpotGeoProfileVersion.active.is_(True),
            )
        )
        if stale_only and profile is not None and profile.status == "ready":
            continue
        point = to_shape(spot.location)
        items.append(
            {
                "spot_id": str(spot.id),
                "spot_name": spot.name,
                "profile_status": profile.status if profile else "missing",
                "profile_class": profile.quality if profile else None,
                "required_sources": ["cop-dem-glo30", "worldcover-2021"],
                "tiles": {
                    "dem": CopernicusDemAdapter.tile(point.y, point.x),
                    "worldcover": WorldCoverAdapter.tile(point.y, point.x),
                },
                "access_obstacles": ["CDSE CCM credentials/licence required"],
            }
        )
    return {"items": items, "total": len(items), "limit": limit}


@router.post("/batch/recalculate")
def batch_recalculate(
    background: BackgroundTasks,
    limit: int = Query(10, ge=1, le=10),
    db: Session = Depends(get_db),
    actor=Depends(require_role("admin")),
) -> dict:
    from app.forecast.publisher import enqueue

    spots = db.scalars(select(Spot).order_by(Spot.updated_at).limit(limit)).all()
    jobs = []
    for spot in spots:
        job = enqueue(
            db,
            spot.id,
            requested_by=getattr(actor, "email", None) or str(actor),
            rebuild_profile=True,
            reason="batch",
        )
        jobs.append(_job_view(job))
        if job.status == "queued":
            background.add_task(_run_job_in_new_session, job.id)
    return {"jobs": jobs, "count": len(jobs), "rate_limit": limit}


@router.put("/spots/{spot_id}/station")
def put_station(
    spot_id: uuid.UUID, body: WeatherStationIn, db: Session = Depends(get_db)
) -> dict:
    if db.get(Spot, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    station = db.scalar(
        select(WeatherStation).where(
            WeatherStation.spot_id == spot_id,
            WeatherStation.provider == body.provider,
            WeatherStation.provider_station_id == body.provider_station_id,
        )
    ) or WeatherStation(
        spot_id=spot_id,
        provider=body.provider,
        provider_station_id=body.provider_station_id,
    )
    for field, value in body.model_dump().items():
        setattr(station, field, value)
    db.add(station)
    db.commit()
    db.refresh(station)
    return {"id": str(station.id), **body.model_dump()}


@router.get("/spots/{spot_id}/calibration")
def get_calibration(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    stations = db.scalars(
        select(WeatherStation).where(WeatherStation.spot_id == spot_id)
    ).all()
    rows = db.scalars(
        select(WeatherModelCalibration).where(
            WeatherModelCalibration.spot_id == spot_id
        )
    ).all()
    return {
        "stations": [
            {
                "id": str(s.id),
                "provider": s.provider,
                "provider_station_id": s.provider_station_id,
                "name": s.name,
                "distance_km": s.distance_km,
                "active": s.active,
            }
            for s in stations
        ],
        "models": [
            {
                "model_id": r.model_id,
                "lead_bucket": r.lead_bucket,
                "sample_count": r.sample_count,
                "bias_ms": r.bias_ms,
                "mae_ms": r.mae_ms,
                "weight_multiplier": r.weight_multiplier,
            }
            for r in rows
        ],
    }


@router.post("/spots/{spot_id}/station/auto")
def auto_station(
    spot_id: uuid.UUID,
    provider: Literal["dwd", "dmi"] = "dwd",
    db: Session = Depends(get_db),
) -> dict:
    """Select the nearest wind-capable official station; an operator still sees the choice."""
    from app.config import get_settings
    from app.weather.providers.common import nearest_stations
    from app.weather.providers import dmi, dwd

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    lat, lon = live_service._spot_coords(spot)
    catalogue = dwd.fetch_stations() if provider == "dwd" else dmi.fetch_stations()
    candidates = nearest_stations(
        lat, lon, catalogue, limit=3, max_km=get_settings().weather_station_match_max_km
    )
    if not candidates:
        raise HTTPException(
            status_code=404, detail="No suitable official wind station in range"
        )
    selected, distance = candidates[0]
    station = db.scalar(
        select(WeatherStation).where(
            WeatherStation.spot_id == spot_id,
            WeatherStation.provider == provider,
            WeatherStation.provider_station_id == selected.station_id,
        )
    ) or WeatherStation(
        spot_id=spot_id, provider=provider, provider_station_id=selected.station_id
    )
    station.name, station.latitude, station.longitude = (
        selected.name,
        selected.latitude,
        selected.longitude,
    )
    station.distance_km, station.active = round(distance, 3), True
    db.add(station)
    db.commit()
    return {
        "selected": {
            "station_id": selected.station_id,
            "name": selected.name,
            "distance_km": round(distance, 2),
        },
        "candidates": [
            {
                "station_id": item.station_id,
                "name": item.name,
                "distance_km": round(km, 2),
            }
            for item, km in candidates
        ],
    }
