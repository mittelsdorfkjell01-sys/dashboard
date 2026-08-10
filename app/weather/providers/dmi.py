"""DMI Open Data metObs v2 adapter (no API key required)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.weather.providers.common import ObservationStation, WindObservation

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


def fetch_recent(station_id: str, *, period: str = "latest-day", timeout: float = 20.0) -> list[WindObservation]:
    payload = _get("observation/items", {
        "stationId": str(station_id), "period": period, "limit": 1000,
    }, timeout=timeout)
    grouped: dict[datetime, dict[str, float]] = {}
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        parameter = props.get("parameterId")
        if parameter not in {"wind_speed", "wind_dir", "wind_max"}:
            continue
        try:
            stamp = datetime.fromisoformat(str(props["observed"]).replace("Z", "+00:00")).astimezone(timezone.utc)
            grouped.setdefault(stamp, {})[parameter] = float(props["value"])
        except (KeyError, TypeError, ValueError):
            continue
    return [
        WindObservation(stamp, values["wind_speed"], values.get("wind_dir"), values.get("wind_max"))
        for stamp, values in sorted(grouped.items()) if values.get("wind_speed", -1) >= 0
    ]
