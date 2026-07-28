import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._http_cache import set_public_cache
from app.db.session import get_db
from app.models import Region
from app.schemas import RegionRead
from app.scoring.region import aggregate_region_season, region_when_to_go

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", response_model=list[RegionRead])
def list_regions(
    response: Response,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> list[RegionRead]:
    """Public listing shows only published regions. The admin passes
    ``status=all`` to see drafts too (or a specific status)."""
    stmt = select(Region).order_by(Region.name)
    if status is None:
        stmt = stmt.where(Region.status == "published")
    elif status != "all":
        stmt = stmt.where(Region.status == status)
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    set_public_cache(response)
    return [RegionRead.from_orm_region(r) for r in rows]


@router.get("/by-slug/{slug}", response_model=RegionRead)
def get_region_by_slug(
    slug: str, response: Response, db: Session = Depends(get_db)
) -> RegionRead:
    """Resolve a region by slug regardless of status — powers the region page +
    draft preview (like the spot detail, which is not status-filtered)."""
    region = db.scalar(select(Region).where(Region.slug == slug))
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    set_public_cache(response)
    return RegionRead.from_orm_region(region)


@router.get("/{region_id}", response_model=RegionRead)
def get_region(
    region_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> RegionRead:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    set_public_cache(response)
    return RegionRead.from_orm_region(region)


@router.get("/{region_id}/season", tags=["open-axes"])
def get_region_season(
    region_id: uuid.UUID,
    sport: str | None = Query(default=None),
    smooth: bool = Query(default=False, description="Also return the smoothed when-to-go curve"),
    db: Session = Depends(get_db),
) -> dict:
    """Region season aggregate (52 weeks of ``spots_working`` + median wind/sst/air).

    Computed and cached on `regions.season`; recomputed when a `sport` is given."""
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")

    season = region.season or {}
    if sport or "weeks" not in season:
        season = aggregate_region_season(region_id, db=db, sport=sport)

    result: dict = {"region_id": str(region.id), "season": season}
    if smooth:
        result["when_to_go"] = region_when_to_go(region_id, db=db, sport=sport)
    return result
