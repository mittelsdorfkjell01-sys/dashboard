"""Non-bypassable visibility helpers for the public catalogue."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Region, Spot

PUBLISHED = "published"


def get_published_spot(db: Session, spot_id) -> Spot | None:
    return db.scalar(
        select(Spot).where(Spot.id == spot_id, Spot.status == PUBLISHED)
    )


def published_spot_exists(db: Session, spot_id) -> bool:
    """Check public visibility without transferring a complete spot row."""
    return db.scalar(
        select(Spot.id)
        .where(Spot.id == spot_id, Spot.status == PUBLISHED)
        .limit(1)
    ) is not None


def get_published_region(db: Session, region_id) -> Region | None:
    return db.scalar(
        select(Region).where(Region.id == region_id, Region.status == PUBLISHED)
    )


def get_region_spot_stats(
    db: Session, region_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, dict[str, object]]:
    """Published spot count + unique sports per region.

    One query for every region that's asked for (or, with `region_ids=None`,
    for the whole catalogue) — never one query per region/tile.
    """
    stmt = select(Spot.region_id, Spot.sports).where(
        Spot.status == PUBLISHED, Spot.region_id.isnot(None)
    )
    if region_ids is not None:
        stmt = stmt.where(Spot.region_id.in_(region_ids))
    stats: dict[uuid.UUID, dict[str, object]] = {}
    for region_id, sports in db.execute(stmt):
        entry = stats.setdefault(region_id, {"spot_count": 0, "sports": set()})
        entry["spot_count"] += 1
        entry["sports"].update(sports or [])
    return stats
