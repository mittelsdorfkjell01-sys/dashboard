"""Non-bypassable visibility helpers for the public catalogue."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Region, Spot

PUBLISHED = "published"


def get_published_spot(db: Session, spot_id) -> Spot | None:
    return db.scalar(
        select(Spot).where(Spot.id == spot_id, Spot.status == PUBLISHED)
    )


def get_published_region(db: Session, region_id) -> Region | None:
    return db.scalar(
        select(Region).where(Region.id == region_id, Region.status == PUBLISHED)
    )
