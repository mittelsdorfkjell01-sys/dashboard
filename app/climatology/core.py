"""Hourly, calendar-aware climatology calculations.

The compact sample payload is derived while ERA5 data is in memory.  It keeps the
minimum information needed to recompute arbitrary wind thresholds and sessions;
it deliberately does not manufacture local corrections which are absent from the
historical source.
"""

from __future__ import annotations

import base64
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import math
from statistics import median
import zlib
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np

from app.era5.components import compute_wind_components
from app.era5.solar import daylight_mask
from app.scoring.evaluate import evaluate_conditions
from app.scoring.params import SCORING_PARAMS_VERSION, get_params

CALCULATION_VERSION = 2
SESSION_MIN_CONSECUTIVE_HOURS = 2
MIN_MONTH_COVERAGE = 0.80
MIN_WIND_THRESHOLD_KT = 6
MAX_WIND_THRESHOLD_KT = 35
VALID_LEVELS = {"beginner", "advanced", "expert"}
VALID_MATERIALS = {"standard", "lightwind", "highwind"}
WIND_SPORTS = {"kitesurf", "windsurf", "wing", "wavekite"}

# Material affects only the ideal/usable wind band and is centralized/versioned.
MATERIAL_OFFSETS_V1 = {
    "kitesurf": {"standard": (0, 0), "lightwind": (-3, -3), "highwind": (3, 5)},
    "windsurf": {"standard": (0, 0), "lightwind": (-2, -2), "highwind": (3, 5)},
    "wing": {"standard": (0, 0), "lightwind": (-2, -3), "highwind": (2, 4)},
    "wavekite": {"standard": (0, 0), "lightwind": (-2, -3), "highwind": (3, 4)},
}


def encode_hourly_samples(series: dict, lat: float, lon: float, timezone_name: str | None = None) -> dict:
    """Pack valid daylight samples into compressed JSON stored with climatology."""
    times = np.asarray(series["time"]).astype("datetime64[h]")
    comp = compute_wind_components(series["u10"], series["v10"])
    valid = daylight_mask(times, lat, lon) & np.isfinite(comp["speed_kt"]) & np.isfinite(comp["dir_deg"])
    epoch = times.astype("int64")
    swh = np.asarray(series.get("swh", np.full(len(times), np.nan)), dtype=float)
    mwp = np.asarray(series.get("mwp", np.full(len(times), np.nan)), dtype=float)
    mwd = np.asarray(series.get("mwd", np.full(len(times), np.nan)), dtype=float)

    rows = []
    for i in np.flatnonzero(valid):
        rows.append([
            int(epoch[i]), round(float(comp["speed_kt"][i]), 1),
            round(float(comp["dir_deg"][i]), 1),
            None if not np.isfinite(swh[i]) else round(float(swh[i]), 2),
            None if not np.isfinite(mwp[i]) else round(float(mwp[i]), 1),
            None if not np.isfinite(mwd[i]) else round(float(mwd[i]), 1),
        ])
    raw = json.dumps(rows, separators=(",", ":")).encode()
    return {
        "version": CALCULATION_VERSION,
        "encoding": "zlib+base64-json",
        "fields": ["epoch_hour", "wind_kt", "wind_dir", "wave_m", "period_s", "wave_dir"],
        "samples": base64.b64encode(zlib.compress(raw, 9)).decode(),
        "valid_daylight_hours": len(rows),
        "total_source_hours": len(times),
        "timezone": timezone_name,
    }


@lru_cache(maxsize=8)
def _decode_samples_cached(samples: str) -> tuple[tuple, ...]:
    return tuple(tuple(row) for row in json.loads(zlib.decompress(base64.b64decode(samples))))


def decode_hourly_samples(payload: dict) -> list[list]:
    if payload.get("version") != CALCULATION_VERSION or payload.get("encoding") != "zlib+base64-json":
        raise ValueError("unsupported climatology hourly payload")
    return [list(row) for row in _decode_samples_cached(payload["samples"])]


def _pct(values: list[float], q: float) -> float | None:
    return round(float(np.percentile(values, q)), 2) if values else None


def count_sessions(hour_flags: list[tuple[int, bool]]) -> int:
    """Count runs of adjacent hourly samples; gaps always break a session."""
    sessions = run = 0
    previous_hour = None
    for hour, flag in hour_flags + [(99, False)]:
        if previous_hour is not None and hour != previous_hour + 1:
            if run >= SESSION_MIN_CONSECUTIVE_HOURS:
                sessions += 1
            run = 0
        if flag:
            run += 1
        else:
            if run >= SESSION_MIN_CONSECUTIVE_HOURS:
                sessions += 1
            run = 0
        previous_hour = hour
    return sessions


def _result_flag(row: list, threshold: float, sport: str, level: str, material: str,
                 editorial: dict, params: dict) -> tuple[bool, str | None]:
    wind, direction, wave, period, wave_dir = row[1:]
    if wind < threshold:
        return False, "threshold"
    low, high = MATERIAL_OFFSETS_V1[sport][material]
    adjusted = dict(params)
    adjusted["wind"] = dict(params["wind"])
    adjusted["wind"]["min_kt"] += low
    adjusted["wind"]["max_kt"] += high
    values = {"wind_kt": wind, "wind_dir": direction, "daylight": True}
    if sport == "wavekite":
        if wave is None or period is None or wave_dir is None:
            return False, "wave_data_missing"
        wave_cfg = params["wavekite_wave"]
        if not (wave_cfg["min_m"] <= wave <= wave_cfg["max_m"] and period >= wave_cfg["period_min_s"]):
            return False, "wave_conditions"
    result = evaluate_conditions(values, editorial, {"level": level}, sport, adjusted)
    return result["rating"] != "nein", (result.get("reasons") or [None])[0]


def calculate(payload: dict, *, month: int, threshold: float, view: str, sport: str,
              level: str, material: str, editorial: dict, confidence_meta: dict | None = None) -> dict:
    """Calculate twelve real calendar months and selected-month travel details."""
    if not 1 <= month <= 12 or not MIN_WIND_THRESHOLD_KT <= threshold <= MAX_WIND_THRESHOLD_KT:
        raise ValueError("invalid month or wind threshold")
    if view not in {"wind", "result"} or sport not in WIND_SPORTS or level not in VALID_LEVELS or material not in VALID_MATERIALS:
        raise ValueError("invalid climatology selection")
    rows = decode_hourly_samples(payload)
    params = get_params(sport)

    # tuple: absolute epoch hour, local wall-clock hour, source row, eligibility, reason
    by_day: dict[date, list[tuple[int, int, list, bool, str | None]]] = {}
    years = set()
    reason_counts: Counter[str] = Counter()
    timezone_name = payload.get("timezone")
    try:
        local_zone = ZoneInfo(timezone_name) if timezone_name else timezone.utc
    except ZoneInfoNotFoundError:
        local_zone = timezone.utc
    for row in rows:
        dt = datetime.fromtimestamp(int(row[0]) * 3600, tz=timezone.utc).astimezone(local_zone)
        d = dt.date()
        years.add(d.year)
        if view == "wind":
            ok, reason = row[1] >= threshold, None
        else:
            ok, reason = _result_flag(row, threshold, sport, level, material, editorial, params)
        if reason:
            reason_counts[reason] += 1
        by_day.setdefault(d, []).append((int(row[0]), dt.hour, row, ok, reason))

    monthly = []
    selected_daily: dict[date, dict] = {}
    per_year_month: list[float] = []
    for mo in range(1, 13):
        year_values = []
        coverage_values = []
        observed_daily_hours = [len(by_day[d]) for d in by_day if d.month == mo]
        expected_daily_hours = float(median(observed_daily_hours)) if observed_daily_hours else 0.0
        for year in sorted(years):
            dates = sorted(d for d in by_day if d.year == year and d.month == mo)
            if not dates:
                continue
            eligible = sum(sum(1 for _, _, _, ok, _ in by_day[d] if ok) for d in dates)
            available_hours = sum(len(by_day[d]) for d in dates)
            # Missing valid samples are excluded from the wind probability.  A
            # month's typical observed daylight length supplies the weekly scale.
            days_in_month = (date(year + (mo == 12), mo % 12 + 1, 1) - date(year, mo, 1)).days
            expected_hours = days_in_month * expected_daily_hours
            coverage = min(1.0, available_hours / expected_hours) if expected_hours else 0.0
            coverage_values.append(coverage)
            if coverage >= MIN_MONTH_COVERAGE:
                value = (eligible / available_hours) * expected_daily_hours * 7 if available_hours else 0.0
                year_values.append(value)
                if mo == month:
                    per_year_month.append(value)
            if mo == month:
                for d in dates:
                    entries = sorted(by_day[d], key=lambda x: x[0])
                    flags = [e[3] for e in entries]
                    selected_daily[d] = {"hours": sum(flags), "sessions": count_sessions([(e[0], e[3]) for e in entries]), "rows": entries}
        coverage = float(np.mean(coverage_values)) if coverage_values else 0.0
        monthly.append({
            "month": mo,
            "hours_per_week": round(float(np.mean(year_values)), 2) if year_values else None,
            "p25": _pct(year_values, 25), "median": _pct(year_values, 50), "p75": _pct(year_values, 75),
            "years": len(year_values), "coverage": round(coverage, 3),
            "reliable": bool(year_values) and coverage >= MIN_MONTH_COVERAGE,
        })

    # A trip starting in the selected month may extend six days beyond its end.
    # Add those actual following dates without attributing their hours to the
    # selected month's monthly statistic.
    starts = [d for d in by_day if d.month == month]
    for start in starts:
        for offset in range(7):
            d = start + timedelta(days=offset)
            if d in selected_daily or d not in by_day:
                continue
            entries = sorted(by_day[d], key=lambda x: x[0])
            flags = [e[3] for e in entries]
            selected_daily[d] = {"hours": sum(flags), "sessions": count_sessions([(e[0], e[3]) for e in entries]), "rows": entries}

    windows = []
    for start in sorted(d for d in selected_daily if d.month == month):
        days = [selected_daily.get(start + timedelta(days=i)) for i in range(7)]
        if any(day is None for day in days):
            continue
        good_days = sum(1 for day in days if day["sessions"] > 0)
        windows.append({"start_day": start.day, "hours": sum(day["hours"] for day in days),
                        "sessions": sum(day["sessions"] for day in days), "good_days": good_days})

    good_days_week = [w["good_days"] for w in windows]
    sessions_week = [w["sessions"] for w in windows]
    hours_week = [w["hours"] for w in windows]
    all_selected_rows = [e for day in selected_daily.values() for e in day["rows"]]
    speed_bins = [0, 6, 10, 14, 18, 25, 35, math.inf]
    speed_dist = []
    for lo, hi in zip(speed_bins, speed_bins[1:]):
        speed_dist.append({"from": lo, "to": None if math.isinf(hi) else hi,
                           "hours": sum(1 for e in all_selected_rows if lo <= e[2][1] < hi)})
    dirs = [0] * 16
    tod = {"morning": 0, "midday": 0, "afternoon": 0, "evening": 0}
    for _, hour, row, ok, _ in all_selected_rows:
        if not ok:
            continue
        dirs[int(round(row[2] / 22.5)) % 16] += 1
        tod["morning" if hour < 10 else "midday" if hour < 14 else "afternoon" if hour < 18 else "evening"] += 1

    coverage = monthly[month - 1]["coverage"]
    conf = "hoch" if len(per_year_month) >= 15 and coverage >= .95 else "mittel" if len(per_year_month) >= 8 and coverage >= .8 else "niedrig"
    limitations = ["Lokale Thermik und Abschattung sind in ERA5 nicht aufgelöst.", "Keine historische Stationskalibrierung vorhanden."]
    if not timezone_name:
        limitations.append("Keine gepflegte Spot-Zeitzone; Kalendertage werden in UTC abgegrenzt.")
    if view == "result":
        limitations.append("Böigkeit und Tide wurden mangels gemeinsamer historischer Zeitreihe nicht berücksichtigt.")
    return {
        "calculation_version": CALCULATION_VERSION, "scoring_version": SCORING_PARAMS_VERSION,
        "selection": {"month": month, "threshold_kt": threshold, "view": view, "sport": sport, "level": level, "material": material},
        "months": monthly,
        "details": {
            "hours_per_week": _pct(hours_week, 50), "hours_p25": _pct(hours_week, 25), "hours_p75": _pct(hours_week, 75),
            "median_good_days": _pct(good_days_week, 50), "median_sessions": _pct(sessions_week, 50),
            "chance_one_session": round(sum(v >= 1 for v in sessions_week) / len(windows), 3) if windows else None,
            "chance_three_good_days": round(sum(v >= 3 for v in good_days_week) / len(windows), 3) if windows else None,
            "chance_five_good_days": round(sum(v >= 5 for v in good_days_week) / len(windows), 3) if windows else None,
            "speed_distribution": speed_dist, "direction_distribution": dirs, "time_of_day": tod,
            "within_month": [{"start_day": d, "hours": round(float(np.mean([w["hours"] for w in windows if w["start_day"] == d])), 2)} for d in sorted({w["start_day"] for w in windows})],
            "years": len(per_year_month), "windows": len(windows), "coverage": coverage,
        },
        "filters": {"session_rule": f">={SESSION_MIN_CONSECUTIVE_HOURS} consecutive hourly samples", "rejections": dict(reason_counts)},
        "confidence": {"level": conf, "coverage": coverage, "limitations": limitations, **(confidence_meta or {})},
    }
