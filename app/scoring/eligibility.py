"""Eligibility for curated recommendation lists.

This is deliberately separate from the numeric scorer: public search and maps
may retain incomplete spots, while recommendation surfaces require reviewed
direction evidence and a known spot orientation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload


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
        .options(selectinload(SpotWeatherProfile.sectors))
    )
    has_reviewed_sectors = bool(
        profile
        and profile.reviewed_at is not None
        and any(sector.enabled for sector in profile.sectors)
    )
    if not has_reviewed_sectors:
        gaps.append("reviewed_sectors")
    if getattr(spot, "facing", None) is None:
        gaps.append("facing")
    return gaps


def is_recommendable(spot: Any, sport: str, db: Any) -> bool:
    """Whether ``spot`` has the reviewed evidence required for ``sport``."""
    return not recommendability_gaps(spot, sport, db)
