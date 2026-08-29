import math

from app.live.cache import InMemoryCache
from app.live.service import get_forecast_series
from app.live.weather_contract import Availability, marine_classification, provider_axis_utc, weather_condition
from app.schemas.live import ForecastDaySummary, ForecastHour
from app.models.weather_profile import SpotWeatherProfile
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


def test_complete_weather_v5_contract_uses_nullable_fields_and_local_dates():
    spot = make_spot()
    result = get_forecast_series(spot.id, db=FakeDB(spot), client=FakeOpenMeteoClient(data_days=10), cache=InMemoryCache())
    assert result["contract_version"] == "weather-v5"
    assert result["timezone"] == "UTC" and len(result["days"]) == 10
    hour = result["days"][0]["hours"][0]
    assert hour["apparent_temperature_c"] == 17
    assert hour["cloud_cover_pct"] == 0 and hour["pressure_msl_hpa"] == 1012
    assert hour["weather_condition"] == "partly_cloudy" and hour["is_day"] is False
    summary = result["days"][0]["summary"]
    assert summary["temperature_min_c"] == 14 and summary["temperature_max_c"] == 24
    assert summary["precipitation_sum_mm"] == 1.2 and summary["solar_state"] == "normal"


def test_forecast_direction_metadata_uses_weather_profile_never_facing():
    spot = make_spot()
    spot.facing = 123
    spot.weather_profile = SpotWeatherProfile(
        spot_id=spot.id, active=True, quality_tier="coastal", timezone="UTC",
        elevation_m=2, coastal_normal_deg=0, physics_version="wind-v1", sectors=[],
    )
    result = get_forecast_series(spot.id, db=FakeDB(spot), client=FakeOpenMeteoClient(data_days=1), cache=InMemoryCache())
    hour = result["days"][0]["hours"][0]
    assert hour["coastal_normal_deg"] == 0
    assert hour["coastal_classification"] == "onshore"
    assert hour["wave_coastal_classification"] in {"onshore", "cross_onshore", "sideshore", "cross_offshore", "offshore", "unavailable"}
    spot.facing = 300
    repeated = get_forecast_series(spot.id, db=FakeDB(spot), client=FakeOpenMeteoClient(data_days=1), cache=InMemoryCache())
    assert repeated["days"][0]["hours"][0]["coastal_classification"] == hour["coastal_classification"]


def test_forecast_schema_preserves_direction_metadata():
    serialized = ForecastHour(
        time="2026-08-24T14:00:00+00:00", dir=0, coastal_normal_deg=359.9,
        coastal_classification="onshore", wave_coastal_classification="sideshore",
        quality_tier="coastal", stale=True,
    ).model_dump()
    assert serialized["coastal_normal_deg"] == 359.9
    assert serialized["coastal_classification"] == "onshore"
    assert serialized["stale"] is True


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


def test_forecast_hour_schema_nulls_invalid_relationships_with_diagnostics():
    hour = ForecastHour.model_validate({
        "time": "2026-01-01T00:00:00+00:00",
        "wind": 20,
        "gust": 15,
        "wind_ms": 10,
        "gust_ms": 9,
        "dir": 360,
        "precip": -1,
        "swell": math.inf,
        "wind_spread": {"low": 15, "median": 10, "high": 20, "n": 1},
    })
    assert hour.wind == 20
    assert hour.gust is None and hour.gust_ms is None and hour.dir is None and hour.precip is None and hour.swell is None
    assert hour.wind_spread is None
    assert {"gust:below_wind", "dir:invalid", "precip:invalid", "swell:invalid", "wind_spread:invalid"} <= set(hour.data_issues)


def test_forecast_summary_schema_nulls_nonfinite_negative_and_contradictory_values():
    summary = ForecastDaySummary.model_validate({
        "wind_avg": math.nan, "wind_max": 20, "gust_max": 15,
        "air_min": 10, "air_max": 5, "swell_max": -1,
        "precipitation_sum_mm": math.inf, "cloud_cover_mean_pct": 101,
    })
    assert summary.wind_avg is None and summary.gust_max is None
    assert summary.air_min is None and summary.air_max is None
    assert summary.swell_max is None and summary.precipitation_sum_mm is None
    assert summary.cloud_cover_mean_pct is None


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
