"""DST-safe local-day and stable 52-seasonal-week helpers for V3."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

SEASONAL_WEEK_COUNT = 52
_LEAP_TEMPLATE_YEAR = 2000


def seasonal_day_index(value: date) -> int:
    """Return the date's fixed 0..365 position in a leap-year template.

    Month/day, rather than the current year's ordinal, is mapped into the fixed
    leap template.  February 29 owns its own position and never shifts dates in
    March through December between leap and common years.
    """
    return date(_LEAP_TEMPLATE_YEAR, value.month, value.day).timetuple().tm_yday - 1


def seasonal_week(value: date) -> int:
    """Map every calendar date to one stable, one-based seasonal week (1..52)."""
    return min(SEASONAL_WEEK_COUNT, seasonal_day_index(value) * SEASONAL_WEEK_COUNT // 366 + 1)


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
    """Real UTC hours belonging to each local seasonal week, including DST."""
    tz = ZoneInfo(timezone_name)
    counts = {week: 0 for week in range(1, 53)}
    current = date(year, 1, 1)
    while current.year == year:
        following = current + timedelta(days=1)
        start = datetime.combine(current, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
        end = datetime.combine(following, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
        counts[seasonal_week(current)] += int((end - start).total_seconds() // 3600)
        current = following
    return counts


@lru_cache
def _week_bounds() -> dict[int, tuple[date, date]]:
    days_by_week: dict[int, list[date]] = defaultdict(list)
    current = date(_LEAP_TEMPLATE_YEAR, 1, 1)
    while current.year == _LEAP_TEMPLATE_YEAR:
        days_by_week[seasonal_week(current)].append(current)
        current += timedelta(days=1)
    return {week: (days[0], days[-1]) for week, days in days_by_week.items()}


def week_date_range(week: int) -> tuple[date, date]:
    """Fixed month/day span (year-independent) covered by one seasonal week.

    Single source of truth for the 52-week calendar so the frontend never
    recomputes seasonal boundaries independently.
    """
    return _week_bounds()[week]
