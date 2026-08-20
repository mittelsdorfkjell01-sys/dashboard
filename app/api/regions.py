import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._http_cache import set_public_cache
from app.db.session import get_db
from app.models import Region
from app.public_catalog import PUBLISHED, get_published_region, get_region_spot_stats
from app.schemas import RegionRead

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", response_model=list[RegionRead])
def list_regions(
    response: Response,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[RegionRead]:
    """List published regions. Editorial states are never public."""
    stmt = select(Region).where(Region.status == PUBLISHED).order_by(Region.name)
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    # One collective query for every region on the page — never one per tile.
    stats = get_region_spot_stats(db, [r.id for r in rows])
    set_public_cache(response)
    return [
        RegionRead.from_orm_region(
            r,
            spot_count=stats.get(r.id, {}).get("spot_count", 0),
            sports=stats.get(r.id, {}).get("sports"),
        )
        for r in rows
    ]


@router.get("/by-slug/{slug}", response_model=RegionRead)
def get_region_by_slug(
    slug: str, response: Response, db: Session = Depends(get_db)
) -> RegionRead:
    region = db.scalar(
        select(Region).where(Region.slug == slug, Region.status == PUBLISHED)
    )
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    stats = get_region_spot_stats(db, [region.id]).get(region.id, {})
    set_public_cache(response)
    return RegionRead.from_orm_region(
        region, spot_count=stats.get("spot_count", 0), sports=stats.get("sports")
    )


@router.get("/{region_id}", response_model=RegionRead)
def get_region(
    region_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> RegionRead:
    region = get_published_region(db, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    stats = get_region_spot_stats(db, [region.id]).get(region.id, {})
    set_public_cache(response)
    return RegionRead.from_orm_region(
        region, spot_count=stats.get("spot_count", 0), sports=stats.get("sports")
    )


@router.get("/{region_id}/season", tags=["open-axes"])
def get_region_season(
    region_id: uuid.UUID,
    sport: str | None = Query(default=None),
    smooth: bool = Query(default=False, description="Also return the smoothed when-to-go curve"),
    db: Session = Depends(get_db),
) -> dict:
    """No V2 region aggregation has been defined yet."""
    region = get_published_region(db, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")

    return {"region_id": str(region.id), "status": "unknown", "season": None}
