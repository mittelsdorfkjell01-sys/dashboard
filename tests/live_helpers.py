"""Test doubles for the live path: a counting fake Open-Meteo client, synthetic
responses, and a minimal fake DB returning a single in-memory spot."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.models import Spot

_BASE = datetime(2026, 6, 29, 0, 0)

# Default per-day growth of the multi-model wind band width (kt/day). With the
# service thresholds (<=6 hoch, <=12 mittel), day-d width = 2.5*d reproduces the
# tier sequence [hoch,hoch,hoch,mittel,mittel,niedrig,niedrig] for a 7-day
# horizon -- now driven by *model spread*, not a calendar rule.
SPREAD_PER_DAY_KT = 2.5


def _hourly_times(days: int) -> list[str]:
    return [
        (_BASE + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")
        for h in range(days * 24)
    ]


def _single_model_forecast(times: list[str]) -> dict:
    """Bare-key response, mirroring Open-Meteo's single-model shape."""
    n = len(times)
    days = sorted({time[:10] for time in times})
    return {
        "latitude": 36.0,
        "longitude": -5.6,
        "timezone": "UTC",
        "current": {
            "time": times[0],
            "wind_speed_10m": 14.0,
            "wind_gusts_10m": 19.0,
            "wind_direction_10m": 270.0,
            "temperature_2m": 22.0,
        },
        "hourly": {
            "time": times,
            "wind_speed_10m": [10.0 + (i % 12) for i in range(n)],
            "wind_gusts_10m": [15.0 + (i % 12) for i in range(n)],
            "wind_direction_10m": [(i * 5) % 360 for i in range(n)],
            "temperature_2m": [18.0 + (i % 8) for i in range(n)],
            "precipitation": [round(0.1 * (i % 5), 1) for i in range(n)],
            "apparent_temperature": [17.0 + (i % 8) for i in range(n)],
            "cloud_cover": [i % 101 for i in range(n)],
            "pressure_msl": [1012.0 for _ in range(n)],
            "uv_index": [max(0, 6 - abs((i % 24) - 12)) for i in range(n)],
            "weather_code": [0 if i % 4 else 2 for i in range(n)],
            "is_day": [1 if 6 <= i % 24 < 20 else 0 for i in range(n)],
        },
        "daily": _daily(days),
    }


def _daily(days: list[str]) -> dict:
    return {
        "time": days, "temperature_2m_min": [14.0] * len(days),
        "temperature_2m_max": [24.0] * len(days), "apparent_temperature_min": [13.0] * len(days),
        "apparent_temperature_max": [25.0] * len(days), "precipitation_sum": [1.2] * len(days),
        "precipitation_probability_max": [30.0] * len(days), "cloud_cover_mean": [45.0] * len(days),
        "weather_code": [2] * len(days), "sunrise": [f"{d}T05:30" for d in days],
        "sunset": [f"{d}T20:30" for d in days], "daylight_duration": [54000.0] * len(days),
        "uv_index_max": [7.0] * len(days),
    }


def make_forecast_response(
    days: int = 8,
    models: list[str] | None = None,
    null_models: list[str] | None = None,
) -> dict:
    """Synthetic Open-Meteo forecast payload.

    - ``models`` None/single -> bare-key (single-model) response.
    - ``models`` with >1 entry -> suffixed keys per model with a symmetric spread
      that grows with the day index, so the consensus (median) stays on the base
      series while the band widens toward the horizon. Models in ``null_models``
      return all-``None`` arrays (coverage gap) to exercise graceful degradation.
    """
    times = _hourly_times(days)
    n = len(times)
    if not models or len(models) == 1:
        return _single_model_forecast(times)

    null_set = set(null_models or [])
    base_wind = [10.0 + (i % 12) for i in range(n)]
    base_gust = [15.0 + (i % 12) for i in range(n)]
    base_dir = [(i * 5) % 360 for i in range(n)]
    base_air = [18.0 + (i % 8) for i in range(n)]

    k = len(models)

    def offset(mi: int, width: float) -> float:
        # Symmetric around 0 so the median lands on the base series.
        step = width / (k - 1)
        return round(step * (mi - (k - 1) / 2), 2)

    hourly: dict = {"time": times}
    for mi, m in enumerate(models):
        if m in null_set:
            hourly[f"wind_speed_10m_{m}"] = [None] * n
            hourly[f"wind_gusts_10m_{m}"] = [None] * n
            hourly[f"wind_direction_10m_{m}"] = [None] * n
            hourly[f"temperature_2m_{m}"] = [None] * n
            hourly[f"precipitation_{m}"] = [None] * n
            continue
        hourly[f"wind_speed_10m_{m}"] = [
            round(base_wind[i] + offset(mi, SPREAD_PER_DAY_KT * (i // 24)), 2)
            for i in range(n)
        ]
        hourly[f"wind_gusts_10m_{m}"] = [
            round(base_gust[i] + offset(mi, SPREAD_PER_DAY_KT * (i // 24)), 2)
            for i in range(n)
        ]
        hourly[f"wind_direction_10m_{m}"] = base_dir
        hourly[f"temperature_2m_{m}"] = base_air
        hourly[f"precipitation_{m}"] = [round(0.1 * (i % 5), 1) for i in range(n)]

    # Open-Meteo returns the `current` block UNSUFFIXED even for a multi-model
    # request (only `hourly` carries per-model suffixes) -- mirror that here so
    # the fake matches reality. The service reads current unsuffixed and derives
    # the "now" spread from the current hour of the hourly series.
    current = {
        "time": times[0],
        "wind_speed_10m": 14.0,
        "wind_gusts_10m": 19.0,
        "wind_direction_10m": 270.0,
        "temperature_2m": 22.0,
    }
    for name, values in {
        "apparent_temperature": [17.0 + (i % 8) for i in range(n)],
        "cloud_cover": [i % 101 for i in range(n)], "pressure_msl": [1012.0] * n,
        "uv_index": [max(0, 6 - abs((i % 24) - 12)) for i in range(n)],
        "weather_code": [0 if i % 4 else 2 for i in range(n)],
        "is_day": [1 if 6 <= i % 24 < 20 else 0 for i in range(n)],
    }.items():
        for m in models:
            hourly[f"{name}_{m}"] = values
    days = sorted({time[:10] for time in times})
    daily = {"time": days}
    for name, values in _daily(days).items():
        if name == "time": continue
        for m in models:
            daily[f"{name}_{m}"] = values
    return {"latitude": 36.0, "longitude": -5.6, "timezone": "UTC", "current": current, "hourly": hourly, "daily": daily}


def make_marine_response(days: int = 8) -> dict:
    times = _hourly_times(days)
    n = len(times)
    return {
        "latitude": 36.01,
        "longitude": -5.60,
        "timezone": "GMT",
        "current": {
            "time": times[0],
            "swell_wave_height": 1.2,
            "swell_wave_period": 9.0,
            "swell_wave_direction": 250.0,
            "sea_surface_temperature": 20.0,
        },
        "hourly": {
            "time": times,
            "swell_wave_height": [1.0 + 0.1 * (i % 5) for i in range(n)],
            "swell_wave_period": [8.0 + (i % 4) for i in range(n)],
            "swell_wave_direction": [(200 + i) % 360 for i in range(n)],
            "sea_surface_temperature": [19.0 + (i % 3) for i in range(n)],
        },
    }


class FakeOpenMeteoClient:
    """Records call counts and the model set it was asked for. No network.

    ``null_models`` (subset of the requested set) return no data, to exercise
    the graceful-degradation path.
    """

    def __init__(
        self, data_days: int = 8, null_models: list[str] | None = None
    ) -> None:
        self._data_days = data_days
        self._null_models = null_models
        self.forecast_calls = 0
        self.marine_calls = 0
        self.models_seen: list[str] = []

    def fetch_forecast(self, lat, lon, models, days=7) -> dict:
        self.forecast_calls += 1
        self.models_seen.append(models)
        model_list = [m for m in models.split(",") if m] if models else []
        return make_forecast_response(
            self._data_days, models=model_list, null_models=self._null_models
        )

    def fetch_marine(self, lat, lon, days=7) -> dict:
        self.marine_calls += 1
        return make_marine_response(self._data_days)


def make_spot(lat: float = 36.0128, lon: float = -5.6035, model_pref=None) -> Spot:
    spot = Spot(
        slug="test-spot",
        name="Test Spot",
        region_id=uuid.uuid4(),
        location=from_shape(Point(lon, lat), srid=4326),
        model_pref=model_pref,
        sports=["kitesurf"],
        status="published",
        water_type=["ocean"],
    )
    spot.id = uuid.uuid4()
    return spot


class FakeDB:
    """Stands in for a SQLAlchemy Session's ``.get`` lookup."""

    def __init__(self, spot: Spot) -> None:
        self._spot = spot

    def get(self, model, ident):
        return self._spot if ident == self._spot.id else None
