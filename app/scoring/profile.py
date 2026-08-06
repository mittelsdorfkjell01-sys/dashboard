"""Rider-profile threshold offsets (the per-level layer of the score model)."""

from __future__ import annotations

from app.scoring.params import get_params

def profile_thresholds(level: str | None, sport: str, params: dict | None = None) -> dict:
    """Threshold offsets (applied to the *ideal* band) for a rider level.

    Unknown/None level -> no offsets. The offsets shift only the good-vs-moderate
    band, so a beginner and an expert can grade conditions differently while
    the hard feasibility gates stay identical.
    """
    params = params or get_params(sport)
    if not level:
        return {}
    return dict(params.get("level_offsets", {}).get(level, {}))
