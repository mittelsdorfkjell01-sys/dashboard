"""Eligibility for curated recommendation lists.

This is deliberately separate from the numeric scorer: public search and maps
may retain incomplete spots, while recommendation surfaces require reviewed
direction evidence and a known spot orientation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

def recommendability_gaps(spot: Any, sport: str, db: Any) -> list[str]:
    """Return stable internal gap keys for recommendation eligibility."""
    gaps: list[str] = []
    if sport not in (getattr(spot, "sports", None) or []):
        gaps.append("sport_not_offered")
    from app.models import SpotWeatherProfile

    profile = db.scalar(
        select(SpotWeatherProfile)
        .where(
            SpotWeatherProfile.spot_id == spot.id,
            SpotWeatherProfile.active.is_(True),
        )
    )
    from app.weather.usable_directions import usable_direction_windows

    if not usable_direction_windows(profile):
        gaps.append("usable_directions")
    if getattr(spot, "facing", None) is None:
        gaps.append("facing")
    return gaps


def is_recommendable(spot: Any, sport: str, db: Any) -> bool:
    """Whether ``spot`` has the direction evidence required for ``sport``."""
    return not recommendability_gaps(spot, sport, db)
