"""Pure scoring primitives used by public recommendation surfaces.

Only ordered spot ids leave this package. Components remain internal so the
public API can enforce the score-visibility contract centrally.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import math
from typing import Any, Iterable, Mapping, Sequence

from app.scoring.geometry import angular_diff, direction_status
from app.scoring.rider.band import PersonalBand


@dataclass(frozen=True, slots=True)
class Components:
    feasibility: float
    condition_fit: float
    character_fit: float
    confidence: float
    reachability: float
    anomaly: float = 0.0
    social: float = 0.5
    social_weight: float = 0.0

    @property
    def utility(self) -> float:
        base = (
            self.feasibility
            * self.condition_fit
            * self.character_fit
            * self.confidence
            * self.reachability
        )
        social_adjustment = self.social_weight * (self.social - 0.5)
        return max(0.0, min(1.0, base + self.anomaly + social_adjustment))

    def payload(self) -> dict[str, float]:
        return {**asdict(self), "utility": self.utility}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def condition_fit(wind_kt: float, band: PersonalBand, big_air_weight: int = 0) -> float:
    """Trapezoid fit over the Personal Band, with a bounded Big-Air tilt."""
    wind = float(wind_kt)
    if wind <= band.min_kt or wind >= band.max_kt:
        return 0.0
    if band.ideal_lo_kt <= wind <= band.ideal_hi_kt:
        fit = 1.0
    elif wind < band.ideal_lo_kt:
        width = max(0.001, band.ideal_lo_kt - band.min_kt)
        fit = (wind - band.min_kt) / width
    else:
        width = max(0.001, band.max_kt - band.ideal_hi_kt)
        fit = (band.max_kt - wind) / width

    # Big-Air may prefer the upper half, but never makes an infeasible hour
    # feasible or moves a boundary from the calibrated Personal Band.
    tilt = max(0, min(3, int(big_air_weight))) / 3.0
    if tilt:
        position = (wind - band.min_kt) / max(0.001, band.max_kt - band.min_kt)
        fit *= 0.85 + 0.3 * position * tilt
    return max(0.0, min(1.0, fit))


def character_fit(profile: Mapping[str, Any], spot: Any) -> float:
    excluded = set(profile.get("excluded_bottoms") or [])
    bottoms = set(getattr(spot, "bottom_type", None) or [])
    if excluded.intersection(bottoms):
        return 0.0

    weights = {
        str(key): max(0.0, float(value))
        for key, value in (profile.get("style_weights") or {}).items()
        if _number(value) is not None
    }
    styles = set(getattr(spot, "style", None) or [])
    if weights and styles:
        keys = set(weights) | styles
        user_norm = math.sqrt(sum(weights.get(key, 0.0) ** 2 for key in keys))
        spot_norm = math.sqrt(sum((3.0 if key in styles else 0.0) ** 2 for key in keys))
        style_fit = (
            sum(weights.get(key, 0.0) * (3.0 if key in styles else 0.0) for key in keys)
            / (user_norm * spot_norm)
            if user_norm and spot_norm
            else 0.0
        )
    else:
        style_fit = 0.6

    preferred_water = set(profile.get("preferred_water_character") or [])
    water = set(getattr(spot, "water_character", None) or [])
    if preferred_water and water:
        water_fit = 1.0 if preferred_water.intersection(water) else 0.7
    else:
        water_fit = 1.0
    return max(0.0, min(1.0, style_fit * water_fit))


def reachability(distance_km: float | None, profile: Mapping[str, Any]) -> float:
    if distance_km is None:
        return 1.0
    configured = _number(profile.get("max_travel_km"))
    if configured is not None and distance_km > configured:
        return 0.0
    scales = {"day_trip": 80.0, "weekend": 250.0, "camper": 600.0, "trip": 1600.0}
    scale = configured or scales.get(str(profile.get("travel_mode") or "day_trip"), 80.0)
    return math.exp(-max(0.0, distance_km) / max(1.0, scale))


def _hour_feasible(
    hour: Mapping[str, Any],
    *,
    band: PersonalBand,
    direction_windows: Sequence[Mapping[str, float]],
    profile: Mapping[str, Any],
    facing: float | None,
    beginner_offshore_ok: bool,
) -> bool:
    if hour.get("is_day") is not True:
        return False
    wind = _number(hour.get("wind"))
    gust = _number(hour.get("gust"))
    direction = _number(hour.get("dir"))
    if wind is None or direction is None:
        return False
    if not (band.min_kt <= wind <= band.max_kt):
        return False
    if gust is not None and gust > wind + band.gust_tolerance_kt:
        return False
    if direction_status(direction, list(direction_windows)) != "ok":
        return False
    if (
        profile.get("level") == "beginner"
        and facing is not None
        and angular_diff(direction, facing) >= 110.0
        and not beginner_offshore_ok
    ):
        return False
    minimum_sst = _number(profile.get("min_water_temp_c"))
    sst = _number(hour.get("sst"))
    if minimum_sst is not None and sst is not None and sst < minimum_sst:
        return False
    return True


def _session_hours(hours: Sequence[Mapping[str, Any]], feasible: Sequence[bool]) -> list[int]:
    """Indexes belonging to runs of at least three consecutive hours."""
    accepted: list[int] = []
    run: list[int] = []
    previous: datetime | None = None
    for index, (hour, ok) in enumerate(zip(hours, feasible)):
        try:
            current = datetime.fromisoformat(str(hour.get("time")).replace("Z", "+00:00"))
        except ValueError:
            current = None
        consecutive = previous is not None and current is not None and 0 < (current - previous).total_seconds() <= 5400
        if ok and (not run or consecutive):
            run.append(index)
        elif ok:
            if len(run) >= 3:
                accepted.extend(run)
            run = [index]
        else:
            if len(run) >= 3:
                accepted.extend(run)
            run = []
        previous = current
    if len(run) >= 3:
        accepted.extend(run)
    return accepted


def forecast_components(
    profile: Mapping[str, Any],
    band: PersonalBand,
    spot: Any,
    days: Iterable[Mapping[str, Any]],
    *,
    direction_windows: Sequence[Mapping[str, float]],
    distance_km: float | None = None,
    anomaly: float = 0.0,
) -> Components:
    """Evaluate forecast days; a spot needs at least one three-hour session."""
    fits: list[float] = []
    confidences: list[float] = []
    big_air = int((profile.get("style_weights") or {}).get("big_air", 0) or 0)
    availability = set(profile.get("availability") or [])
    editorial = getattr(spot, "editorial", None) or {}
    facing = _number(getattr(spot, "facing", None))
    for day in days:
        try:
            weekday = datetime.fromisoformat(str(day.get("local_date") or day.get("date"))).weekday()
        except ValueError:
            weekday = None
        if availability and weekday is not None and weekday not in availability:
            continue
        hours = list(day.get("hours") or [])
        feasible = [
            _hour_feasible(
                hour,
                band=band,
                direction_windows=direction_windows,
                profile=profile,
                facing=facing,
                beginner_offshore_ok=editorial.get("beginner_offshore_ok") is True,
            )
            for hour in hours
        ]
        indexes = _session_hours(hours, feasible)
        if not indexes:
            continue
        fits.extend(condition_fit(float(hours[index]["wind"]), band, big_air) for index in indexes)
        confidence = _number(day.get("confidence"))
        confidences.append(confidence if confidence is not None else 0.7)

    feasible = 1.0 if fits else 0.0
    return Components(
        feasibility=feasible,
        condition_fit=sum(fits) / len(fits) if fits else 0.0,
        character_fit=character_fit(profile, spot),
        confidence=sum(confidences) / len(confidences) if confidences else 0.0,
        reachability=reachability(distance_km, profile),
        anomaly=max(0.0, min(0.15, anomaly)) if feasible else 0.0,
    )
