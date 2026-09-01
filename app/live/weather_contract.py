"""Weather W1 contract helpers. No provider payloads or model internals escape here."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEATHER_CONTRACT_VERSION = "weather-v6"
MODEL_NOWCAST_STALE_SECONDS = 15 * 60
MEASUREMENT_STALE_SECONDS = 30 * 60
ATMOSPHERE_FORECAST_STALE_SECONDS = 3 * 60 * 60
MARINE_FORECAST_STALE_SECONDS = 6 * 60 * 60
WMO_MAPPING_VERSION = "wmo-v1"


class Availability(StrEnum):
    AVAILABLE = "available"
    AVAILABLE_STALE = "available_stale"
    NOT_APPLICABLE_INLAND = "not_applicable_inland"
    UNAVAILABLE_OUT_OF_RANGE = "unavailable_out_of_range"
    UNAVAILABLE_PROVIDER = "unavailable_provider"
    UNKNOWN_LOCATION_TYPE = "unknown_location_type"


_WMO = {
    0: "clear", 1: "mainly_clear", 2: "partly_cloudy", 3: "overcast",
    45: "fog", 48: "fog",
    **{code: "drizzle" for code in (51, 53, 55, 56, 57)},
    **{code: "rain" for code in (61, 63, 65, 66, 67)},
    **{code: "snow" for code in (71, 73, 75, 77)},
    **{code: "rain_showers" for code in (80, 81, 82)},
    **{code: "snow_showers" for code in (85, 86)},
    **{code: "thunderstorm" for code in (95, 96, 99)},
}


def weather_condition(code) -> str:
    return _WMO.get(code, "unknown") if isinstance(code, int) and not isinstance(code, bool) else "unknown"


def valid_number(value, *, minimum=None, maximum=None):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return None
    number = float(value)
    if minimum is not None and number < minimum or maximum is not None and number > maximum:
        return None
    return number


def provider_timezone(payload: dict) -> str:
    name = payload.get("timezone") or "UTC"
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return "UTC"
    return name


def provider_time_utc(value: str | None, timezone_name: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed.astimezone(timezone.utc)
    except (ValueError, ZoneInfoNotFoundError):
        return None


def age_seconds(value: datetime | None, *, now: datetime | None = None) -> int | None:
    """Age of a real timestamp. Unknown and future instants stay explicit."""
    if value is None:
        return None
    reference = now or datetime.now(timezone.utc)
    return max(0, int((reference - value.astimezone(timezone.utc)).total_seconds()))


def is_stale(*ages: int | None, threshold_seconds: int) -> bool:
    known = [age for age in ages if age is not None]
    return not known or max(known) > threshold_seconds


def provider_axis_utc(values: list, timezone_name: str) -> list[datetime | None]:
    """Resolve a local provider axis monotonically, including repeated DST hours."""
    zone = ZoneInfo(timezone_name)
    result: list[datetime | None] = []
    previous: datetime | None = None
    for value in values:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                candidates = [parsed.astimezone(timezone.utc)]
            else:
                candidates = sorted({
                    parsed.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
                    for fold in (0, 1)
                })
            chosen = next((candidate for candidate in candidates if previous is None or candidate > previous), None)
        except (ValueError, ZoneInfoNotFoundError):
            chosen = None
        result.append(chosen)
        if chosen is not None:
            previous = chosen
    return result


def marine_classification(spot) -> Availability:
    kinds = set(getattr(spot, "water_type", None) or [])
    if kinds & {"ocean", "sea", "lagoon"}:
        return Availability.AVAILABLE
    if kinds & {"lake", "river", "reservoir"}:
        return Availability.NOT_APPLICABLE_INLAND
    return Availability.UNKNOWN_LOCATION_TYPE


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
