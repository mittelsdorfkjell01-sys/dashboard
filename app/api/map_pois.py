"""Public, cache-backed POIs for the spot locator map."""

from __future__ import annotations

import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, HttpUrl

from app.config import get_settings
from app.community.ratelimit import RateLimiter, enforce, get_rate_limiter
from app.live.cache import Cache, default_cache
from app.map_pois import PoiClient, PoiProviderError, get_poi_client

router = APIRouter(prefix="/map", tags=["map"])


class MapPoi(BaseModel):
    id: str
    category: Literal["parking", "cafe", "bar", "surf_school", "campsite"]
    name: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    distance_m: int = Field(ge=0)
    osm_url: HttpUrl
    # Details as mapped in OpenStreetMap; empty means "not recorded".
    opening_hours: str | None = None
    website: HttpUrl | None = None
    phone: str | None = None
    address: str | None = None
    cuisine: list[str] = Field(default_factory=list)
    outdoor_seating: bool | None = None
    wheelchair: Literal["yes", "limited", "no"] | None = None
    fee: bool | None = None
    capacity: int | None = Field(default=None, ge=0)
    takeaway: Literal["yes", "no", "only"] | None = None
    wifi: bool | None = None
    vegetarian: Literal["yes", "no", "only", "limited"] | None = None
    vegan: Literal["yes", "no", "only", "limited"] | None = None
    dogs: Literal["yes", "no", "leashed"] | None = None
    card_payment: bool | None = None
    toilets: bool | None = None
    reservation: Literal["yes", "no", "required", "recommended"] | None = None
    smoking: Literal["yes", "no", "outside", "separated", "isolated"] | None = None
    instagram: HttpUrl | None = None
    check_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}(?:-\d{2})?$")


class MapPoisResponse(BaseModel):
    items: list[MapPoi]
    source: Literal["OpenStreetMap"] = "OpenStreetMap"
    attribution: str = "© OpenStreetMap-Mitwirkende"
    incomplete: bool = True


def get_poi_cache() -> Cache:
    return default_cache()


@router.get("/pois", response_model=MapPoisResponse)
def map_pois(
    request: Request,
    response: Response,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius_m: int = Query(default=3_000, ge=500, le=5_000),
    cache: Cache = Depends(get_poi_cache),
    client: PoiClient = Depends(get_poi_client),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> MapPoisResponse:
    enforce(limiter, request, "map-pois", limit=60, window=3_600)
    settings = get_settings()
    cache_key = f"osm-poi:v3:{lat:.4f}:{lon:.4f}:{radius_m}"
    response.headers["Cache-Control"] = (
        "public, max-age=3600, s-maxage=86400, "
        "stale-while-revalidate=604800, stale-if-error=604800"
    )
    if cached := cache.get(cache_key):
        return MapPoisResponse.model_validate(cached)

    lock_key = f"{cache_key}:lock"
    lock_token = secrets.token_urlsafe(16)
    if not cache.acquire_lock(lock_key, lock_token, 15):
        raise HTTPException(
            status_code=503,
            detail="Orte werden bereits aktualisiert. Bitte gleich erneut versuchen.",
            headers={"Retry-After": "5", "Cache-Control": "no-store"},
        )
    try:
        items = client.nearby(lat, lon, radius_m)
        result = MapPoisResponse(items=[MapPoi.model_validate(item) for item in items])
        cache.set(cache_key, result.model_dump(mode="json"), settings.osm_poi_cache_ttl_seconds)
        return result
    except PoiProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail="Orte aus OpenStreetMap sind momentan nicht verfügbar.",
            headers={"Retry-After": "30", "Cache-Control": "no-store"},
        ) from exc
    finally:
        cache.release_lock(lock_key, lock_token)
