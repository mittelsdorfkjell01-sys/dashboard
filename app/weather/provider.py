"""Port implemented by Open-Meteo today and direct model sources later."""

from __future__ import annotations

from typing import Protocol

from app.weather.contracts import ForecastRequest, ProviderForecast


class WeatherProvider(Protocol):
    """Fetch and normalize weather data without leaking provider JSON."""

    def fetch_forecast(self, request: ForecastRequest) -> ProviderForecast: ...
