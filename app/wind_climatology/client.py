from __future__ import annotations

import time
from datetime import date

import httpx

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class WindHistoryClient:
    def __init__(self, http=None):
        self.http = http or self._get

    @staticmethod
    def _get(url, params):
        last_error = None
        for attempt in range(3):
            try:
                response = httpx.get(url, params=params, timeout=120)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise RuntimeError("Open-Meteo ERA5 request failed after retries") from last_error

    def fetch(self, lat: float, lon: float, start_year: int, end_year: int) -> dict:
        params = {"latitude": lat, "longitude": lon, "start_date": f"{start_year}-01-01", "end_date": f"{end_year}-12-31", "hourly": "wind_speed_10m", "wind_speed_unit": "kn", "timezone": "auto", "timeformat": "unixtime", "models": "era5", "cell_selection": "nearest", "elevation": "nan"}
        payload = self.http(ARCHIVE_URL, params)
        hourly = payload.get("hourly") or {}
        units = payload.get("hourly_units") or {}
        if units.get("wind_speed_10m") not in {"kn", "kt"}:
            raise RuntimeError(f"unexpected wind unit: {units.get('wind_speed_10m')!r}")
        reported_model = payload.get("model") or payload.get("models")
        if reported_model and "era5" not in str(reported_model).lower():
            raise RuntimeError(f"unexpected weather model: {reported_model!r}")
        if not isinstance(hourly.get("time"), list) or not isinstance(hourly.get("wind_speed_10m"), list):
            raise RuntimeError("Open-Meteo response lacks hourly ERA5 wind")
        if len(hourly["time"]) != len(hourly["wind_speed_10m"]):
            raise RuntimeError("Open-Meteo time/wind arrays differ")
        expected_hours = (date(end_year + 1, 1, 1) - date(start_year, 1, 1)).days * 24
        if len(hourly["time"]) != expected_hours:
            raise RuntimeError(f"incomplete ERA5 period: expected {expected_hours} hours, got {len(hourly['time'])}")
        if payload.get("latitude") is None or payload.get("longitude") is None or not payload.get("timezone"):
            raise RuntimeError("Open-Meteo response lacks grid coordinates/timezone")
        return {"times": hourly["time"], "speeds_kn": hourly["wind_speed_10m"], "actual_lat": float(payload["latitude"]), "actual_lon": float(payload["longitude"]), "timezone": payload["timezone"], "unit": units["wind_speed_10m"], "request": params}
