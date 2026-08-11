from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import zlib

from app.climatology.core import CALCULATION_VERSION, calculate, count_sessions


def _payload(rows):
    raw = json.dumps(rows, separators=(",", ":")).encode()
    return {
        "version": CALCULATION_VERSION,
        "encoding": "zlib+base64-json",
        "samples": base64.b64encode(zlib.compress(raw)).decode(),
    }


def _hour(year, month, day, hour):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() // 3600)


def _month_rows(speed=16, direction=0, wave=1.2, period=9):
    rows = []
    for year in (2023, 2024):
        for month, days in ((1, 31), (2, 7)):
            for day in range(1, days + 1):
                for hour in range(8, 18):
                    rows.append([_hour(year, month, day, hour), speed, direction, wave, period, 270])
    return rows


def _calc(rows, **kw):
    args = dict(month=1, threshold=14, view="wind", sport="kitesurf",
                level="advanced", material="standard", editorial={})
    args.update(kw)
    return calculate(_payload(rows), **args)


def test_two_consecutive_hours_make_session_but_isolated_hour_does_not():
    assert count_sessions([(8, True), (9, True)]) == 1
    assert count_sessions([(8, True), (10, True)]) == 0
    assert count_sessions([(8, True), (9, False), (10, True)]) == 0


def test_higher_wind_threshold_never_increases_hours():
    rows = _month_rows(speed=16)
    low = _calc(rows, threshold=14)
    high = _calc(rows, threshold=18)
    assert low["months"][0]["hours_per_week"] >= high["months"][0]["hours_per_week"]


def test_rolling_windows_may_cross_month_boundary():
    result = _calc(_month_rows())
    # Starts near the end of January are valid because February samples exist.
    assert any(point["start_day"] == 31 for point in result["details"]["within_month"])


def test_spot_direction_is_only_applied_in_result_view():
    rows = _month_rows(direction=180)
    editorial = {"usable_wind_directions": {"min": 0, "max": 45}}
    wind = _calc(rows, view="wind", editorial=editorial)
    result = _calc(rows, view="result", editorial=editorial)
    assert wind["months"][0]["hours_per_week"] > 0
    assert result["months"][0]["hours_per_week"] == 0


def test_wavekite_requires_wave_at_same_timestamp():
    rows = _month_rows(wave=None, period=None)
    result = _calc(rows, view="result", sport="wavekite")
    assert result["months"][0]["hours_per_week"] == 0
    assert result["filters"]["rejections"]["wave_data_missing"] > 0
