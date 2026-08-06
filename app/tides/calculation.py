from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable, Literal, Sequence

EventType = Literal["high", "low"]


@dataclass(frozen=True)
class CurvePoint:
    time: datetime
    height: float


@dataclass(frozen=True)
class RawEvent:
    event_type: EventType
    time: datetime
    relative_height: float


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Tide-Zeitpunkte müssen eine Zeitzone enthalten")
    return value.astimezone(timezone.utc)


def detect_extrema(points: Sequence[CurvePoint], *, minimum_separation_minutes: int = 120) -> list[RawEvent]:
    """Find stable local extrema and refine their time parabolically.

    FES worker samples are evenly spaced. Flat/duplicate extrema are collapsed,
    and implausibly close extrema of the same type keep the more pronounced one.
    """
    if len(points) < 3:
        return []
    normal = [CurvePoint(ensure_utc(p.time), float(p.height)) for p in points]
    if any(normal[i].time >= normal[i + 1].time for i in range(len(normal) - 1)):
        raise ValueError("Tidekurve muss streng chronologisch sortiert sein")
    events: list[RawEvent] = []
    for idx in range(1, len(normal) - 1):
        left, center, right = normal[idx - 1], normal[idx], normal[idx + 1]
        is_high = center.height > left.height and center.height >= right.height
        is_low = center.height < left.height and center.height <= right.height
        if not (is_high or is_low):
            continue
        step_before = (center.time - left.time).total_seconds()
        step_after = (right.time - center.time).total_seconds()
        event_time = center.time
        event_height = center.height
        if abs(step_before - step_after) <= 1 and step_before > 0:
            denominator = left.height - 2 * center.height + right.height
            if abs(denominator) > 1e-12:
                fraction = 0.5 * (left.height - right.height) / denominator
                if -1 <= fraction <= 1:
                    event_time = center.time + timedelta(seconds=fraction * step_before)
                    event_height = center.height - 0.25 * (left.height - right.height) * fraction
        candidate = RawEvent("high" if is_high else "low", event_time, event_height)
        if events and candidate.event_type == events[-1].event_type:
            distance = (candidate.time - events[-1].time).total_seconds() / 60
            if distance < minimum_separation_minutes:
                old = events[-1]
                better = candidate.relative_height > old.relative_height if is_high else candidate.relative_height < old.relative_height
                if better:
                    events[-1] = candidate
                continue
        events.append(candidate)
    return events


def corrected_time(
    raw_time: datetime,
    event_type: EventType,
    *,
    global_offset_minutes: int = 0,
    high_offset_minutes: int = 0,
    low_offset_minutes: int = 0,
) -> datetime:
    specific = high_offset_minutes if event_type == "high" else low_offset_minutes
    return ensure_utc(raw_time) + timedelta(minutes=global_offset_minutes + specific)


def calibration_suggestion(differences: Iterable[tuple[EventType, int]]) -> dict:
    """Explainable robust suggestion using medians and median deviation."""
    grouped = {"high": [], "low": []}
    for event_type, value in differences:
        grouped[event_type].append(int(value))
    result: dict[str, object] = {"total": sum(map(len, grouped.values()))}
    for event_type, values in grouped.items():
        if not values:
            result[event_type] = None
            continue
        center = int(round(median(values)))
        deviations = [abs(value - center) for value in values]
        mad = float(median(deviations))
        # 1.4826*MAD approximates standard deviation for a normal distribution;
        # never claim less than the observed five-minute model sampling interval.
        uncertainty = max(5, int(round(1.4826 * mad)))
        result[event_type] = {
            "offset_minutes": center,
            "spread_minutes": mad,
            "uncertainty_minutes": uncertainty,
            "count": len(values),
        }
    return result


def phase_at(events: Sequence[tuple[EventType, datetime]], now: datetime) -> tuple[str, float | None]:
    """Return phase and relative progress between surrounding extrema."""
    current = ensure_utc(now)
    ordered = sorted(((kind, ensure_utc(at)) for kind, at in events), key=lambda item: item[1])
    previous = next(((kind, at) for kind, at in reversed(ordered) if at <= current), None)
    upcoming = next(((kind, at) for kind, at in ordered if at > current), None)
    if previous is None or upcoming is None:
        return "unavailable", None
    duration = (upcoming[1] - previous[1]).total_seconds()
    progress = 0.0 if duration <= 0 else (current - previous[1]).total_seconds() / duration
    if progress <= 0.03:
        return ("high" if previous[0] == "high" else "low"), 0.0
    return ("falling" if upcoming[0] == "low" else "rising"), min(1.0, max(0.0, progress))


def effective_uncertainty(*, manual: int | None, estimated: int | None, quality: str) -> int:
    if manual is not None:
        return max(0, manual)
    if estimated is not None:
        return max(0, estimated)
    return {
        "gauge_calibrated": 10,
        "manual_calibrated": 20,
        "reviewed_anchor": 30,
        "model_only": 45,
    }.get(quality, 90)
