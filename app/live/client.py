"""Open-Meteo client seam.

Two endpoints are used: the Forecast API (wind/gusts/direction/temperature/
precipitation) and the Marine API (swell height/period/direction +
sea-surface temperature). The :class:`OpenMeteoClient` protocol lets tests
inject a fake so no HTTP call is made in the suite.
"""

from __future__ import annotations

import random
import time
from typing import Protocol
from app.weather.budget import RequestBudget, default_request_budget

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

FORECAST_HOURLY = (
    "wind_speed_10m,wind_gusts_10m,wind_direction_10m,temperature_2m,"
    "apparent_temperature,pressure_msl,cloud_cover,cloud_cover_low,"
    "shortwave_radiation_instant,precipitation,uv_index,weather_code,is_day"
)
FORECAST_DAILY = (
    "temperature_2m_min,temperature_2m_max,apparent_temperature_min,"
    "apparent_temperature_max,precipitation_sum,precipitation_probability_max,"
    "cloud_cover_mean,weather_code,sunrise,sunset,daylight_duration,uv_index_max"
)
FORECAST_MINUTELY_15 = "wind_speed_10m,wind_gusts_10m,wind_direction_10m"
MARINE_HOURLY = (
    "wave_height,wave_period,wave_direction,swell_wave_height,swell_wave_period,"
    "swell_wave_direction,sea_surface_temperature"
)
MARINE_DAILY = "wave_height_max,wave_direction_dominant,wave_period_max"

# Open-Meteo's hard limit for the free forecast horizon; we never request more.
MAX_FORECAST_DAYS = 10


class OpenMeteoClient(Protocol):
    def fetch_forecast(self, lat: float, lon: float, models: str, days: int) -> dict: ...

    def fetch_marine(self, lat: float, lon: float, days: int) -> dict: ...
    def fetch_nowcast(self, lat: float, lon: float, models: str) -> dict: ...
    def fetch_current_marine(self, lat: float, lon: float) -> dict: ...


class HttpOpenMeteoClient:
    """Real client backed by ``httpx``. Returns the parsed JSON response."""

    def __init__(self, timeout: float = 10.0, attempts: int = 3, budget: RequestBudget | None = None) -> None:
        self._timeout = timeout
        self._attempts = max(1, attempts)
        self._budget = budget or default_request_budget
        self.request_attempts = 0
        self.response_bytes = 0
        self.requests_by_endpoint = {"atmosphere": 0, "marine": 0}
        self.bytes_by_endpoint = {"atmosphere": 0, "marine": 0}

    def _get(self, url: str, params: dict) -> dict:
        import httpx

        last_error: Exception | None = None
        for attempt in range(self._attempts):
            try:
                self._budget.consume()
                group = "marine" if url == MARINE_URL else "atmosphere"
                self.request_attempts += 1
                self.requests_by_endpoint[group] += 1
                resp = httpx.get(url, params=params, timeout=self._timeout)
                resp.raise_for_status()
                size = len(resp.content)
                self.response_bytes += size
                self.bytes_by_endpoint[group] += size
                return resp.json()
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {
                    408, 425, 429, 500, 502, 503, 504,
                }
                if not retryable or attempt + 1 >= self._attempts:
                    raise
                time.sleep((0.2 * (2**attempt)) + random.uniform(0.0, 0.1))
        raise RuntimeError("weather provider request failed") from last_error

    def fetch_forecast(
        self, lat: float, lon: float, models: str, days: int = MAX_FORECAST_DAYS
    ) -> dict:
        """Fetch one or more models in a single request.

        ``models`` is a comma-joined list (e.g. ``"icon_eu,gfs_seamless"``). When
        more than one model is requested Open-Meteo suffixes the hourly/current
        field names (``wind_speed_10m_icon_eu``); a single model uses bare keys.
        A multi-model request costs the same as a single one -- the payload is
        larger but there is no extra request per model.
        """
        return self._get(
            FORECAST_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "hourly": FORECAST_HOURLY,
                "minutely_15": FORECAST_MINUTELY_15,
                "current": FORECAST_HOURLY,
                "daily": FORECAST_DAILY,
                "models": models,
                "forecast_days": min(days, MAX_FORECAST_DAYS),
                "wind_speed_unit": "ms",
                "timezone": "auto",
            },
        )

    def fetch_nowcast(self, lat: float, lon: float, models: str) -> dict:
        """Small atmospheric current/minutely request; no ten-day daily payload."""
        return self._get(FORECAST_URL, {
            "latitude": lat, "longitude": lon,
            "minutely_15": FORECAST_MINUTELY_15,
            "current": "wind_speed_10m,wind_gusts_10m,wind_direction_10m,temperature_2m",
            "hourly": FORECAST_MINUTELY_15, "forecast_hours": 3,
            "models": models, "wind_speed_unit": "ms", "timezone": "auto",
        })

    def fetch_marine(
        self, lat: float, lon: float, days: int = MAX_FORECAST_DAYS
    ) -> dict:
        return self._get(
            MARINE_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "hourly": MARINE_HOURLY,
                "current": MARINE_HOURLY,
                "daily": MARINE_DAILY,
                "forecast_days": min(days, MAX_FORECAST_DAYS),
                "timezone": "GMT",
                "cell_selection": "sea",
            },
        )

    def fetch_current_marine(self, lat: float, lon: float) -> dict:
        """Small current marine request with a short alignment horizon."""
        return self._get(MARINE_URL, {
            "latitude": lat, "longitude": lon, "current": MARINE_HOURLY,
            "hourly": MARINE_HOURLY, "forecast_hours": 3,
            "timezone": "GMT", "cell_selection": "sea",
        })


_default_client: HttpOpenMeteoClient | None = None


def default_client() -> OpenMeteoClient:
    global _default_client
    if _default_client is None:
        _default_client = HttpOpenMeteoClient()
    return _default_client
