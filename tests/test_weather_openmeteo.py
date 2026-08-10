from datetime import datetime, timedelta, timezone

from app.weather.contracts import ForecastRequest
from app.weather.openmeteo import OpenMeteoProvider
from tests.live_helpers import FakeOpenMeteoClient


def test_openmeteo_adapter_returns_only_normalized_utc_ms_points():
    start = datetime(2026, 6, 29, tzinfo=timezone.utc)
    result = OpenMeteoProvider(FakeOpenMeteoClient(data_days=2)).fetch_forecast(
        ForecastRequest(latitude=54, longitude=10, start=start, end=start + timedelta(days=2), model_ids=("ecmwf_ifs", "ncep_gfs_global"))
    )
    assert result.provider == "open-meteo"
    assert len(result.points) == 96
    assert all(point.valid_at.tzinfo is timezone.utc for point in result.points)
    assert all(point.wind_speed_ms >= 0 for point in result.points)
