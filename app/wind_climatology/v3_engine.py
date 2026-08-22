"""Pure V3 session/reliability engine.  No persistence and no provider I/O."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np

from app.era5.solar import daylight_mask
from app.wind_climatology.v3_direction import canonical_windows, direction_matches
from app.wind_climatology.v3_time import expected_hours_by_week, seasonal_week, utc_datetime

ALGORITHM_VERSION = "wind-climatology-v3.0"
SESSION_HOURS = 3
SUCCESSFUL_DAYS = 2
COMPLETENESS_THRESHOLD = 0.95
MIN_SAMPLE_YEARS = 15
DirectionMode = Literal["all", "usable"]


@dataclass(frozen=True)
class Hour:
    utc: datetime
    local: datetime
    speed_kn: float | None
    direction_deg: float | None
    daylight: bool


@dataclass
class AggregationContext:
    grouped: dict[tuple[int, int], list[Hour]]
    expected: dict[tuple[int, int], int]
    start_year: int
    end_year: int


def variant_specs(include_usable: bool) -> list[tuple[int, int | None, DirectionMode]]:
    modes: list[DirectionMode] = ["all", "usable"] if include_usable else ["all"]
    specs = []
    for mode in modes:
        for low in range(5, 41):
            for high in range(low + 1, 41):
                specs.append((low, high, mode))
            specs.append((low, None, mode))
    return specs


def variant_key(low: int, high: int | None, mode: DirectionMode) -> str:
    return f"{low}:{'plus' if high is None else high}:{mode}"


def prepare_hours(times, speeds_kn, directions_deg, *, timezone_name: str, spot_lat: float, spot_lon: float) -> list[Hour]:
    if not (len(times) == len(speeds_kn) == len(directions_deg)):
        raise ValueError("V3 time, speed and direction arrays differ")
    utc = [utc_datetime(value) for value in times]
    if any(right <= left for left, right in zip(utc, utc[1:])):
        raise ValueError("V3 timestamps must be unique and strictly increasing")
    tz = ZoneInfo(timezone_name)
    daylight = daylight_mask(np.asarray([np.datetime64(item.replace(tzinfo=None)) for item in utc], dtype="datetime64[s]"), spot_lat, spot_lon)
    result = []
    for instant, speed, direction, is_day in zip(utc, speeds_kn, directions_deg, daylight):
        valid_speed = float(speed) if speed is not None and np.isfinite(speed) and float(speed) >= 0 else None
        valid_direction = float(direction) % 360 if direction is not None and np.isfinite(direction) else None
        result.append(Hour(instant, instant.astimezone(tz), valid_speed, valid_direction, bool(is_day)))
    return result


def _sessions(qualified: list[Hour]) -> list[int]:
    if not qualified:
        return []
    sessions, run = [], [qualified[0]]
    for item in qualified[1:]:
        previous = run[-1]
        continuous = item.utc - previous.utc == timedelta(hours=1) and item.local.date() == previous.local.date()
        if continuous:
            run.append(item)
        else:
            if len(run) >= SESSION_HOURS:
                sessions.append(len(run))
            run = [item]
    if len(run) >= SESSION_HOURS:
        sessions.append(len(run))
    return sessions


def _percentile(values: list[int], q: int) -> float:
    return round(float(np.percentile(values, q)), 2) if values else 0.0


def _quality(sample_years: int) -> str:
    if sample_years >= 18:
        return "high"
    if sample_years >= MIN_SAMPLE_YEARS:
        return "limited"
    return "insufficient"


def prepare_context(hours: list[Hour], *, start_year: int, end_year: int, timezone_name: str) -> AggregationContext:
    grouped: dict[tuple[int, int], list[Hour]] = defaultdict(list)
    for hour in hours:
        if start_year <= hour.local.year <= end_year:
            grouped[(hour.local.year, seasonal_week(hour.local.date()))].append(hour)
    expected = {(year, week): count for year in range(start_year, end_year + 1) for week, count in expected_hours_by_week(year, timezone_name).items()}
    return AggregationContext(grouped, expected, start_year, end_year)


def _aggregate_context(context: AggregationContext, *, min_wind_kn: int, max_wind_kn: int | None, direction_mode: DirectionMode, windows: list[dict[str, float]]) -> dict:
    year_week = {}
    for year in range(context.start_year, context.end_year + 1):
        for week in range(1, 53):
            rows = context.grouped[(year, week)]
            valid_values = sum(1 for row in rows if row.speed_kn is not None and (direction_mode == "all" or row.direction_deg is not None))
            completeness = valid_values / context.expected[(year, week)]
            valid = completeness >= COMPLETENESS_THRESHOLD
            days: dict[object, list[Hour]] = defaultdict(list)
            if valid:
                for row in rows:
                    speed_ok = row.speed_kn is not None and row.speed_kn >= min_wind_kn and (max_wind_kn is None or row.speed_kn < max_wind_kn)
                    direction_ok = direction_mode == "all" or direction_matches(row.direction_deg, windows)
                    if row.daylight and speed_ok and direction_ok:
                        days[row.local.date()].append(row)
            sessions_by_day = [_sessions(day_rows) for day_rows in days.values()]
            usable_days = sum(bool(items) for items in sessions_by_day)
            session_hours = sum(sum(items) for items in sessions_by_day)
            longest = max((max(items) for items in sessions_by_day if items), default=0)
            year_week[(year, week)] = {"valid": valid, "completeness": completeness, "usable_days": usable_days, "session_hours": session_hours, "longest_session": longest}

    weeks = []
    for week in range(1, 53):
        samples = [year_week[(year, week)] for year in range(context.start_year, context.end_year + 1) if year_week[(year, week)]["valid"]]
        sample_years = len(samples)
        successful_years = sum(row["usable_days"] >= SUCCESSFUL_DAYS for row in samples)
        days = [row["usable_days"] for row in samples]
        session_hours = [row["session_hours"] for row in samples]
        longest = [row["longest_session"] for row in samples]
        quality = _quality(sample_years)
        reliable = quality != "insufficient"
        probability = lambda threshold: round(sum(value >= threshold for value in days) / sample_years * 100, 2) if sample_years and reliable else None
        weeks.append({
            "week": week,
            "sample_years": sample_years,
            "successful_years": successful_years,
            "reliability_percent": round(successful_years / sample_years * 100, 2) if sample_years and reliable else None,
            "probability_at_least_1_day": probability(1),
            "probability_at_least_2_days": probability(2),
            "probability_at_least_3_days": probability(3),
            "median_usable_days": round(float(median(days)), 2) if days and reliable else None,
            "median_session_hours": round(float(median(session_hours)), 2) if session_hours and reliable else None,
            "p25_session_hours": _percentile(session_hours, 25) if reliable else None,
            "p75_session_hours": _percentile(session_hours, 75) if reliable else None,
            "median_longest_session": round(float(median(longest)), 2) if longest and reliable else None,
            "quality_status": quality,
        })
    return {"min_wind_kn": min_wind_kn, "max_wind_kn": max_wind_kn, "direction_mode": direction_mode, "weeks": weeks}


def aggregate_variant(hours: list[Hour], *, start_year: int, end_year: int, timezone_name: str = "UTC", min_wind_kn: int = 15, max_wind_kn: int | None = 20, direction_mode: DirectionMode = "all", usable_windows=None) -> dict:
    if not 5 <= min_wind_kn <= 40 or (max_wind_kn is not None and not min_wind_kn < max_wind_kn <= 40):
        raise ValueError("invalid V3 wind window")
    windows = canonical_windows(usable_windows)
    if direction_mode == "usable" and not windows:
        raise ValueError("usable mode requires reviewed direction windows")
    context = prepare_context(hours, start_year=start_year, end_year=end_year, timezone_name=timezone_name)
    return _aggregate_context(context, min_wind_kn=min_wind_kn, max_wind_kn=max_wind_kn, direction_mode=direction_mode, windows=windows)


def build_variant_cube(hours: list[Hour], *, start_year: int, end_year: int, timezone_name: str = "UTC", usable_windows=None) -> dict[str, dict]:
    windows = canonical_windows(usable_windows)
    context = prepare_context(hours, start_year=start_year, end_year=end_year, timezone_name=timezone_name)
    return {
        variant_key(low, high, mode): _aggregate_context(context, min_wind_kn=low, max_wind_kn=high, direction_mode=mode, windows=windows)
        for low, high, mode in variant_specs(bool(windows))
    }
