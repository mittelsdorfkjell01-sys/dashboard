from __future__ import annotations

import calendar
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

from app.era5.solar import daylight_mask

ALGORITHM_VERSION = "wind-climatology-v2.0"
METHOD_VERSION = "wind-availability-v2"
WIND_WINDOWS = {"10_15": (10, 15), "15_20": (15, 20), "20_30": (20, 30), "30_plus": (30, None)}


def section_for_day(day: int) -> int:
    return 1 if day <= 7 else 2 if day <= 14 else 3 if day <= 21 else 4


def date_range(month: int, section: int, year: int | None = None) -> tuple[int, int]:
    end = (calendar.monthrange(year or 2021, month)[1] if section == 4 else section * 7)
    return ((section - 1) * 7 + 1, end)


def speed_bin(speed: float) -> int:
    if not np.isfinite(speed) or speed < 0:
        raise ValueError("wind speed must be finite and non-negative")
    return min(int(np.floor(speed)), 50)


def _parse_times(times: list[str | int | float], tz: ZoneInfo) -> tuple[list[datetime], np.ndarray]:
    local, utc = [], []
    for value in times:
        if isinstance(value, (int, float)):
            aware = datetime.fromtimestamp(value, timezone.utc)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            aware = parsed.replace(tzinfo=tz).astimezone(timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        local.append(aware.astimezone(tz))
        utc.append(np.datetime64(aware.replace(tzinfo=None)))
    return local, np.asarray(utc, dtype="datetime64[s]")


def aggregate(times: list[str | int | float], speeds_kn: list[float], *, timezone_name: str, spot_lat: float, spot_lon: float, start_year: int, end_year: int) -> tuple[list[dict], dict]:
    if len(times) != len(speeds_kn):
        raise ValueError("time and wind arrays differ")
    if end_year - start_year + 1 != 20:
        raise ValueError("exactly 20 complete years required")
    tz = ZoneInfo(timezone_name)
    locals_, utc = _parse_times(times, tz)
    daylight = daylight_mask(utc, spot_lat, spot_lon)
    buckets: dict[tuple[int, int, int], dict] = {}
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            for section in range(1, 5):
                first, last = date_range(month, section, year)
                buckets[(year, month, section)] = {"year": year, "month": month, "section": section, "day_start": first, "day_end": last, "calendar_days": last - first + 1, "daylight_hours": 0, "bins": [0] * 51, "complete": True}
    for local, raw_speed, is_day in zip(locals_, speeds_kn, daylight):
        if local.year < start_year or local.year > end_year or not is_day:
            continue
        if raw_speed is None or not np.isfinite(raw_speed):
            raise ValueError(f"missing daylight wind observation at {local.isoformat()}")
        row = buckets[(local.year, local.month, section_for_day(local.day))]
        row["bins"][speed_bin(float(raw_speed))] += 1
        row["daylight_hours"] += 1
    annual = list(buckets.values())
    public_sections = []
    for month in range(1, 13):
        for section in range(1, 5):
            rows = [buckets[(year, month, section)] for year in range(start_year, end_year + 1)]
            bins = [sum(r["bins"][i] for r in rows) for i in range(51)]
            daylight_hours = sum(bins)
            days = sum(r["calendar_days"] for r in rows)
            if daylight_hours <= 0:
                raise ValueError(f"no daylight observations for month={month} section={section}")
            windows = {}
            for key, (low, high) in WIND_WINDOWS.items():
                count = sum(bins[low:(high if high is not None else 51)])
                windows[key] = {"hours": count, "percent": round(count / daylight_hours * 100, 2), "hours_per_day": round(count / days, 2)}
            first, last = date_range(month, section)
            public_sections.append({"month": month, "section": section, "day_start": first, "day_end": last if section < 4 else "month_end", "date_label": f"{first}.–{last if section < 4 else 'Monatsende'}", "calendar_days": days, "daylight_hours": daylight_hours, "windows": windows})
    public = {"method_version": METHOD_VERSION, "algorithm_version": ALGORITHM_VERSION, "period": {"start_year": start_year, "end_year": end_year}, "model": "ERA5", "wind_height_m": 10, "unit": "kn", "sections": public_sections}
    validate(annual, public)
    return annual, public


def validate(annual: list[dict], public: dict) -> None:
    years = {r["year"] for r in annual}
    if len(years) != 20 or len(annual) != 20 * 48 or len(public.get("sections", [])) != 48:
        raise ValueError("incomplete 20-year/48-section aggregation")
    for row in annual:
        if len(row["bins"]) != 51 or sum(row["bins"]) != row["daylight_hours"]:
            raise ValueError("wind-bin conservation failed")
    for section in public["sections"]:
        for metric in section["windows"].values():
            if not 0 <= metric["percent"] <= 100 or not 0 <= metric["hours_per_day"] <= 24:
                raise ValueError("metric outside valid range")
