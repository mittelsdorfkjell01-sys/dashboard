"""Family-weighted wind consensus calculated in vector space."""

from __future__ import annotations

from dataclasses import dataclass

from app.weather.catalog import family_for
from app.weather.vectors import weighted_vector_mean
from app.weather.weights import normalized_model_weights


@dataclass(frozen=True)
class WindMember:
    model_id: str
    speed_ms: float
    direction_deg: float
    gust_ms: float | None = None


@dataclass(frozen=True)
class WindConsensus:
    speed_ms: float
    direction_deg: float | None
    gust_ms: float | None
    low_ms: float
    high_ms: float
    member_count: int
    weights: dict[str, float]


def calculate_wind_consensus(
    members: list[WindMember], lead_hours: float, *, multipliers: dict[str, float] | None = None
) -> WindConsensus | None:
    valid = [m for m in members if m.speed_ms >= 0]
    if not valid:
        return None
    weights = normalized_model_weights(
        ((member.model_id, family_for(member.model_id)) for member in valid), lead_hours, multipliers
    )
    speed, direction = weighted_vector_mean(
        (member.speed_ms, member.direction_deg, weights[member.model_id]) for member in valid
    )
    gust_members = [member for member in valid if member.gust_ms is not None]
    gust_weight = sum(weights[member.model_id] for member in gust_members)
    gust = (
        sum(member.gust_ms * weights[member.model_id] for member in gust_members) / gust_weight
        if gust_weight > 0
        else None
    )
    if gust is not None:
        gust = max(speed, gust)
    return WindConsensus(
        speed_ms=speed,
        direction_deg=direction,
        gust_ms=gust,
        low_ms=min(member.speed_ms for member in valid),
        high_ms=max(member.speed_ms for member in valid),
        member_count=len(valid),
        weights=weights,
    )
