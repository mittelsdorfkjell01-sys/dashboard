"""Provider-neutral weather domain for calculated wind products.

All calculations in this package use UTC timestamps and metres per second.
Conversion into display units belongs at the public API/UI boundary.
"""

from app.weather.contracts import ForecastPoint, ForecastRequest, ProviderForecast

__all__ = ["ForecastPoint", "ForecastRequest", "ProviderForecast"]
