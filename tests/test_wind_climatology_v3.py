from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.wind_climatology.v3_artifact import decode_cube, encode_cube
from app.wind_climatology.v3_direction import canonical_windows, direction_matches
from app.wind_climatology.v3_engine import Hour, _sessions, aggregate_variant, variant_specs
from app.wind_climatology.v3_time import expected_hours_by_week, seasonal_week
from app.wind_climatology.v3_service import _config, _hash, error_category, state_label


def hour(at: datetime, speed=16.0, direction=0.0, daylight=True) -> Hour:
    return Hour(at, at, speed, direction, daylight)


def test_sessions_require_three_real_consecutive_same_day_hours():
    start = datetime(2025, 1, 1, 10, tzinfo=timezone.utc)
    assert _sessions([hour(start)]) == []
    assert _sessions([hour(start), hour(start + timedelta(hours=1))]) == []
    assert _sessions([hour(start + timedelta(hours=i)) for i in range(3)]) == [3]
    assert _sessions([hour(start + timedelta(hours=i)) for i in range(4)]) == [4]
    assert _sessions([hour(start), hour(start + timedelta(hours=1)), hour(start + timedelta(hours=3))]) == []


def test_local_day_change_breaks_session_even_when_utc_is_continuous():
    values = [hour(datetime(2025, 1, 1, 22 + i, tzinfo=timezone.utc)) for i in range(2)]
    last = hour(datetime(2025, 1, 2, 0, tzinfo=timezone.utc))
    assert _sessions(values + [last]) == []


def _week_one_hours(session_years: set[int], *, concentrated_days=2, direction=0.0):
    rows = []
    for year in range(2006, 2026):
        current = datetime(year, 1, 1, tzinfo=timezone.utc)
        while current.year == year and seasonal_week(current.date()) == 1:
            for clock in range(24):
                speed = 16.0 if year in session_years and current.day <= concentrated_days and 10 <= clock <= 12 else 0.0
                rows.append(hour(current.replace(hour=clock), speed=speed, direction=direction, daylight=True))
            current += timedelta(days=1)
    return rows


def test_yearly_regularity_beats_same_hours_concentrated_in_fewer_years():
    # Both fixtures contain 42 qualified hours: 7 years × 2 days × 3 hours
    # versus 2 years × 7 days × 3 hours.
    regular = aggregate_variant(_week_one_hours(set(range(2006, 2013))), start_year=2006, end_year=2025)
    concentrated = aggregate_variant(_week_one_hours({2006, 2007}, concentrated_days=7), start_year=2006, end_year=2025)
    assert regular["weeks"][0]["reliability_percent"] > concentrated["weeks"][0]["reliability_percent"]


def test_direction_windows_are_strict_and_support_wrap_and_multiple_ranges():
    windows = canonical_windows([{"min": 315, "max": 45}, {"min": 120, "max": 150}])
    assert direction_matches(350, windows)
    assert direction_matches(20, windows)
    assert direction_matches(135, windows)
    assert not direction_matches(90, windows)
    assert not direction_matches(None, windows)
    assert not direction_matches(20, [])


def test_usable_filter_cannot_increase_result_and_missing_definition_is_rejected():
    rows = _week_one_hours(set(range(2006, 2026)), direction=90)
    all_result = aggregate_variant(rows, start_year=2006, end_year=2025, direction_mode="all")
    usable = aggregate_variant(rows, start_year=2006, end_year=2025, direction_mode="usable", usable_windows=[{"min": 315, "max": 45}])
    assert usable["weeks"][0]["reliability_percent"] <= all_result["weeks"][0]["reliability_percent"]
    with pytest.raises(ValueError, match="reviewed"):
        aggregate_variant(rows, start_year=2006, end_year=2025, direction_mode="usable")


@pytest.mark.parametrize("break_kind", ["night", "speed", "direction"])
def test_night_unmatched_speed_and_unmatched_direction_break_qualification(break_kind):
    rows = _week_one_hours(set(range(2006, 2026)))
    for index, item in enumerate(rows):
        if item.speed_kn == 16 and item.utc.hour == 11:
            rows[index] = Hour(item.utc, item.local, 0 if break_kind == "speed" else item.speed_kn, 180 if break_kind == "direction" else item.direction_deg, False if break_kind == "night" else item.daylight)
    result = aggregate_variant(rows, start_year=2006, end_year=2025, direction_mode="usable", usable_windows=[{"min": 315, "max": 45}])
    assert result["weeks"][0]["reliability_percent"] == 0


def test_dst_uses_real_utc_continuity_without_artificial_gap():
    tz = ZoneInfo("Europe/Berlin")
    utc_rows = [datetime(2025, 3, 30, hour, tzinfo=timezone.utc) for hour in (0, 1, 2)]
    rows = [Hour(item, item.astimezone(tz), 16, 0, True) for item in utc_rows]
    assert [row.local.hour for row in rows] == [1, 3, 4]
    assert _sessions(rows) == [3]


def test_seasonal_week_is_complete_stable_and_ungloothed():
    for year in (2023, 2024):
        current, seen = date(year, 1, 1), []
        while current.year == year:
            seen.append(seasonal_week(current))
            current += timedelta(days=1)
        assert len(seen) == 365 + (year == 2024)
        assert set(seen) == set(range(1, 53))
    assert seasonal_week(date(2023, 3, 1)) == seasonal_week(date(2024, 3, 1))
    assert sum(expected_hours_by_week(2024, "Europe/Berlin").values()) == 366 * 24


def test_missing_values_and_hours_reduce_completeness_not_calm_wind():
    rows = _week_one_hours(set(range(2006, 2026)))
    # Remove enough real timestamps in one year/week to cross below 95%.
    rows = [row for row in rows if not (row.local.year == 2006 and row.local.day == 1)]
    result = aggregate_variant(rows, start_year=2006, end_year=2025)
    assert result["weeks"][0]["sample_years"] == 19
    assert result["weeks"][0]["quality_status"] == "high"


def test_fewer_than_fifteen_years_suppresses_reliability():
    rows = [row for row in _week_one_hours(set(range(2006, 2026))) if row.local.year < 2020]
    result = aggregate_variant(rows, start_year=2006, end_year=2025)
    assert result["weeks"][0]["sample_years"] == 14
    assert result["weeks"][0]["reliability_percent"] is None
    assert result["weeks"][0]["quality_status"] == "insufficient"


def test_variant_space_and_artifact_are_deterministic():
    specs = variant_specs(include_usable=False)
    assert (15, 20, "all") in specs and (40, None, "all") in specs
    assert all(high is None or low < high for low, high, _ in specs)
    blob_a, hash_a = encode_cube({"15:20:all": {"weeks": list(range(52))}})
    blob_b, hash_b = encode_cube({"15:20:all": {"weeks": list(range(52))}})
    assert (blob_a, hash_a) == (blob_b, hash_b)
    assert decode_cube(blob_a)["15:20:all"]["weeks"] == list(range(52))


def test_config_hash_changes_with_coordinates_and_directions():
    base = dict(start=2006, end=2025, spot_coords=(1, 2), requested_coords=(1, 2), actual_coords=(1, 2), windows=[])
    original = _hash(_config(**base))
    assert _hash(_config(**{**base, "spot_coords": (1.1, 2)})) != original
    assert _hash(_config(**{**base, "windows": [{"start_deg": 315, "end_deg": 45}]})) != original


class _Run:
    def __init__(self, status, quality=None):
        self.status = status
        self.quality_metadata = quality or {}


def test_dashboard_state_preserves_active_version_during_refresh_and_failure():
    active = _Run("ready")
    assert state_label(_Run("processing"), active, False) == "refresh_processing"
    assert state_label(_Run("failed"), active, False) == "failed_active_preserved"
    assert state_label(_Run("failed"), None, False) == "failed_no_active"
    assert state_label(active, active, True) == "stale"


def test_dashboard_error_categories_are_sanitized():
    assert error_category("Open-Meteo timeout") == "provider"
    assert error_category("invalid timezone") == "validation"
    assert error_category("bad grid coordinate") == "coordinates"
    assert error_category("secret implementation detail") == "unknown"
