"""Authenticated weather-profile management and volatile diagnostics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.deps import require_role
from app.db.session import get_db
from app.live import service as live_service
from app.models import Region, Spot, SpotWeatherProfile, SpotWeatherSector, WeatherModelCalibration, WeatherStation

router = APIRouter(prefix="/admin/weather", tags=["admin-weather"], dependencies=[Depends(require_role("admin", "curator"))])


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
    quality_tier: Literal["coordinates", "coastal", "extended", "advanced"] = "coordinates"
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
    return any(max(a, c) < min(b, d) or max(a, c) == min(b, d) for a, b in _intervals(left) for c, d in _intervals(right))


def _view(profile: SpotWeatherProfile) -> dict:
    return {
        "id": str(profile.id), "spot_id": str(profile.spot_id),
        "timezone": profile.timezone, "elevation_m": profile.elevation_m,
        "coastal_normal_deg": profile.coastal_normal_deg, "exposure": profile.exposure,
        "roughness_length_m": profile.roughness_length_m,
        "land_reference": profile.land_reference, "water_reference": profile.water_reference,
        "quality_tier": profile.quality_tier, "physics_version": profile.physics_version,
        "reviewed_at": profile.reviewed_at.isoformat() if profile.reviewed_at else None,
        "updated_at": profile.updated_at.isoformat(),
        "active": profile.active,
        "sectors": [{
            "id": str(s.id), "start_deg": s.start_deg, "end_deg": s.end_deg,
            "speed_factor": s.speed_factor, "direction_offset_deg": s.direction_offset_deg,
            "version": s.version, "enabled": s.enabled, "note": s.note,
        } for s in profile.sectors],
    }


def _load(db: Session, spot_id: uuid.UUID) -> SpotWeatherProfile | None:
    return db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id).options(selectinload(SpotWeatherProfile.sectors)))


@router.get("/profiles")
def list_profiles(country: str | None = None, state: str | None = None, db: Session = Depends(get_db)) -> dict:
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
        missing = [] if profile and profile.quality_tier == "coordinates" else [
            name for name, value in {
                "timezone": profile.timezone if profile else None,
                "elevation_m": profile.elevation_m if profile else None,
                "coastal_normal_deg": profile.coastal_normal_deg if profile else None,
            }.items() if value is None
        ]
        profile_state = "none" if profile is None else (
            "coordinates" if profile.quality_tier == "coordinates" else
            "advanced_released" if profile.quality_tier == "advanced" and profile.reviewed_at else
            "advanced_draft" if profile.quality_tier == "advanced" else
            "complete" if not missing else "incomplete"
        )
        if state and profile_state != state:
            continue
        items.append({
            "spot_id": str(spot.id), "spot_name": spot.name,
            "region": region.name if region else None, "country": region.country if region else None,
            "quality_tier": profile.quality_tier if profile else None,
            "profile_state": profile_state, "missing": missing,
            "active": profile.active if profile else False,
            "reviewed_at": profile.reviewed_at.isoformat() if profile and profile.reviewed_at else None,
            "updated_at": profile.updated_at.isoformat() if profile else None,
        })
    return {"items": items, "total": len(items)}


@router.get("/spots/{spot_id}/profile")
def get_profile(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    profile = _load(db, spot_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Weather profile not found")
    return _view(profile)


@router.put("/spots/{spot_id}/profile")
def put_profile(spot_id: uuid.UUID, body: WeatherProfileIn, db: Session = Depends(get_db)) -> dict:
    if db.get(Spot, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    if body.timezone:
        try:
            ZoneInfo(body.timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=422, detail={"timezone": "Ungültige IANA-Zeitzone."})
    missing = _missing(body)
    if body.quality_tier != "coordinates" and missing:
        raise HTTPException(status_code=422, detail={name: "Pflichtfeld für diese Qualitätsstufe." for name in missing})
    enabled = [sector for sector in body.sectors if sector.enabled]
    for index, left in enumerate(enabled):
        if any(_overlap(left, right) for right in enabled[index + 1:]):
            raise HTTPException(status_code=422, detail={"sectors": "Aktive Windsektoren dürfen sich nicht überschneiden."})
    if body.quality_tier == "advanced":
        raise HTTPException(status_code=422, detail={"quality_tier": "Advanced bleibt bis zur fachlichen Validierung deaktiviert."})
    profile = _load(db, spot_id) or SpotWeatherProfile(spot_id=spot_id)
    if profile.id and body.expected_updated_at:
        loaded = profile.updated_at if profile.updated_at.tzinfo else profile.updated_at.replace(tzinfo=timezone.utc)
        expected = body.expected_updated_at if body.expected_updated_at.tzinfo else body.expected_updated_at.replace(tzinfo=timezone.utc)
        if loaded != expected:
            raise HTTPException(status_code=409, detail="Das Wetterprofil wurde zwischenzeitlich geändert.")
    db.add(profile)
    for field in ("timezone", "elevation_m", "coastal_normal_deg", "exposure", "roughness_length_m", "land_reference", "water_reference", "quality_tier", "physics_version", "active"):
        value = getattr(body, field)
        setattr(profile, field, value.model_dump() if isinstance(value, ReferencePointIn) else value)
    profile.reviewed_at = datetime.now(timezone.utc) if body.reviewed else None
    profile.sectors.clear()
    profile.sectors.extend(SpotWeatherSector(**sector.model_dump()) for sector in body.sectors)
    db.flush()
    return _view(profile)


@router.get("/spots/{spot_id}/diagnostics")
def diagnostics(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return live_service.get_forecast_series(spot_id, 10, db=db)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")


@router.put("/spots/{spot_id}/station")
def put_station(spot_id: uuid.UUID, body: WeatherStationIn, db: Session = Depends(get_db)) -> dict:
    if db.get(Spot, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    station = db.scalar(select(WeatherStation).where(
        WeatherStation.spot_id == spot_id, WeatherStation.provider == body.provider,
        WeatherStation.provider_station_id == body.provider_station_id,
    )) or WeatherStation(spot_id=spot_id, provider=body.provider, provider_station_id=body.provider_station_id)
    for field, value in body.model_dump().items():
        setattr(station, field, value)
    db.add(station)
    db.commit()
    db.refresh(station)
    return {"id": str(station.id), **body.model_dump()}


@router.get("/spots/{spot_id}/calibration")
def get_calibration(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    stations = db.scalars(select(WeatherStation).where(WeatherStation.spot_id == spot_id)).all()
    rows = db.scalars(select(WeatherModelCalibration).where(WeatherModelCalibration.spot_id == spot_id)).all()
    return {
        "stations": [{"id": str(s.id), "provider": s.provider, "provider_station_id": s.provider_station_id,
                      "name": s.name, "distance_km": s.distance_km, "active": s.active} for s in stations],
        "models": [{"model_id": r.model_id, "lead_bucket": r.lead_bucket, "sample_count": r.sample_count,
                    "bias_ms": r.bias_ms, "mae_ms": r.mae_ms, "weight_multiplier": r.weight_multiplier} for r in rows],
    }


@router.post("/spots/{spot_id}/station/auto")
def auto_station(spot_id: uuid.UUID, provider: Literal["dwd", "dmi"] = "dwd", db: Session = Depends(get_db)) -> dict:
    """Select the nearest wind-capable official station; an operator still sees the choice."""
    from app.config import get_settings
    from app.weather.providers.common import nearest_stations
    from app.weather.providers import dmi, dwd

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    lat, lon = live_service._spot_coords(spot)
    catalogue = dwd.fetch_stations() if provider == "dwd" else dmi.fetch_stations()
    candidates = nearest_stations(lat, lon, catalogue, limit=3,
                                  max_km=get_settings().weather_station_match_max_km)
    if not candidates:
        raise HTTPException(status_code=404, detail="No suitable official wind station in range")
    selected, distance = candidates[0]
    station = db.scalar(select(WeatherStation).where(
        WeatherStation.spot_id == spot_id, WeatherStation.provider == provider,
        WeatherStation.provider_station_id == selected.station_id,
    )) or WeatherStation(spot_id=spot_id, provider=provider, provider_station_id=selected.station_id)
    station.name, station.latitude, station.longitude = selected.name, selected.latitude, selected.longitude
    station.distance_km, station.active = round(distance, 3), True
    db.add(station)
    db.commit()
    return {
        "selected": {"station_id": selected.station_id, "name": selected.name, "distance_km": round(distance, 2)},
        "candidates": [{"station_id": item.station_id, "name": item.name, "distance_km": round(km, 2)}
                       for item, km in candidates],
    }
