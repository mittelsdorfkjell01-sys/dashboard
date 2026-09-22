"""Provider-independent physical-station identity and duplicate grouping."""

from __future__ import annotations

from collections import defaultdict
import math

from app.weather.providers.common import haversine_km


def _text(value) -> str | None:
    cleaned = str(value or "").strip().upper()
    return cleaned or None


def _provider_id(station) -> tuple[str, str] | None:
    provider = _text(getattr(station, "provider", None))
    identifier = _text(
        getattr(station, "provider_station_id", None)
        or getattr(station, "station_id", None)
    )
    return (provider, identifier) if provider and identifier else None


def station_identity_keys(station) -> tuple[str, ...]:
    """Stable strong identifiers; all are compared before spatial matching."""
    keys = []
    provider_id = _provider_id(station)
    if provider_id:
        keys.append(f"provider:{provider_id[0]}:{provider_id[1]}")
    wigos = _text(getattr(station, "wigos_id", None))
    icao = _text(getattr(station, "icao_id", None))
    if wigos:
        keys.append(f"wigos:{wigos}")
    if icao:
        keys.append(f"icao:{icao}")
    if getattr(station, "identity_review_status", "unreviewed") == "passed":
        physical = _text(getattr(station, "physical_station_group", None))
        if physical:
            keys.append(f"reviewed_physical:{physical}")
    return tuple(keys)


def _coordinate(station) -> tuple[float, float] | None:
    try:
        latitude = float(getattr(station, "latitude"))
        longitude = float(getattr(station, "longitude"))
    except (AttributeError, TypeError, ValueError):
        return None
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    return latitude, longitude


def _same_spatial_station(
    left,
    right,
    *,
    spatial_threshold_km: float,
    elevation_threshold_m: float,
) -> bool:
    left_coordinate, right_coordinate = _coordinate(left), _coordinate(right)
    if left_coordinate is None or right_coordinate is None:
        return False
    distance = haversine_km(*left_coordinate, *right_coordinate)
    if distance > spatial_threshold_km:
        return False
    left_elevation = getattr(left, "elevation_m", None)
    right_elevation = getattr(right, "elevation_m", None)
    if left_elevation is None or right_elevation is None:
        # With no vertical evidence, require near-identical coordinates.
        return distance <= min(0.1, spatial_threshold_km)
    try:
        return abs(float(left_elevation) - float(right_elevation)) <= elevation_threshold_m
    except (TypeError, ValueError):
        return False


def duplicate_station_groups(
    stations: list,
    *,
    spatial_threshold_km: float = 0.5,
    elevation_threshold_m: float = 50.0,
) -> list[tuple[int, ...]]:
    """Return confirmed strong-ID groups; proximity alone never merges records."""
    parents = list(range(len(stations)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    strong_keys: dict[str, int] = {}
    for index, station in enumerate(stations):
        # ICAO and a bare WIGOS identify a site, not necessarily the same wind
        # sensor. They remain holdout exclusion hints, never auto-confirmation.
        keys = [key for key in station_identity_keys(station)
                if key.startswith(("provider:", "reviewed_physical:"))]
        sensor = (getattr(station, "sensor_metadata", None) or {}).get("sensor_instance_id")
        if sensor and (getattr(station, "sensor_metadata", None) or {}).get("official_crosswalk"):
            wigos = _text(getattr(station, "wigos_id", None))
            if wigos:
                keys.append(f"official_sensor:{wigos}:{_text(sensor)}")
        for key in keys:
            if key in strong_keys:
                union(index, strong_keys[key])
            else:
                strong_keys[key] = index

    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(stations)):
        grouped[find(index)].append(index)
    return [tuple(values) for values in grouped.values() if len(values) > 1]


def spatial_duplicate_candidates(stations: list, *, spatial_threshold_km: float = 0.5,
                                 elevation_threshold_m: float = 50.0) -> list[tuple[int, int]]:
    """Unreviewed proximity hints; must not establish physical identity."""
    confirmed = {frozenset((left, right)) for group in duplicate_station_groups(stations)
                 for left in group for right in group if left < right}
    return [(left, right) for left in range(len(stations)) for right in range(left + 1, len(stations))
            if frozenset((left, right)) not in confirmed and _same_spatial_station(
                stations[left], stations[right], spatial_threshold_km=spatial_threshold_km,
                elevation_threshold_m=elevation_threshold_m)]


def possible_duplicate_candidates(stations: list) -> list[tuple[int, int, tuple[str, ...]]]:
    """Unconfirmed cross-provider hints; never establish identity by themselves."""
    confirmed = {frozenset((left, right)) for group in duplicate_station_groups(stations)
                 for left in group for right in group if left < right}
    spatial = set(spatial_duplicate_candidates(stations))
    output = []
    for left in range(len(stations)):
        for right in range(left + 1, len(stations)):
            if frozenset((left, right)) in confirmed:
                continue
            reasons = []
            left_keys, right_keys = set(station_identity_keys(stations[left])), set(station_identity_keys(stations[right]))
            shared = left_keys.intersection(right_keys)
            if any(key.startswith("wigos:") for key in shared):
                reasons.append("shared_wigos_sensor_unproven")
            if any(key.startswith("icao:") for key in shared):
                reasons.append("shared_icao_sensor_unproven")
            if (left, right) in spatial:
                reasons.append("spatial_proximity")
            if reasons:
                output.append((left, right, tuple(reasons)))
    return output


def station_display_identity(station) -> str:
    provider_id = _provider_id(station)
    if provider_id:
        return f"{provider_id[0].lower()}:{provider_id[1]}"
    keys = station_identity_keys(station)
    return keys[0].lower() if keys else f"station:{id(station)}"
