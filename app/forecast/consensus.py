"""Dynamic family-aware vector consensus for corrected direct model values."""

from __future__ import annotations
from dataclasses import dataclass
from app.forecast.physics import CorrectedValue
from app.forecast.registry import MODELS
from app.weather.vectors import uv_to_wind


@dataclass(frozen=True)
class ConsensusValue:
    speed_ms: float
    direction_deg: float | None
    gust_ms: float | None
    low_ms: float
    high_ms: float
    confidence: str
    model_count: int
    effective_weight: float
    youngest_age_minutes: float
    weights: dict[str, float]


def _base(model: str, lead: int, age_minutes: float, complete: bool) -> float:
    spec = next((m for m in MODELS if m.key == model), None)
    if not spec or lead > spec.horizon_hours or not complete:
        return 0
    resolution = max(0.55, min(1.25, 20 / spec.resolution_km))
    horizon = max(0.35, 1 - lead / max(1, spec.horizon_hours) * 0.45)
    freshness = max(0.2, 1 - age_minutes / 720)
    return resolution * horizon * freshness


def combine(values: list[CorrectedValue], *, now) -> ConsensusValue:
    if not values:
        raise ValueError("at least one corrected model value is required")
    weighted = []
    family_totals = {}
    raw_weights = {}
    for value in values:
        age = max(0, (now - value.raw.model_run).total_seconds() / 60)
        weight = _base(
            value.raw.model, value.raw.horizon_hours, age, value.raw.complete
        )
        family = next(
            (m.family for m in MODELS if m.key == value.raw.model), value.raw.model
        )
        family_totals[family] = family_totals.get(family, 0) + weight
        raw_weights[value.raw.model] = (weight, family)
    for value in values:
        weight, family = raw_weights[value.raw.model]
        total = family_totals[family]
        weight = weight / max(1, total)  # correlated family cap
        if weight > 0:
            weighted.append((value, weight))
    if not weighted:
        raise ValueError("no valid model contribution")
    total = sum(w for _, w in weighted)
    u = sum(item.u_ms * w for item, w in weighted) / total
    vv = sum(item.v_ms * w for item, w in weighted) / total
    speed, direction = uv_to_wind(u, vv)
    speeds = sorted(v.speed_ms for v, _ in weighted)
    gusts = [
        max(v.speed_ms, v.raw.gust_ms) for v, _ in weighted if v.raw.gust_ms is not None
    ]
    spread = speeds[-1] - speeds[0]
    confidence = (
        "hoch"
        if len(weighted) >= 3 and spread <= 2
        else "mittel"
        if len(weighted) >= 2 and spread <= 4
        else "niedrig"
    )
    ages = [max(0, (now - v.raw.model_run).total_seconds() / 60) for v, _ in weighted]
    return ConsensusValue(
        speed,
        direction,
        max(speed, sum(g * w for (v, w), g in zip(weighted, gusts)) / total)
        if len(gusts) == len(weighted)
        else None,
        min(speed, speeds[0]),
        max(speed, speeds[-1]),
        confidence,
        len(weighted),
        round(total, 4),
        min(ages),
        {v.raw.model: round(w / total, 4) for v, w in weighted},
    )
