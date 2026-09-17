"""DMI Open Data metObs v2 adapter (no API key required)."""

from __future__ import annotations

from datetime import datetime, timezone
import math

import httpx

from app.weather.providers.common import (
    NormalizedObservation,
    ObservationStation,
    deduplicate_observations,
    normalize_observation,
)

DMI_BASE = "https://opendataapi.dmi.dk/v2/metObs/collections"
DMI_LICENSE = "CC BY 4.0"
DMI_PROVENANCE = {
    "source": "Danish Meteorological Institute Open Data",
    "collection": "metObs",
    "source_url": DMI_BASE,
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "terms_url": "https://www.dmi.dk/friedata/dokumentation/terms-of-use",
    "parameter_documentation_url": (
        "https://www.dmi.dk/friedata/dokumentation/"
        "meteorological-observations-data"
    ),
    "wind_measurement_height_m": 10,
    "wind_max_averaging_seconds": 3,
    "wind_max_window_seconds": 600,
    "country_code": "DK",
    "commercial_reuse": True,
    "attribution_required": True,
    "typical_interval_minutes": 10,
}


def _optional_float(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _get(path: str, params: dict, *, timeout: float) -> dict:
    response = httpx.get(f"{DMI_BASE}/{path}", params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_stations(*, timeout: float = 20.0) -> list[ObservationStation]:
    payload = _get("station/items", {"status": "Active", "limit": 1000}, timeout=timeout)
    by_id: dict[str, ObservationStation] = {}
    for feature in payload.get("features") or []:
        props, geometry = feature.get("properties") or {}, feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        station_id = str(props.get("stationId") or "").strip()
        if not station_id or len(coords) < 2 or props.get("status") != "Active":
            continue
        parameters = tuple(str(value) for value in (props.get("parameterId") or []))
        if "wind_speed" not in parameters:
            continue
        latitude = _optional_float(coords[1])
        longitude = _optional_float(coords[0])
        if latitude is None or longitude is None:
            continue
        by_id[station_id] = ObservationStation(
            provider="dmi", station_id=station_id, name=str(props.get("name") or station_id),
            latitude=latitude, longitude=longitude,
            elevation_m=_optional_float(props.get("stationHeight")),
            parameters=parameters,
            wigos_id=props.get("wigosId") or props.get("wigosStationIdentifier"),
            icao_id=props.get("icaoId"),
            measurement_height_m=_optional_float(
                props.get("measurementHeight") or props.get("sensorHeight")
            ) or 10.0,
            license=DMI_LICENSE,
            provenance=DMI_PROVENANCE,
            country_code="DK",
            typical_interval_minutes=10,
            commercial_reuse=True,
            attribution_required=True,
        )
    return list(by_id.values())


def fetch_recent(station_id: str, *, period: str = "latest-day", timeout: float = 20.0) -> list[NormalizedObservation]:
    payload = _get("observation/items", {
        "stationId": str(station_id), "period": period, "limit": 1000,
    }, timeout=timeout)
    received_at = datetime.now(timezone.utc)
    grouped: dict[str, dict[str, object]] = {}
    malformed = []
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        parameter = props.get("parameterId")
        if parameter not in {"wind_speed", "wind_dir", "wind_max"}:
            continue
        raw_observed = props.get("observed")
        try:
            stamp = datetime.fromisoformat(str(raw_observed).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            issues = ["provider_parse:invalid"]
            actual_station_id = str(props.get("stationId") or station_id)
            if actual_station_id != str(station_id):
                issues.append("station_identity:mismatch")
            malformed.append(normalize_observation(
                provider="dmi",
                station_id=actual_station_id,
                observed_at=None,
                wind_speed_ms=props.get("value") if parameter == "wind_speed" else None,
                received_at=received_at,
                imported_at=datetime.now(timezone.utc),
                provider_quality=props.get("quality"),
                license=DMI_LICENSE,
                provenance=DMI_PROVENANCE,
                raw_payload=feature,
                extra_issues=issues,
            ))
            continue
        stamp_key = (
            stamp.astimezone(timezone.utc).isoformat()
            if stamp.tzinfo is not None and stamp.utcoffset() is not None
            else f"naive:{stamp.isoformat()}"
        )
        values = grouped.setdefault(stamp_key, {
            "observed_at": stamp,
            "features": [],
            "qualities": set(),
            "issues": [],
            "station_id": props.get("stationId") or station_id,
            "geometry": feature.get("geometry") or {},
            "properties": props,
        })
        existing = values.get(parameter)
        incoming = props.get("value")
        if existing is not None:
            existing_number = _optional_float(existing)
            incoming_number = _optional_float(incoming)
            same_value = (
                existing_number == incoming_number
                if existing_number is not None and incoming_number is not None
                else existing == incoming
            )
            if not same_value:
                values["issues"].append("duplicate:conflict")
        values[parameter] = incoming
        values["features"].append(feature)
        if props.get("quality") is not None:
            values["qualities"].add(str(props["quality"]))
        actual_station_id = str(props.get("stationId") or station_id)
        if actual_station_id != str(station_id):
            values["issues"].append("station_identity:mismatch")

    rows = malformed
    for values in grouped.values():
        props = values["properties"]
        coordinates = values["geometry"].get("coordinates") or []
        wind_direction = values.get("wind_dir")
        direction_number = _optional_float(wind_direction)
        if direction_number == 360:
            wind_direction = 0.0
        speed_number = _optional_float(values.get("wind_speed"))
        if direction_number == 0 and speed_number is not None and speed_number > 0:
            values["issues"].append("wind_direction:provider_calm_conflict")
        rows.append(normalize_observation(
            provider="dmi",
            station_id=values["station_id"],
            observed_at=values["observed_at"],
            wind_speed_ms=values.get("wind_speed"),
            wind_direction_deg=wind_direction,
            wind_gust_ms=values.get("wind_max"),
            # DMI defines wind_max as the highest 3-second mean in the latest
            # 10-minute window; this field records that window explicitly.
            gust_period_seconds=600 if values.get("wind_max") is not None else None,
            provider_quality=",".join(sorted(values["qualities"])) or None,
            received_at=received_at,
            imported_at=datetime.now(timezone.utc),
            wigos_id=props.get("wigosId") or props.get("wigosStationIdentifier"),
            icao_id=props.get("icaoId"),
            longitude=coordinates[0] if len(coordinates) >= 2 else None,
            latitude=coordinates[1] if len(coordinates) >= 2 else None,
            elevation_m=props.get("stationHeight"),
            measurement_height_m=(
                props.get("measurementHeight") or props.get("sensorHeight")
            ) or 10.0,
            license=DMI_LICENSE,
            provenance=DMI_PROVENANCE,
            raw_payload={"features": values["features"]},
            extra_issues=values["issues"],
        ))
    return deduplicate_observations(rows)
