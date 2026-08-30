"""DST-safe local-day and comparable seven-day seasonal windows for V3."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

SEASONAL_WEEK_COUNT = 52
SEASONAL_WEEK_DAYS = 7
_TEMPLATE_YEAR = 2001  # Common year: stable month/day anchors after February.
_TEMPLATE_START = date(_TEMPLATE_YEAR, 1, 1)


def seasonal_day_index(value: date) -> int:
    """Return the date's stable common-year position.

    February 29 shares February 28's position.  Public V3 no longer partitions
    all 365/366 dates into uneven buckets; it samples 52 comparable seven-day
    windows instead, so this helper is retained only as a stable seasonal index.
    """
    day = 28 if value.month == 2 and value.day == 29 else value.day
    return (date(_TEMPLATE_YEAR, value.month, day) - _TEMPLATE_START).days


@lru_cache
def _week_bounds() -> dict[int, tuple[date, date]]:
    """Return 52 non-overlapping, exactly seven-day reference windows.

    The anchors follow the common-year calendar (Jan 1–7, Jan 8–14, …,
    Dec 24–30).  December 31 and February 29 are deliberately not assigned:
    omitting a tiny, explicit share is preferable to giving two chart bars an
    eighth day and a systematically higher chance of satisfying the two-day
    success rule.
    """
    bounds: dict[int, tuple[date, date]] = {}
    for week in range(1, SEASONAL_WEEK_COUNT + 1):
        template_start = _TEMPLATE_START + timedelta(days=(week - 1) * SEASONAL_WEEK_DAYS)
        start = template_start
        bounds[week] = (start, start + timedelta(days=SEASONAL_WEEK_DAYS - 1))
    return bounds


def seasonal_week(value: date) -> int | None:
    """Return the comparable V3 window containing ``value``, if represented."""
    if (value.month, value.day) == (2, 29):
        return None
    index = seasonal_day_index(value)
    if index >= SEASONAL_WEEK_COUNT * SEASONAL_WEEK_DAYS:
        return None
    return index // SEASONAL_WEEK_DAYS + 1


def utc_datetime(value: str | int | float | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, timezone.utc)
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("V3 timestamps must carry an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def local_datetime(value: str | int | float | datetime, timezone_name: str) -> datetime:
    return utc_datetime(value).astimezone(ZoneInfo(timezone_name))


def expected_hours_by_week(year: int, timezone_name: str) -> dict[int, int]:
    """Real UTC hours in each seven-local-day window, including DST."""
    tz = ZoneInfo(timezone_name)
    counts = {week: 0 for week in range(1, SEASONAL_WEEK_COUNT + 1)}
    current = date(year, 1, 1)
    while current.year == year:
        week = seasonal_week(current)
        if week is not None:
            following = current + timedelta(days=1)
            start = datetime.combine(current, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
            end = datetime.combine(following, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
            counts[week] += int((end - start).total_seconds() // 3600)
        current += timedelta(days=1)
    return counts


def week_date_range(week: int) -> tuple[date, date]:
    """Fixed seven-day month/day span covered by one seasonal chart week.

    Single source of truth for the 52-week calendar so the frontend never
    recomputes seasonal boundaries independently.
    """
    if week not in range(1, SEASONAL_WEEK_COUNT + 1):
        raise ValueError("seasonal week must be between 1 and 52")
    return _week_bounds()[week]
