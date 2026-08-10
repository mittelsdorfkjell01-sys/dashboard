"""Shared observation-provider contracts and station matching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
