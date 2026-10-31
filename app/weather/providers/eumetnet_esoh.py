"""EUMETNET MeteoGate E-SOH surface-wind observation adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import math
import re

import httpx

from app.weather.providers.common import (
    NormalizedObservation,
    ObservationStation,
    deduplicate_observations,
    normalize_observation,
)


ESOH_BASE = (
    "https://api.meteogate.eu/"
    "eu-eumetnet-surface-observations/collections/observations"
)
ESOH_LICENSE = "CC BY 4.0"
OSCAR_SEARCH_URL = "https://oscar.wmo.int/surface/rest/api/search/station"
ESOH_PROVENANCE = {
    "source": "EUMETNET MeteoGate E-SOH",
    "collection": "Meteorological Observations in Europe",
    "source_url": ESOH_BASE,
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "commercial_reuse": True,
    "attribution_required": True,
}
_PARAMETER = re.compile(
    r"^(?P<standard>[^:]+):(?P<level>-?[0-9.]+):(?P<method>[^:]+):(?P<period>PT[^:]+)$"
)
_PAIR_PREFERENCE = (
    ("mean", "PT10M"),
    ("point", "PT10M"),
    ("mean", "PT2M"),
    ("point", "PT0S"),
    ("mean", "PT1H"),
    ("point", "PT1H"),
)

_TERRITORY_CODES = {
    "Albania": "AL", "Algeria": "DZ", "Andorra": "AD", "Armenia": "AM",
    "Austria": "AT", "Azerbaijan": "AZ", "Belarus": "BY", "Belgium": "BE",
    "Bosnia and Herzegovina": "BA", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czechia": "CZ", "Denmark": "DK", "Egypt": "EG",
    "Estonia": "EE", "Faroe Islands": "FO", "Finland": "FI", "France": "FR",
    "Georgia": "GE", "Germany": "DE", "Gibraltar": "GI", "Greece": "GR",
    "Greenland": "GL", "Hungary": "HU", "Iceland": "IS", "Ireland": "IE",
    "Israel": "IL", "Italy": "IT", "Jordan": "JO", "Kosovo": "XK",
    "Latvia": "LV", "Lebanon": "LB", "Liechtenstein": "LI", "Lithuania": "LT",
    "Luxembourg": "LU", "Malta": "MT", "Moldova": "MD", "Monaco": "MC",
    "Montenegro": "ME", "Morocco": "MA", "Netherlands": "NL",
    "North Macedonia": "MK", "Norway": "NO", "Poland": "PL", "Portugal": "PT",
    "Romania": "RO", "Russian Federation": "RU", "San Marino": "SM",
    "Serbia": "RS", "Slovakia": "SK", "Slovenia": "SI", "Spain": "ES",
    "Sweden": "SE", "Switzerland": "CH", "Tunisia": "TN", "Türkiye": "TR",
    "Turkey": "TR", "Ukraine": "UA", "United Kingdom": "GB",
    "Vatican City": "VA",
}


def _number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parameter_parts(value: str) -> tuple[str, float, str, str] | None:
    match = _PARAMETER.match(str(value))
    if not match:
        return None
    level = _number(match.group("level"))
    if level is None:
        return None
    return match.group("standard"), level, match.group("method"), match.group("period")


def _period_seconds(value: str | None) -> int | None:
    if not value or not value.startswith("PT"):
        return None
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return None
    hours, minutes, seconds = (int(item or 0) for item in match.groups())
    total = hours * 3600 + minutes * 60 + seconds
    return total or None


def select_wind_parameters(parameters: list[str] | tuple[str, ...]) -> dict | None:
    """Choose one comparable 10 m speed/direction pair and an optional gust."""
    parsed = []
    for raw in parameters:
        parts = _parameter_parts(raw)
        if parts is not None and math.isclose(parts[1], 10.0, abs_tol=0.01):
            parsed.append((str(raw), *parts))
    by_key: dict[tuple[str, str], dict[str, str]] = {}
    for raw, standard, _level, method, period in parsed:
        by_key.setdefault((method, period), {})[standard] = raw
    chosen = None
    for key in _PAIR_PREFERENCE:
        values = by_key.get(key, {})
        if {"wind_speed", "wind_from_direction"}.issubset(values):
            chosen = (key, values)
            break
    if chosen is None:
        for key in sorted(by_key):
            values = by_key[key]
            if {"wind_speed", "wind_from_direction"}.issubset(values):
                chosen = (key, values)
                break
    if chosen is None:
        return None
    (method, period), values = chosen
    gust_candidates = [
        (raw, candidate_method, candidate_period)
        for raw, standard, _level, candidate_method, candidate_period in parsed
        if standard == "wind_speed_of_gust"
    ]
    gust_candidates.sort(key=lambda item: (
        item[1] != "maximum",
        item[2] != period,
        item[2],
        item[0],
    ))
    return {
        "speed_parameter": values["wind_speed"],
        "direction_parameter": values["wind_from_direction"],
        "gust_parameter": gust_candidates[0][0] if gust_candidates else None,
        "method": method,
        "period": period,
        "period_seconds": _period_seconds(period),
        "measurement_height_m": 10.0,
    }


def parse_station_catalog(
    payload: dict,
    *,
    received_at: datetime | None = None,
) -> list[ObservationStation]:
    received = received_at or datetime.now(timezone.utc)
    output = []
    for feature in payload.get("features") or []:
        if not isinstance(feature, dict):
            continue
        props, geometry = feature.get("properties") or {}, feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        station_id = str(feature.get("id") or "").strip()
        selected = select_wind_parameters(tuple(props.get("parameter-name") or ()))
        longitude = _number(coordinates[0]) if len(coordinates) >= 2 else None
        latitude = _number(coordinates[1]) if len(coordinates) >= 2 else None
        if (
            not station_id
            or len(station_id) > 80
            or selected is None
            or latitude is None
            or longitude is None
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            continue
        output.append(ObservationStation(
            provider="eumetnet_esoh",
            station_id=station_id,
            name=str(props.get("name") or station_id),
            latitude=latitude,
            longitude=longitude,
            parameters=tuple(props.get("parameter-name") or ()),
            wigos_id=station_id,
            measurement_height_m=10.0,
            license=ESOH_LICENSE,
            provenance={**ESOH_PROVENANCE, "station_detail": props.get("detail")},
            typical_interval_minutes=max(1, (selected.get("period_seconds") or 600) // 60),
            commercial_reuse=True,
            attribution_required=True,
            operator="EUMETNET member",
            station_type="surface_observation",
            sensor_metadata={"esoh_wind": selected},
            source_url=str(props.get("detail") or f"{ESOH_BASE}/locations/{station_id}"),
            raw_payload=feature,
            received_at=received,
        ))
    return sorted(output, key=lambda item: item.station_id)


def fetch_stations(*, timeout: float = 30.0) -> list[ObservationStation]:
    response = httpx.get(f"{ESOH_BASE}/locations", params={"f": "json"}, timeout=timeout)
    response.raise_for_status()
    return parse_station_catalog(response.json())


def _oscar_metadata(station: ObservationStation, *, timeout: float) -> ObservationStation:
    """Add authoritative country and station identity metadata from OSCAR."""
    response = httpx.get(
        OSCAR_SEARCH_URL,
        params={"wigosId": station.wigos_id or station.station_id},
        timeout=timeout,
    )
    response.raise_for_status()
    matches = response.json().get("stationSearchResults") or []
    match = next(
        (item for item in matches if item.get("wigosId") == (station.wigos_id or station.station_id)),
        None,
    )
    if match is None:
        return station
    territory = str(match.get("territory") or "").strip()
    country_code = _TERRITORY_CODES.get(territory)
    if country_code is None:
        return station
    provenance = {
        **station.provenance,
        "oscar": {
            "source_url": str(response.url.copy_with(query=None)),
            "territory": territory,
            "declared_status": match.get("declaredStatus"),
            "assessed_status": match.get("assessedStatus"),
            "station_type": match.get("stationTypeName"),
        },
    }
    return replace(
        station,
        country_code=country_code,
        elevation_m=(
            _number(match.get("elevation"))
            if _number(match.get("elevation")) is not None
            else station.elevation_m
        ),
        station_type=str(match.get("stationTypeName") or station.station_type),
        provenance=provenance,
    )


def enrich_oscar_metadata(
    stations: list[ObservationStation],
    *,
    timeout: float = 15.0,
    workers: int = 8,
) -> tuple[list[ObservationStation], int]:
    """Enrich a bounded selected set; failures remain explicit and retryable."""
    def enrich(station: ObservationStation) -> ObservationStation:
        try:
            return _oscar_metadata(station, timeout=timeout)
        except (httpx.HTTPError, ValueError, TypeError):
            return station

    with ThreadPoolExecutor(max_workers=max(1, min(workers, 12))) as pool:
        enriched = list(pool.map(enrich, stations))
    missing = sum(item.country_code is None for item in enriched)
    return enriched, missing


def _coverage_values(payload: dict, parameter: str) -> dict[datetime, float | None]:
    times = (((payload.get("domain") or {}).get("axes") or {}).get("t") or {}).get("values") or []
    values = (((payload.get("ranges") or {}).get(parameter) or {}).get("values") or [])
    output = {}
    for raw_time, raw_value in zip(times, values):
        try:
            observed_at = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
        except ValueError:
            continue
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            continue
        output[observed_at.astimezone(timezone.utc)] = _number(raw_value)
    return output


def _fetch_coverage(
    station_id: str,
    parameter: str,
    *,
    start: datetime,
    end: datetime,
    timeout: float,
) -> dict:
    response = httpx.get(
        f"{ESOH_BASE}/locations/{station_id}",
        params={
            "datetime": f"{start.isoformat().replace('+00:00', 'Z')}/"
                        f"{end.isoformat().replace('+00:00', 'Z')}",
            "parameter-name": parameter,
            "f": "CoverageJSON",
        },
        timeout=timeout,
    )
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    return response.json()


def fetch_recent(
    station_id: str,
    *,
    sensor_metadata: dict,
    hours: int = 6,
    timeout: float = 30.0,
    now: datetime | None = None,
) -> list[NormalizedObservation]:
    selected = (sensor_metadata or {}).get("esoh_wind") or {}
    speed_name = selected.get("speed_parameter")
    direction_name = selected.get("direction_parameter")
    if not speed_name or not direction_name:
        raise ValueError("E-SOH station has no selected wind parameter pair")
    received_at = now or datetime.now(timezone.utc)
    end = received_at.astimezone(timezone.utc)
    start = end - timedelta(hours=max(1, min(int(hours), 24)))
    names = [speed_name, direction_name]
    if selected.get("gust_parameter"):
        names.append(selected["gust_parameter"])
    series = {
        name: _coverage_values(
            _fetch_coverage(
                station_id, name, start=start, end=end, timeout=timeout
            ),
            name,
        )
        for name in names
    }
    speed_values = series[speed_name]
    direction_values = series[direction_name]
    gust_values = series.get(selected.get("gust_parameter"), {})
    period_seconds = selected.get("period_seconds")
    rows = []
    for observed_at, speed in speed_values.items():
        if speed is None:
            continue
        direction = direction_values.get(observed_at)
        gust = gust_values.get(observed_at)
        rows.append(normalize_observation(
            provider="eumetnet_esoh",
            station_id=station_id,
            observed_at=observed_at,
            wind_speed_ms=speed,
            wind_direction_deg=direction,
            wind_gust_ms=gust,
            gust_period_seconds=period_seconds if gust is not None else None,
            # E-SOH exposes normalized source observations but no common quality
            # flag across every member. Keep it unknown instead of inventing a
            # provider-wide approval marker.
            provider_quality=None,
            received_at=received_at,
            imported_at=datetime.now(timezone.utc),
            wigos_id=station_id,
            measurement_height_m=10.0,
            license=ESOH_LICENSE,
            provenance=ESOH_PROVENANCE,
            raw_payload={
                "speed_parameter": speed_name,
                "direction_parameter": direction_name,
                "gust_parameter": selected.get("gust_parameter"),
                "observed_at": observed_at.isoformat(),
                "values": {"speed": speed, "direction": direction, "gust": gust},
            },
            measurement_period_seconds=period_seconds,
            averaging_period_seconds=(
                period_seconds if selected.get("method") == "mean" else None
            ),
        ))
    return deduplicate_observations(rows)
