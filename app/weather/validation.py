"""Provider-boundary validation shared by public weather calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math


@dataclass(frozen=True)
class ValidationResult:
    value: float | None
    issues: tuple[str, ...] = ()
    hard_error: bool = False


BOUNDS = {
    "wind_speed_ms": (0.0, 75.0),
    "wind_gust_ms": (0.0, 100.0),
    "wave_height_m": (0.0, 30.0),
    "wave_period_s": (0.5, 35.0),
    "precipitation_mm": (0.0, 500.0),
    "temperature_c": (-90.0, 60.0),
    "pressure_hpa": (800.0, 1100.0),
    "direction_deg": (0.0, 359.999999),
}


def bounded_value(value, field: str) -> ValidationResult:
    """Reject non-finite, wrongly typed and physically impossible values."""
    if value is None:
        return ValidationResult(None, (f"{field}_missing",), False)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ValidationResult(None, (f"{field}_type",), True)
    number = float(value)
    if not math.isfinite(number):
        return ValidationResult(None, (f"{field}_non_finite",), True)
    lower, upper = BOUNDS[field]
    if not lower <= number <= upper:
        return ValidationResult(None, (f"{field}_out_of_range",), True)
    return ValidationResult(number)


def validate_time_axis(values: list[object], *, now: datetime | None = None) -> tuple[datetime, ...]:
    """Return a strict UTC time axis; never repair malformed or reordered input."""
    parsed: list[datetime] = []
    reference = now or datetime.now(timezone.utc)
    for raw in values:
        try:
            item = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_timestamp") from exc
        item = item.replace(tzinfo=timezone.utc) if item.tzinfo is None else item.astimezone(timezone.utc)
        if item > reference + timedelta(days=11):
            raise ValueError("unexpected_future_timestamp")
        if parsed and item <= parsed[-1]:
            raise ValueError("time_axis_not_strictly_increasing")
        parsed.append(item)
    return tuple(parsed)


def validate_aligned_columns(times: list[object], columns: dict[str, list[object]], required: set[str]) -> None:
    missing = sorted(required - columns.keys())
    if missing:
        raise ValueError("missing_columns:" + ",".join(missing))
    wrong = sorted(name for name, values in columns.items() if len(values) != len(times))
    if wrong:
        raise ValueError("array_length_mismatch:" + ",".join(wrong))

