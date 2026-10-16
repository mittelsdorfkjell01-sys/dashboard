"""Tide-gauge provider contracts and normalized free-data adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ProviderStation:
    provider: str
    provider_station_id: str
    name: str
    latitude: float
    longitude: float
    country_code: str | None
    operator: str | None
    source_url: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProviderObservation:
    provider: str
    provider_station_id: str
    provider_sensor_id: str
    observed_at: datetime
    value_m: float
    unit: str
    vertical_datum: str | None
    quality_status: str
    raw: dict[str, Any]


class TideStationProvider(Protocol):
    key: str

    def stations(self) -> list[ProviderStation]: ...
    def observations(self, station_id: str, *, start: datetime) -> list[ProviderObservation]: ...


def _json_get(url: str, *, timeout: float = 30.0) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Surfwinddata/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed provider URL
        return json.loads(response.read().decode("utf-8"))


class PegelOnlineProvider:
    """Unauthenticated German WSV water-level API adapter."""

    key = "pegelonline"
    base_url = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"

    def stations(self) -> list[ProviderStation]:
        payload = _json_get(f"{self.base_url}/stations.json?includeTimeseries=true")
        result: list[ProviderStation] = []
        for item in payload:
            series = item.get("timeseries") or []
            if not any(row.get("shortname") == "W" for row in series):
                continue
            station_id = str(item["uuid"])
            result.append(ProviderStation(
                provider=self.key,
                provider_station_id=station_id,
                name=item.get("longname") or item.get("shortname") or station_id,
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                country_code="DE",
                operator=item.get("agency"),
                source_url=f"{self.base_url}/stations/{station_id}.json",
                metadata={"water": item.get("water"), "number": item.get("number")},
            ))
        return result

    def observations(self, station_id: str, *, start: datetime) -> list[ProviderObservation]:
        if start.tzinfo is None:
            raise ValueError("observation start must include a timezone")
        query = urlencode({"start": start.astimezone(timezone.utc).isoformat()})
        payload = _json_get(f"{self.base_url}/stations/{station_id}/W/measurements.json?{query}")
        result: list[ProviderObservation] = []
        for item in payload:
            value = item.get("value")
            timestamp = item.get("timestamp")
            if value is None or not timestamp:
                continue
            result.append(ProviderObservation(
                provider=self.key,
                provider_station_id=station_id,
                provider_sensor_id=f"{station_id}:W",
                observed_at=datetime.fromisoformat(timestamp).astimezone(timezone.utc),
                value_m=float(value) / 100.0,
                unit="m",
                vertical_datum=None,
                quality_status="raw",
                raw=item,
            ))
        return result
