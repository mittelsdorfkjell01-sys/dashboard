"""Open-Meteo adapter that normalizes provider JSON into the weather domain."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from app.live.client import HttpOpenMeteoClient, OpenMeteoClient
from app.weather.catalog import family_for
from app.weather.contracts import ForecastPoint, ForecastRequest, ProviderForecast


class OpenMeteoProvider:
    def __init__(self, client: OpenMeteoClient | None = None) -> None:
        self._client = client or HttpOpenMeteoClient()

    def fetch_forecast(self, request: ForecastRequest) -> ProviderForecast:
        days = max(1, min(10, math.ceil((request.end - request.start).total_seconds() / 86400)))
        raw = self._client.fetch_forecast(
            request.latitude, request.longitude, ",".join(request.model_ids), days
        )
        hourly = raw.get("hourly") or {}
        times = hourly.get("time") or []
        multi = len(request.model_ids) > 1
        points: list[ForecastPoint] = []
        for model_id in request.model_ids:
            suffix = f"_{model_id}" if multi else ""
            columns = {
                name: hourly.get(f"{provider_name}{suffix}") or []
                for name, provider_name in {
                    "wind": "wind_speed_10m", "direction": "wind_direction_10m",
                    "gust": "wind_gusts_10m", "air": "temperature_2m",
                    "pressure": "pressure_msl", "cloud": "cloud_cover",
                    "low_cloud": "cloud_cover_low", "radiation": "shortwave_radiation_instant",
                    "precipitation": "precipitation",
                }.items()
            }
            for index, time_value in enumerate(times):
                wind = _at(columns["wind"], index)
                direction = _at(columns["direction"], index)
                if wind is None or direction is None:
                    continue
                valid_at = _utc(time_value)
                if not request.start <= valid_at < request.end:
                    continue
                gust = _at(columns["gust"], index)
                points.append(ForecastPoint(
                    valid_at=valid_at, model_id=model_id, family=family_for(model_id),
                    wind_speed_ms=wind, wind_direction_deg=direction % 360,
                    gust_speed_ms=max(wind, gust) if gust is not None else None,
                    air_temperature_c=_at(columns["air"], index),
                    pressure_msl_hpa=_at(columns["pressure"], index),
                    cloud_cover_pct=_at(columns["cloud"], index),
                    low_cloud_cover_pct=_at(columns["low_cloud"], index),
                    shortwave_radiation_wm2=_at(columns["radiation"], index),
                    precipitation_mm=_at(columns["precipitation"], index),
                ))
        return ProviderForecast(
            provider="open-meteo", fetched_at=datetime.now(timezone.utc),
            model_runs={}, points=tuple(points),
        )


def _at(values: list, index: int) -> float | None:
    value = values[index] if index < len(values) else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
