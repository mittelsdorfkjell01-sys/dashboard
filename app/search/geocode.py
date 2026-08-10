"""Geocoding seam + point/area classification.

Uses the Open-Meteo Geocoding API behind a :class:`Geocoder` protocol so tests
inject a fake. The key job is classifying a hit as a **point** (a town/place — we
search *around* it but never surface the place itself as a result) or an **area**
(country/island/admin region — we query its **bounds**, not a radius around the
centre).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# GeoNames feature-code prefixes that denote an *area* (query by bounds).
_AREA_PREFIXES = ("PCL", "ADM", "ISL", "RGN", "CONT", "AREA", "TERR")

# Approximate half-size (degrees) for an area bbox when the geocoder gives no
# bounding box (the Open-Meteo geocoder never does). Sized so the box actually
# covers the spots that belong to the area: a large Mediterranean/Atlantic island
# like Sardinia or Sicily spans ~2° of latitude, so a 0.6° island box missed all
# of its spots — an area search that returns nothing is worse than one that also
# includes a little surrounding sea (empty of spots anyway; ranking sorts by
# distance regardless). An explicit ``bbox`` from the geocoder always wins.
_AREA_HALFSIZE_DEG = {
    "PCL": 5.0,   # country
    "ADM": 1.5,   # admin division
    "ISL": 2.0,   # island (large Med/Atlantic islands span ~2° lat)
    "RGN": 1.5,
    "CONT": 20.0,
    "AREA": 1.5,
    "TERR": 2.0,
}
_DEFAULT_HALFSIZE_DEG = 1.5


@dataclass
class GeocodeResult:
    name: str
    lat: float
    lon: float
    feature_code: str | None = None
    country: str | None = None
    # Optional explicit bounding box [min_lon, min_lat, max_lon, max_lat].
    bbox: list[float] | None = None


class Geocoder(Protocol):
    def geocode(self, query: str) -> list[GeocodeResult]: ...


class HttpOpenMeteoGeocoder:
    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def geocode(self, query: str) -> list[GeocodeResult]:
        import httpx

        resp = httpx.get(
            GEOCODE_URL,
            params={"name": query, "count": 5, "language": "en", "format": "json"},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        out = []
        for r in resp.json().get("results", []) or []:
            out.append(
                GeocodeResult(
                    name=r.get("name", ""),
                    lat=r["latitude"],
                    lon=r["longitude"],
                    feature_code=r.get("feature_code"),
                    country=r.get("country_code"),
                )
            )
        return out


def _is_area(result: GeocodeResult) -> bool:
    code = (result.feature_code or "").upper()
    return any(code.startswith(p) for p in _AREA_PREFIXES)


def _derive_bounds(result: GeocodeResult) -> dict:
    if result.bbox:
        min_lon, min_lat, max_lon, max_lat = result.bbox
    else:
        code = (result.feature_code or "")[:3].upper()
        h = _AREA_HALFSIZE_DEG.get(code, _DEFAULT_HALFSIZE_DEG)
        min_lon, min_lat = result.lon - h, result.lat - h
        max_lon, max_lat = result.lon + h, result.lat + h
    return {
        "min_lon": round(min_lon, 6),
        "min_lat": round(min_lat, 6),
        "max_lon": round(max_lon, 6),
        "max_lat": round(max_lat, 6),
    }


def classify_geocode(
    query: str, *, geocoder: Geocoder, country: str | None = None,
) -> dict | None:
    """Classify the top geocoding hit as a point or an area.

    Returns ``{"type": "point"|"area", "point": {lat, lon}, "bounds": {...}|None,
    "name": str}`` or ``None`` when nothing is found. A *place* is never returned
    as a search result by the orchestration — it only drives a spatial query.
    """
    results = geocoder.geocode(query)
    if not results:
        return None
    if country:
        matching = [r for r in results if (r.country or "").upper() == country.upper()]
        if matching:
            results = matching
        r = next((candidate for candidate in results if _is_area(candidate)), results[0])
    else:
        r = results[0]
    point = {"lat": r.lat, "lon": r.lon}
    if _is_area(r):
        return {"type": "area", "point": point, "bounds": _derive_bounds(r), "name": r.name}
    return {"type": "point", "point": point, "bounds": None, "name": r.name}
