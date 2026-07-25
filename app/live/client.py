"""Open-Meteo client seam.

Two endpoints are used: the Forecast API (wind/gusts/direction/temperature/
precipitation) and the Marine API (swell height/period/direction +
sea-surface temperature). The :class:`OpenMeteoClient` protocol lets tests
inject a fake so no HTTP call is made in the suite.
"""

from __future__ import annotations

from typing import Protocol

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

FORECAST_HOURLY = (
    "wind_speed_10m,wind_gusts_10m,wind_direction_10m,temperature_2m,precipitation"
)
MARINE_HOURLY = (
    "swell_wave_height,swell_wave_period,swell_wave_direction,sea_surface_temperature"
)

# Open-Meteo's hard limit for the free forecast horizon; we never request more.
MAX_FORECAST_DAYS = 7


class OpenMeteoClient(Protocol):
    def fetch_forecast(self, lat: float, lon: float, models: str, days: int) -> dict: ...

    def fetch_marine(self, lat: float, lon: float, days: int) -> dict: ...


class HttpOpenMeteoClient:
    """Real client backed by ``httpx``. Returns the parsed JSON response."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def _get(self, url: str, params: dict) -> dict:
        import httpx

        resp = httpx.get(url, params=params, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

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
                "current": FORECAST_HOURLY,
                "models": models,
                "forecast_days": min(days, MAX_FORECAST_DAYS),
                "wind_speed_unit": "kn",
                "timezone": "auto",
            },
        )

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
                "forecast_days": min(days, MAX_FORECAST_DAYS),
                "timezone": "auto",
            },
        )


_default_client: HttpOpenMeteoClient | None = None


def default_client() -> OpenMeteoClient:
    global _default_client
    if _default_client is None:
        _default_client = HttpOpenMeteoClient()
    return _default_client
