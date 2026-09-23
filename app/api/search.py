"""Search, geometry-search, map, portfolio (Sprint 5) + open-axes (Sprint 6)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.account.deps import optional_account
from app.api._http_cache import set_recommendation_cache
from app.models import AppUser
from app.scoring import Scorer
from app.search import service
from app.search.deps import get_geocoder, get_scorer
from app.search.geocode import Geocoder
from app.search.timewindow import resolve_time_window
from app.schemas.search import GeometryRequest

router = APIRouter(tags=["search"])


def _time_context(week: int | None) -> dict | None:
    return {"week": week} if week else None


def _profile(level: str | None) -> dict | None:
    if not level:
        return None
    from app.admin.constants import LEVELS

    canonical = {"intermediate": "advanced", "pro": "expert"}.get(level, level)
    if canonical not in LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown level {level!r}; allowed: {list(LEVELS)}",
        )
    return {"level": canonical}


def _season_window(month: int | None, weeks: str | None) -> dict:
    """Build a season time window from ``month`` or a ``"start-end"`` week range.

    Neither given → the open axis (all 52 weeks).
    """
    if weeks:
        try:
            a, b = (int(x) for x in weeks.split("-"))
        except ValueError:
            raise HTTPException(status_code=422, detail="weeks must be 'start-end'")
        return resolve_time_window("season", {"weeks": [a, b]})
    if month:
        return resolve_time_window("season", {"month": month})
    return resolve_time_window("season", None)  # open


@router.get("/search")
def search(
    response: Response,
    q: str = Query(..., min_length=1, description="Free-text query (place or spot/region)"),
    sport: str | None = Query(default=None),
    variant: str | None = Query(
        default=None,
        description="Sport variant key (e.g. windsurf:foil, kitesurf:foil); "
        "filters to spots that actually offer this variant",
    ),
    week: int | None = Query(default=None, ge=1, le=52),
    level: str | None = Query(default=None, description="Skill profile level"),
    db: Session = Depends(get_db),
    geocoder: Geocoder = Depends(get_geocoder),
    scorer: Scorer = Depends(get_scorer),
    account: AppUser | None = Depends(optional_account),
) -> dict:
    """Resolve a query to ranked spots/regions (entities first, else geocode)."""
    profile = _profile(level)
    rider_scorer = None
    if sport == "kitesurf":
        from app.recommendations.service import RiderUtilityScorer
        from app.scoring.rider.resolve import resolve_rider

        rider = resolve_rider(db, account, sport)
        rider_scorer = RiderUtilityScorer(scorer, rider)
        scorer = rider_scorer
        profile = {**rider.profile, **(profile or {})}
        set_recommendation_cache(response, private=account is not None)
    result = service.search(
        q,
        sport=sport,
        variant=variant,
        time_context=_time_context(week),
        profile=profile,
        db=db,
        geocoder=geocoder,
        scorer=scorer,
    )
    if rider_scorer is not None:
        rider_scorer.write_log(
            db, app_user_id=account.id if account is not None else None
        )
    return result


@router.post("/search/geometry")
def search_geometry(
    body: GeometryRequest,
    level: str | None = Query(default=None),
    db: Session = Depends(get_db),
    scorer: Scorer = Depends(get_scorer),
) -> dict:
    """Rank spots inside a drawn circle (ST_DWithin) or rectangle (ST_Within)."""
    try:
        shape = body.to_shape()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return service.search_geometry(
        shape,
        sport=body.sport,
        variant=body.variant,
        time_context=_time_context(body.week),
        profile=_profile(level),
        db=db,
        scorer=scorer,
    )


@router.get("/map")
def map_view(
    min_lon: float = Query(...),
    min_lat: float = Query(...),
    max_lon: float = Query(...),
    max_lat: float = Query(...),
    sport: str | None = Query(default=None),
    variant: str | None = Query(default=None),
    week: int | None = Query(default=None, ge=1, le=52),
    level: str | None = Query(default=None),
    db: Session = Depends(get_db),
    scorer: Scorer = Depends(get_scorer),
) -> dict:
    """Pins for a viewport bbox, privately ranked without score fields."""
    bounds = {
        "min_lon": min_lon,
        "min_lat": min_lat,
        "max_lon": max_lon,
        "max_lat": max_lat,
    }
    return service.query_map(
        bounds,
        time_context=_time_context(week),
        sport=sport,
        variant=variant,
        profile=_profile(level),
        db=db,
        scorer=scorer,
    )


@router.get("/portfolio")
def portfolio(
    level: str = Query(default="region", description="region | global"),
    sport: str | None = Query(default=None),
    week: int | None = Query(default=None, ge=1, le=52),
    db: Session = Depends(get_db),
    scorer: Scorer = Depends(get_scorer),
) -> dict:
    """Portfolio of pin-maps, kept in sync with /map's pin logic."""
    return service.query_portfolio(
        level,
        time_context=_time_context(week),
        sport=sport,
        profile=None,
        db=db,
        scorer=scorer,
    )


# --- Sprint 6: open axes / reverse search ----------------------------------

@router.get("/search/best-spots", tags=["open-axes"])
def best_spots(
    sport: str | None = Query(default=None),
    region_id: uuid.UUID | None = Query(default=None, description="Region scope; omit for the whole catalogue"),
    month: int | None = Query(default=None, ge=1, le=12),
    weeks: str | None = Query(default=None, description="Week range 'start-end'"),
    level: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    """Best spots over a time window. Open *place* (no `region_id`) ranks the
    whole catalogue (v1 = Europe); open *time* (no month/weeks) uses all 52 weeks."""
    window = _season_window(month, weeks)
    profile = _profile(level)
    if region_id is not None:
        return service.best_spots_in_region(
            region_id, db=db, sport=sport, profile=profile, window=window, limit=limit
        )
    return service.best_spots_open_place(
        db=db, sport=sport, profile=profile, window=window, limit=limit
    )


@router.get("/search/best-regions", tags=["open-axes"])
def best_regions(
    sport: str | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    weeks: str | None = Query(default=None, description="Week range 'start-end'"),
    level: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    """Rank regions over a time window (travel default when time is open too)."""
    window = _season_window(month, weeks)
    try:
        return service.best_regions_for_window(
            window, db=db, sport=sport, profile=_profile(level), limit=limit
        )
    except KeyError:
        raise HTTPException(status_code=422, detail=f"Unknown sport {sport!r}")


@router.get("/areas/best-weeks", tags=["open-axes"])
def areas_best_weeks(
    sport: str | None = Query(default=None),
    region_id: uuid.UUID | None = Query(default=None),
    spot_id: uuid.UUID | None = Query(default=None),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    radius_km: float = Query(default=25.0, gt=0),
    level: str | None = Query(default=None),
    top: int = Query(default=12, ge=1, le=52),
    db: Session = Depends(get_db),
) -> dict:
    """Open *time*: the best weeks for an area (region / spot / point, else catalogue)."""
    if region_id is not None:
        area: dict = {"region_id": region_id}
    elif spot_id is not None:
        area = {"spot_id": spot_id}
    elif lat is not None and lon is not None:
        area = {"point": {"lat": lat, "lon": lon}, "radius_km": radius_km}
    else:
        area = {}  # whole catalogue
    return service.best_weeks_for_area(
        area, db=db, sport=sport, profile=_profile(level), top=top
    )
