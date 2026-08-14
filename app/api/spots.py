import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, defer, selectinload

from app.api._http_cache import set_public_cache
from app.db.session import get_db
from app.discovery import service as discovery
from app.live import service as live_service
from app.live.cache import Cache
from app.live.client import MAX_FORECAST_DAYS, OpenMeteoClient
from app.live.deps import get_cache, get_om_client
from app.models import Spot
from app.names import normalize_name
from app.public_catalog import PUBLISHED, get_published_spot
from app.schemas import SpotRead, SpotSummary
from app.schemas.live import ForecastSeriesRead, LiveConditionsRead
from app.scoring import (
    describe_week_entry,
    score_climatology_curve,
    score_live,
)
from app.similarity import service as similarity_service
from app.tides import service as tide_service
from app.tides.schemas import PublicTideRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spots", tags=["spots"])


@router.get("/{spot_id}/tides", response_model=PublicTideRead, tags=["tides"])
def get_spot_tides(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> PublicTideRead:
    if get_published_spot(db, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    return PublicTideRead.model_validate(tide_service.public_tides(spot_id, db=db))


def _safe_summaries(rows: list[Spot]) -> list[SpotSummary]:
    """Serialize a list of spots, skipping (and logging) any row whose data
    can't be summarized. One malformed spot must never 500 the whole list — a
    single bad record would otherwise take down the public landing/map views.
    The log names the spot so the underlying data can be repaired."""
    out: list[SpotSummary] = []
    for s in rows:
        try:
            out.append(SpotSummary.from_orm_spot(s))
        except Exception:
            logger.exception(
                "skipping spot %s (%s): summary serialization failed",
                getattr(s, "id", None),
                getattr(s, "slug", None),
            )
    return out


@router.get("", response_model=list[SpotSummary])
def list_spots(
    response: Response,
    db: Session = Depends(get_db),
    region_id: uuid.UUID | None = Query(default=None),
    sport: str | None = Query(
        default=None, description="Filter to spots offering this sport"
    ),
    level: str | None = Query(
        default=None, description="Filter to spots at this rider level"
    ),
    water_character: str | None = Query(
        default=None, description="Filter by water character (Wasserart)"
    ),
    style: list[str] | None = Query(
        default=None, description="Filter to spots offering any of these riding styles"
    ),
    bottom_type: list[str] | None = Query(
        default=None, description="Filter to spots matching any selected bottom type"
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SpotSummary]:
    """List spots (lightweight view — no climatology/overrides blobs; editorial
    is loaded only to derive the tile's typical wind/wave-height figure, never
    returned raw).

    Fetch a single spot's full record (incl. climatology) via ``GET /spots/{id}``.
    """
    # Don't load the heavy JSONB columns for a list view — editorial stays
    # (SpotSummary derives typical_wind_kt/typical_wave_height_m from it).
    stmt = (
        select(Spot)
        .where(Spot.status == PUBLISHED)
        .options(
            defer(Spot.climatology),
            defer(Spot.overrides),
            defer(Spot.era5_cell),
            selectinload(Spot.region),
        )
        .order_by(Spot.name)
    )
    if region_id is not None:
        stmt = stmt.where(Spot.region_id == region_id)
    if sport is not None:
        stmt = stmt.where(Spot.sports.any(sport))
    if level is not None:
        stmt = stmt.where(Spot.level.any(level))
    if water_character is not None:
        stmt = stmt.where(Spot.water_character.any(water_character))
    if style:
        # Match spots offering ANY of the requested styles (array overlap).
        stmt = stmt.where(Spot.style.overlap(style))
    if bottom_type:
        stmt = stmt.where(Spot.bottom_type.overlap(bottom_type))
    stmt = stmt.limit(limit).offset(offset)

    rows = db.scalars(stmt).all()
    set_public_cache(response)
    return _safe_summaries(rows)


@router.get("/top", response_model=list[SpotSummary])
def list_top_spots(
    response: Response,
    db: Session = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=20),
    sport: str | None = Query(
        default=None, description="Rank only spots offering this sport"
    ),
    client: OpenMeteoClient = Depends(get_om_client),
    cache: Cache = Depends(get_cache),
) -> list[SpotSummary]:
    """ "aktuelle Top Spots": published spots ranked by a blend of this week's
    wind forecast, today's conditions and community popularity.

    Stable within a day and re-ranked when the date rolls over (a date seed also
    rotates ties), so the set changes daily. Declared before ``/{spot_id}`` so
    ``/spots/top`` is matched as a literal path, not a spot id.

    Non-critical widget: if the ranking can't be computed (e.g. the forecast
    provider is unreachable), it degrades to a plain published list instead of
    500-ing, so the landing row always renders.
    """
    # Over-fetch a few extra candidates so a single spot dropped by
    # _safe_summaries (malformed data) doesn't shrink the row below `limit`.
    fetch_n = min(limit + 3, 20)
    try:
        ids = discovery.top_spot_ids(
            db, limit=fetch_n, sport=sport, client=client, cache=cache
        )
    except Exception:
        logger.exception("featured top-spots ranking failed — serving published list")
        db.rollback()
        ids = []

    if ids:
        by_id = {
            s.id: s
            for s in db.scalars(
                select(Spot)
                .where(Spot.id.in_(ids), Spot.status == PUBLISHED)
                .options(selectinload(Spot.region))
            )
        }
        ordered = [by_id[i] for i in ids if i in by_id]
    else:
        # Graceful fallback: the pre-ranking behaviour (published spots by name).
        stmt = (
            select(Spot)
            .where(Spot.status == "published")
            .options(selectinload(Spot.region))
        )
        if sport is not None:
            stmt = stmt.where(Spot.sports.any(sport))
        ordered = list(db.scalars(stmt.order_by(Spot.name).limit(fetch_n)))

    set_public_cache(response)
    # Serialize (dropping any malformed rows), then trim to the requested count.
    return _safe_summaries(ordered)[:limit]


@router.get("/live", response_model=list[LiveConditionsRead], tags=["live"])
def get_spots_live_batch(
    ids: str = Query(..., description="Comma-separated spot UUIDs (max 20)"),
    db: Session = Depends(get_db),
    client: OpenMeteoClient = Depends(get_om_client),
    cache: Cache = Depends(get_cache),
) -> list[LiveConditionsRead]:
    """Current conditions for several spots in one call — replaces the per-tile
    fan-out on the landing/map views (one round-trip instead of N).

    Declared before ``/{spot_id}`` so the literal ``/spots/live`` wins over the
    UUID path. Unknown or malformed ids are skipped rather than failing the whole
    batch; duplicates are de-duplicated; the count is capped to keep per-request
    work bounded. Each item carries its ``spot_id`` so the client can map results.
    """
    tokens = [t.strip() for t in ids.split(",") if t.strip()]
    if not tokens:
        return []
    if len(tokens) > 20:
        raise HTTPException(status_code=400, detail="Too many ids (max 20)")

    parsed: list[uuid.UUID] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        try:
            spot_id = uuid.UUID(token)
        except ValueError:
            continue
        parsed.append(spot_id)

    rows = list(
        db.scalars(select(Spot).where(Spot.id.in_(parsed), Spot.status == PUBLISHED))
    )
    by_id = {spot.id: spot for spot in rows}
    ordered = [by_id[spot_id] for spot_id in parsed if spot_id in by_id]
    results: dict[uuid.UUID, LiveConditionsRead] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(ordered) or 1)) as pool:
        futures = {
            pool.submit(
                live_service.get_live_conditions_for_spot,
                spot,
                client=client,
                cache=cache,
            ): spot.id
            for spot in ordered
        }
        for future in as_completed(futures):
            try:
                data = dict(future.result())
                data["model"] = "surfwinddata"
                data["models"] = []
                results[futures[future]] = LiveConditionsRead.model_validate(data)
            except Exception:
                logger.exception("live batch failed for spot %s", futures[future])
    return [results[spot.id] for spot in ordered if spot.id in results]


def _published_spot_by_reference(db: Session, reference: str) -> Spot | None:
    """Resolve UUID, legacy slug, or a display-name URL without exposing IDs."""
    try:
        spot_id = uuid.UUID(reference)
    except ValueError:
        spot_id = None
    if spot_id is not None:
        return db.scalar(
            select(Spot)
            .where(Spot.id == spot_id, Spot.status == PUBLISHED)
            .options(selectinload(Spot.region))
        )

    try:
        normalized = normalize_name(reference.replace("-", " "))
    except ValueError:
        return None
    rows = list(
        db.scalars(
            select(Spot)
            .where(
                Spot.status == PUBLISHED,
                or_(
                    Spot.slug == reference.casefold(),
                    Spot.normalized_name == normalized,
                ),
            )
            .options(selectinload(Spot.region))
            .order_by(Spot.name)
            .limit(2)
        )
    )
    slug_match = next(
        (spot for spot in rows if spot.slug == reference.casefold()), None
    )
    if slug_match is not None:
        return slug_match
    if len(rows) > 1:
        raise HTTPException(status_code=409, detail="Spot name is ambiguous")
    return rows[0] if rows else None


@router.get("/{spot_reference}", response_model=SpotRead)
def get_spot(
    spot_reference: str, response: Response, db: Session = Depends(get_db)
) -> SpotRead:
    spot = _published_spot_by_reference(db, spot_reference)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    set_public_cache(response)
    return SpotRead.from_orm_spot(spot)


@router.get("/{spot_id}/live", response_model=LiveConditionsRead, tags=["live"])
def get_spot_live(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    client: OpenMeteoClient = Depends(get_om_client),
    cache: Cache = Depends(get_cache),
) -> LiveConditionsRead:
    """Current conditions for a spot (Open-Meteo, cached). Not persisted."""
    if get_published_spot(db, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    try:
        data = live_service.get_live_conditions(
            spot_id, db=db, client=client, cache=cache
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    data = dict(data)
    data["model"] = "surfwinddata"
    data["models"] = []
    return LiveConditionsRead.model_validate(data)


@router.get("/{spot_id}/forecast", response_model=ForecastSeriesRead, tags=["live"])
def get_spot_forecast(
    spot_id: uuid.UUID,
    db: Session = Depends(get_db),
    days: int = Query(default=MAX_FORECAST_DAYS, ge=1, le=MAX_FORECAST_DAYS),
    client: OpenMeteoClient = Depends(get_om_client),
    cache: Cache = Depends(get_cache),
) -> ForecastSeriesRead:
    """Surfwinddata 10-day forecast: days 1–5 hourly, days 6–10 trend."""
    if get_published_spot(db, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    from app.forecast.publisher import active_snapshot, public_payload

    snapshot = active_snapshot(db, spot_id)
    if snapshot is not None:
        return ForecastSeriesRead.model_validate(public_payload(snapshot))
    try:
        data = live_service.get_forecast_series(
            spot_id, days, db=db, client=client, cache=cache
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    # Transitional cold path: a spot always retains the working global
    # baseline even before its first persisted publisher job completes.
    data["model"] = "surfwinddata"
    data["models"] = []
    data["product"] = "Surfwinddata Forecast"
    data["attributions"] = [
        {
            "provider": "Open-Meteo",
            "text": "Weather data by Open-Meteo.com",
            "url": "https://open-meteo.com/",
            "licence": "CC BY 4.0",
        }
    ]
    return ForecastSeriesRead.model_validate(data)


@router.get("/{spot_id}/badge", tags=["score"])
def get_spot_badge(
    spot_id: uuid.UUID,
    sport: str | None = Query(
        default=None, description="Defaults to the spot's first sport"
    ),
    level: str | None = Query(
        default=None, description="Rider level (beginner, advanced, expert)"
    ),
    db: Session = Depends(get_db),
    client: OpenMeteoClient = Depends(get_om_client),
    cache: Cache = Depends(get_cache),
) -> dict:
    """Now-badge: rate current conditions (gut / mäßig / nein) for the spot."""
    if get_published_spot(db, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    profile = {"level": level} if level else None
    try:
        return score_live(spot_id, profile, sport, db=db, client=client, cache=cache)
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{spot_id}/season", tags=["score"])
def get_spot_season(
    spot_id: uuid.UUID,
    stage: int = Query(default=2, ge=1, le=2),
    sport: str | None = Query(default=None),
    level: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Seasonal curve. ``stage=1`` is descriptive (no gates); ``stage=2`` scores
    the usable-hours curve over 52 weeks."""
    spot = get_published_spot(db, spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    if not (spot.climatology and spot.climatology.get("weeks")):
        raise HTTPException(status_code=404, detail="Spot has no climatology")

    if stage == 1:
        weeks = sorted(spot.climatology["weeks"], key=lambda w: w.get("week", 0))
        return {
            "stage": 1,
            "spot_id": spot.id,
            "window": spot.climatology.get("window"),
            "weeks": [describe_week_entry(w) for w in weeks],
        }

    resolved_sport = sport or (spot.sports[0] if spot.sports else None)
    if resolved_sport is None:
        raise HTTPException(status_code=422, detail="No sport to score")
    profile = {"level": level} if level else None
    try:
        result = score_climatology_curve(spot_id, profile, resolved_sport, db=db)
    except KeyError:
        raise HTTPException(status_code=422, detail=f"Unknown sport {resolved_sport!r}")
    return {"stage": 2, "spot_id": spot.id, **result}


@router.get("/{spot_id}/similar", tags=["similarity"])
def get_spot_similar(
    spot_id: uuid.UUID,
    mode: str = Query(default="charakter", description="charakter | saison | beides"),
    sport: str | None = Query(default=None),
    level: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Spots similar in character (feel), season (when they run), or both."""
    if get_published_spot(db, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    profile = {"level": level} if level else None
    try:
        return similarity_service.find_similar_spots(
            spot_id, mode, sport, profile, db=db, limit=limit
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{spot_id}/alternatives", tags=["similarity"])
def get_spot_alternatives(
    spot_id: uuid.UUID,
    sport: str | None = Query(default=None),
    week: int | None = Query(default=None, ge=1, le=52),
    level: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Character-similar spots that are running in the chosen week, ranked."""
    if get_published_spot(db, spot_id) is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    profile = {"level": level} if level else None
    time_context = {"week": week} if week else None
    try:
        return similarity_service.find_alternatives(
            spot_id, time_context, sport, profile, db=db, limit=limit
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Spot not found")
