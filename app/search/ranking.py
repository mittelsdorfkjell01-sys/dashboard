"""Distance-damped ranking: Score (Sprint 4 seam) x exp(-d/d0)."""

from __future__ import annotations

import math
from typing import Any

from app.scoring import Scorer


def rank_nearby(
    items: list[tuple[Any, float | None]],
    time_context: dict | None,
    profile: dict | None,
    *,
    scorer: Scorer,
    d0_km: float,
) -> list[dict]:
    """Rank ``(spot, distance_m)`` items by ``score x exp(-d_km/d0_km)``.

    A clearly better but somewhat farther spot can outrank a mediocre near one.
    Items with unknown distance are treated as distance 0 (no damping). Returns
    dicts ``{spot, distance_m, score, rank_score}`` sorted best-first.
    """
    ranked: list[dict] = []
    for spot, distance_m in items:
        weeks = (time_context or {}).get("weeks") if isinstance(time_context, dict) else None
        if weeks:
            values = [
                float(scorer.score(spot, {"week": week}, profile))
                for week in weeks
            ]
            score = sum(values) / len(values) if values else 0.0
        else:
            score = float(scorer.score(spot, time_context, profile))
        d_km = (distance_m or 0.0) / 1000.0
        decay = math.exp(-d_km / d0_km) if d0_km > 0 else 1.0
        ranked.append(
            {
                "spot": spot,
                "distance_m": distance_m,
                "score": round(score, 4),
                "rank_score": round(score * decay, 6),
            }
        )
    ranked.sort(key=lambda r: r["rank_score"], reverse=True)
    return ranked
