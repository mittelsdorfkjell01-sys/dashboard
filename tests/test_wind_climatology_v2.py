from datetime import datetime, timezone
import importlib

import pytest

from app.wind_climatology.aggregate import aggregate, date_range, section_for_day, speed_bin
from app.wind_climatology.client import WindHistoryClient
from app.wind_climatology.service import full_year_window


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (0.999, 0), (14.999, 14), (15, 15), (20, 20), (30, 30), (49.999, 49), (50, 50), (90, 50)])
def test_one_knot_half_open_bins(value, expected):
    assert speed_bin(value) == expected


def test_sections_are_month_local_and_leap_aware():
    assert [section_for_day(d) for d in (1, 7, 8, 14, 15, 21, 22, 29)] == [1, 1, 2, 2, 3, 3, 4, 4]
    assert date_range(2, 4, 2024) == (22, 29)
    assert date_range(2, 4, 2023) == (22, 28)


def test_window_is_last_twenty_completed_years():
    from datetime import date
    assert full_year_window(date(2026, 8, 16)) == (2006, 2025)


def test_explicit_era5_nearest_cell_and_knots_are_requested():
    captured = {}
    expected = (datetime(2026, 1, 1) - datetime(2006, 1, 1)).days * 24
    def fake(_url, params):
        captured.update(params)
        return {"latitude": 54.25, "longitude": 10.0, "timezone": "Europe/Berlin", "hourly_units": {"wind_speed_10m": "kn"}, "hourly": {"time": [0] * expected, "wind_speed_10m": [15.0] * expected}}
    result = WindHistoryClient(fake).fetch(54.2, 10.1, 2006, 2025)
    assert captured["models"] == "era5"
    assert captured["wind_speed_unit"] == "kn"
    assert captured["cell_selection"] == "nearest"
    assert captured["timeformat"] == "unixtime"
    assert (result["actual_lat"], result["actual_lon"]) == (54.25, 10.0)


def test_unexpected_unit_or_model_fails_closed():
    base = {"latitude": 1, "longitude": 2, "timezone": "UTC", "hourly": {"time": [0], "wind_speed_10m": [15]}}
    with pytest.raises(RuntimeError, match="unit"):
        WindHistoryClient(lambda *_: {**base, "hourly_units": {"wind_speed_10m": "km/h"}}).fetch(1, 2, 2006, 2025)
    with pytest.raises(RuntimeError, match="model"):
        WindHistoryClient(lambda *_: {**base, "model": "best_match", "hourly_units": {"wind_speed_10m": "kn"}}).fetch(1, 2, 2006, 2025)


def test_aggregation_has_48_unsmoothed_sections_and_full_denominator(monkeypatch):
    times, speeds = [], []
    for year in range(2006, 2026):
        for month in range(1, 13):
            for day, speed in ((1, 9.9), (8, 10.0), (15, 15.0), (22, 20.0)):
                times.append(datetime(year, month, day, 12, tzinfo=timezone.utc).timestamp())
                speeds.append(speed)
    aggregate_module = importlib.import_module("app.wind_climatology.aggregate")
    monkeypatch.setattr(aggregate_module, "daylight_mask", lambda times, *_: [True] * len(times))
    annual, public = aggregate(times, speeds, timezone_name="Europe/Berlin", spot_lat=54, spot_lon=10, start_year=2006, end_year=2025)
    assert len(annual) == 960
    assert len(public["sections"]) == 48
    assert public["sections"][0]["windows"]["10_15"]["percent"] == 0
    assert public["sections"][1]["windows"]["10_15"]["percent"] == 100
    assert public["sections"][2]["windows"]["15_20"]["percent"] == 100
    assert public["sections"][3]["windows"]["20_30"]["percent"] == 100
    assert public["sections"][1]["windows"]["10_15"]["hours_per_day"] == round(20 / 140, 2)
