"""Public score-private recommendation lists."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.account.deps import optional_account
from app.api._http_cache import set_recommendation_cache
from app.api.spots import _safe_summaries
from app.db.session import get_db
from app.live.cache import Cache
from app.live.client import OpenMeteoClient
from app.live.deps import get_cache, get_om_client
from app.models import AppUser
from app.recommendations.service import RecommendationSurface, bucket_location, recommendations
from app.schemas import SpotSummary
from app.scoring.rider.resolve import resolve_rider

router = APIRouter(tags=["recommendations"])


def _weeks(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    try:
        start, end = (int(part) for part in value.split("-", 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="weeks must be 'start-end'")
    if not (1 <= start <= 52 and 1 <= end <= 52):
        raise HTTPException(status_code=422, detail="weeks must be between 1 and 52")
    return start, end


@router.get("/recommendations", response_model=list[SpotSummary])
def get_recommendations(
    response: Response,
    sport: str = Query(default="kitesurf"),
    surface: RecommendationSurface = Query(default=RecommendationSurface.NOW),
    region_id: uuid.UUID | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    weeks: str | None = Query(default=None),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    limit: int = Query(default=12, ge=1, le=24),
    db: Session = Depends(get_db),
    account: AppUser | None = Depends(optional_account),
    client: OpenMeteoClient = Depends(get_om_client),
    cache: Cache = Depends(get_cache),
) -> list[SpotSummary]:
    """Return existing spot cards in personalized order, without score fields."""
    started = time.perf_counter()
    if sport != "kitesurf":
        raise HTTPException(status_code=422, detail="recommendations are currently available for kitesurf")
    if surface == RecommendationSurface.REGION and region_id is None:
        raise HTTPException(status_code=422, detail="region_id is required for the region surface")
    if surface != RecommendationSurface.REGION and region_id is not None:
        raise HTTPException(status_code=422, detail="region_id is only valid for the region surface")
    if surface != RecommendationSurface.SEASON and (month is not None or weeks is not None):
        raise HTTPException(status_code=422, detail="month and weeks are only valid for the season surface")
    if month is not None and weeks is not None:
        raise HTTPException(status_code=422, detail="choose month or weeks")
    if (lat is None) != (lon is None):
        raise HTTPException(status_code=422, detail="lat and lon must be supplied together")

    rider = resolve_rider(db, account, sport)
    rows = recommendations(
        db,
        rider,
        surface=surface,
        sport=sport,
        client=client,
        cache=cache,
        app_user_id=account.id if account else None,
        region_id=region_id,
        month=month,
        weeks=_weeks(weeks),
        location=bucket_location(lat, lon),
        limit=limit,
    )
    set_recommendation_cache(response, private=account is not None)
    response.headers["Server-Timing"] = (
        f'recommendations;dur={(time.perf_counter() - started) * 1000:.1f}'
    )
    return _safe_summaries(rows, db)
