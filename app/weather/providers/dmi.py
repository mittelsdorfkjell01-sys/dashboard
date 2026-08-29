"""DMI Open Data metObs v2 adapter (no API key required)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.weather.providers.common import NormalizedObservation, ObservationStation, normalize_observation

DMI_BASE = "https://opendataapi.dmi.dk/v2/metObs/collections"


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
        by_id[station_id] = ObservationStation(
            provider="dmi", station_id=station_id, name=str(props.get("name") or station_id),
            latitude=float(coords[1]), longitude=float(coords[0]),
            elevation_m=float(props["stationHeight"]) if isinstance(props.get("stationHeight"), (int, float)) else None,
            parameters=parameters,
        )
    return list(by_id.values())


def fetch_recent(station_id: str, *, period: str = "latest-day", timeout: float = 20.0) -> list[NormalizedObservation]:
    payload = _get("observation/items", {
        "stationId": str(station_id), "period": period, "limit": 1000,
    }, timeout=timeout)
    grouped: dict[datetime, dict[str, object]] = {}
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        parameter = props.get("parameterId")
        if parameter not in {"wind_speed", "wind_dir", "wind_max"}:
            continue
        try:
            stamp = datetime.fromisoformat(str(props["observed"]).replace("Z", "+00:00")).astimezone(timezone.utc)
            values = grouped.setdefault(stamp, {})
            values[parameter] = float(props["value"])
            if props.get("quality") is not None: values["quality"] = props["quality"]
        except (KeyError, TypeError, ValueError):
            continue
    return [
        normalize_observation(provider="dmi", station_id=station_id, observed_at=stamp,
                              wind_speed_ms=values["wind_speed"], wind_direction_deg=values.get("wind_dir"),
                              wind_gust_ms=values.get("wind_max"), provider_quality=values.get("quality"))
        for stamp, values in sorted(grouped.items()) if values.get("wind_speed", -1) >= 0
    ]
