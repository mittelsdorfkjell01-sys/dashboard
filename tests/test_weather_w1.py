from app.live.cache import InMemoryCache
from app.live.service import get_forecast_series
from app.live.weather_contract import Availability, marine_classification, provider_axis_utc, weather_condition
from tests.live_helpers import FakeDB, FakeOpenMeteoClient, make_forecast_response, make_spot


def test_wmo_v1_all_groups_and_unknown():
    expected = {
        0: "clear", 1: "mainly_clear", 2: "partly_cloudy", 3: "overcast",
        45: "fog", 48: "fog", 51: "drizzle", 57: "drizzle", 61: "rain",
        67: "rain", 71: "snow", 77: "snow", 80: "rain_showers", 82: "rain_showers",
        85: "snow_showers", 86: "snow_showers", 95: "thunderstorm", 99: "thunderstorm",
        42: "unknown",
    }
    assert {code: weather_condition(code) for code in expected} == expected


def test_dst_axes_are_strict_for_spring_gap_and_repeated_fall_hour():
    spring = provider_axis_utc(["2026-03-29T01:00", "2026-03-29T03:00"], "Europe/Berlin")
    fall = provider_axis_utc(["2026-10-25T01:00", "2026-10-25T02:00", "2026-10-25T02:00", "2026-10-25T03:00"], "Europe/Berlin")
    assert all(a is not None and b is not None and a < b for a, b in zip(spring, spring[1:]))
    assert all(a is not None and b is not None and a < b for a, b in zip(fall, fall[1:]))
    assert (fall[2] - fall[1]).total_seconds() == 3600


def test_complete_weather_v2_contract_uses_nullable_fields_and_local_dates():
    spot = make_spot()
    result = get_forecast_series(spot.id, db=FakeDB(spot), client=FakeOpenMeteoClient(data_days=10), cache=InMemoryCache())
    assert result["contract_version"] == "weather-v2"
    assert result["timezone"] == "UTC" and len(result["days"]) == 10
    hour = result["days"][0]["hours"][0]
    assert hour["apparent_temperature_c"] == 17
    assert hour["cloud_cover_pct"] == 0 and hour["pressure_msl_hpa"] == 1012
    assert hour["weather_condition"] == "partly_cloudy" and hour["is_day"] is False
    summary = result["days"][0]["summary"]
    assert summary["temperature_min_c"] == 14 and summary["temperature_max_c"] == 24
    assert summary["precipitation_sum_mm"] == 1.2 and summary["solar_state"] == "normal"


def test_invalid_individual_weather_value_becomes_null_not_zero():
    class InvalidClient(FakeOpenMeteoClient):
        def fetch_forecast(self, lat, lon, models, days=10):
            payload = make_forecast_response(2, models=[m for m in models.split(",") if m])
            first = models.split(",")[0]
            payload["hourly"][f"uv_index_{first}"][0] = -1
            payload["hourly"][f"cloud_cover_{first}"][0] = 101
            return payload
    spot = make_spot()
    result = get_forecast_series(spot.id, 2, db=FakeDB(spot), client=InvalidClient(), cache=InMemoryCache())
    assert result["days"][0]["hours"][0]["uv_index"] is None
    assert result["days"][0]["hours"][0]["cloud_cover_pct"] is None


def test_polar_day_and_night_are_explicit_without_invented_sun_times():
    class PolarClient(FakeOpenMeteoClient):
        def __init__(self, daylight):
            super().__init__(data_days=2)
            self.daylight = daylight

        def fetch_forecast(self, lat, lon, models, days=10):
            payload = make_forecast_response(2, models=[m for m in models.split(",") if m])
            for key in list(payload["daily"]):
                if key.startswith("sunrise_") or key.startswith("sunset_"):
                    payload["daily"][key] = [None, None]
                if key.startswith("daylight_duration_"):
                    payload["daily"][key] = [self.daylight, self.daylight]
            return payload

    spot = make_spot()
    for daylight, state in ((86400, "polar_day"), (0, "polar_night")):
        result = get_forecast_series(spot.id, 2, db=FakeDB(spot), client=PolarClient(daylight), cache=InMemoryCache())
        assert result["days"][0]["summary"]["solar_state"] == state
        assert result["days"][0]["summary"]["sunrise_at"] is None


def test_marine_eligibility_is_conservative_for_inland_and_unknown():
    inland = make_spot()
    inland.water_type = ["lake"]
    unknown = make_spot()
    unknown.water_type = []
    assert marine_classification(inland) is Availability.NOT_APPLICABLE_INLAND
    assert marine_classification(unknown) is Availability.UNKNOWN_LOCATION_TYPE
    client = FakeOpenMeteoClient(data_days=2)
    result = get_forecast_series(inland.id, 2, db=FakeDB(inland), client=client, cache=InMemoryCache())
    assert result["availability"]["marine"] == "not_applicable_inland"
    assert client.marine_calls == 0
    assert all(hour["swell"] is None for day in result["days"] for hour in day["hours"])
