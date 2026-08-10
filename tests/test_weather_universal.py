from pathlib import Path

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.live.cache import InMemoryCache
from app.live.service import InvalidSpotCoordinates, get_forecast_series, get_live_conditions
from app.weather.profiles import resolve_weather_profile
from tests.live_helpers import FakeDB, FakeOpenMeteoClient, make_spot


def test_new_spot_without_profile_immediately_gets_coordinates_weather():
    spot = make_spot()
    client = FakeOpenMeteoClient(data_days=11)
    current = get_live_conditions(spot.id, db=FakeDB(spot), client=client, cache=InMemoryCache())
    forecast = get_forecast_series(spot.id, 10, db=FakeDB(spot), client=client, cache=InMemoryCache())
    assert current["quality_tier"] == "coordinates"
    assert len(forecast["days"]) == 10


def test_availability_does_not_depend_on_process_registry_or_profile():
    spot = make_spot()
    for _ in range(2):
        result = get_live_conditions(spot.id, db=FakeDB(spot), client=FakeOpenMeteoClient(), cache=InMemoryCache())
        assert result["current"]["wind"] is not None


def test_invalid_coordinates_never_call_provider():
    spot = make_spot()
    spot.location = from_shape(Point(float("nan"), 54), srid=4326)
    client = FakeOpenMeteoClient()
    with pytest.raises(InvalidSpotCoordinates):
        get_live_conditions(spot.id, db=FakeDB(spot), client=client, cache=InMemoryCache())
    assert client.forecast_calls == 0 and client.marine_calls == 0


def test_coordinate_change_cannot_reuse_old_forecast_cache_entry():
    spot = make_spot()
    client, cache, db = FakeOpenMeteoClient(), InMemoryCache(), FakeDB(spot)
    get_live_conditions(spot.id, db=db, client=client, cache=cache)
    spot.location = from_shape(Point(10.5, 54.5), srid=4326)
    get_live_conditions(spot.id, db=db, client=client, cache=cache)
    assert client.forecast_calls == 2 and client.marine_calls == 2


def test_incomplete_and_advanced_profiles_degrade_to_safe_coastal_or_coordinates():
    incomplete = type("P", (), {"active": True, "quality_tier": "coastal", "timezone": None, "elevation_m": 2, "coastal_normal_deg": 270})()
    assert resolve_weather_profile(incomplete) is None
    advanced = type("P", (), {"active": True, "quality_tier": "advanced", "timezone": "Europe/Berlin", "elevation_m": 2, "coastal_normal_deg": 270})()
    resolved = resolve_weather_profile(advanced)
    assert resolved is not None and resolved.quality_tier == "coastal" and not resolved.sectors


def test_pilot_configuration_is_not_imported_by_productive_weather_code():
    root = Path(__file__).resolve().parents[1] / "app"
    assert not any("weather-pilot-spots" in path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
