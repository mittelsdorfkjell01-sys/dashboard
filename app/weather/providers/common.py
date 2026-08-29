"""Shared observation-provider contracts and station matching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math


@dataclass(frozen=True)
class ObservationStation:
    provider: str
    station_id: str
    name: str
    latitude: float
    longitude: float
    elevation_m: float | None = None
    parameters: tuple[str, ...] = ()


@dataclass(frozen=True)
class WindObservation:
    observed_at: datetime
    wind_speed_ms: float
    wind_direction_deg: float | None = None
    wind_gust_ms: float | None = None
    quality: int | None = None


@dataclass(frozen=True)
class NormalizedObservation:
    provider: str
    station_id: str
    observed_at: datetime
    wind_speed_ms: float | None
    wind_direction_deg: float | None
    wind_gust_ms: float | None
    provider_quality: str | None
    fetched_at: datetime
    import_status: str
    data_issues: tuple[str, ...] = ()


def normalize_observation(*, provider, station_id, observed_at, wind_speed_ms,
                          wind_direction_deg=None, wind_gust_ms=None,
                          provider_quality=None, fetched_at=None) -> NormalizedObservation:
    issues = []
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        issues.append("observed_at:naive")
    observed = observed_at.replace(tzinfo=timezone.utc) if observed_at.tzinfo is None else observed_at.astimezone(timezone.utc)
    speed = float(wind_speed_ms) if isinstance(wind_speed_ms, (int, float)) and math.isfinite(wind_speed_ms) else None
    direction = float(wind_direction_deg) if isinstance(wind_direction_deg, (int, float)) and math.isfinite(wind_direction_deg) else None
    gust = float(wind_gust_ms) if isinstance(wind_gust_ms, (int, float)) and math.isfinite(wind_gust_ms) else None
    if speed is None or not 0 <= speed <= 75: issues.append("wind_speed:invalid")
    if direction is not None and not 0 <= direction < 360: issues.append("wind_direction:invalid")
    if gust is not None and (gust < 0 or speed is not None and gust < speed): issues.append("wind_gust:invalid")
    status = "accepted" if not issues else "rejected"
    return NormalizedObservation(
        provider=str(provider), station_id=str(station_id), observed_at=observed,
        wind_speed_ms=speed, wind_direction_deg=direction, wind_gust_ms=gust,
        provider_quality=None if provider_quality is None else str(provider_quality),
        fetched_at=fetched_at or datetime.now(timezone.utc), import_status=status,
        data_issues=tuple(issues),
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_stations(
    latitude: float, longitude: float, stations: list[ObservationStation], *, limit: int = 3, max_km: float = 100
) -> list[tuple[ObservationStation, float]]:
    """Return deterministic nearest wind-capable stations inside a safe radius."""
    ranked = []
    for station in stations:
        if station.parameters and "wind_speed" not in station.parameters:
            continue
        distance = haversine_km(latitude, longitude, station.latitude, station.longitude)
        if distance <= max_km:
            ranked.append((station, distance))
    return sorted(ranked, key=lambda item: (item[1], item[0].station_id))[:max(1, limit)]
