"""Search orchestration: text -> geocode -> spatial -> rank, plus map/portfolio."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.scoring import Scorer, default_scorer, distance_decay_d0
from app.search.geocode import Geocoder, classify_geocode
from app.search.pins import build_pins, coords, spot_brief
from app.search.ranking import rank_nearby
from app.search.spatial import (
    bounds_query,
    search_by_geometry,
    search_nearby_spots,
)
from app.search.text import search_entities


# --- serialisation helpers -------------------------------------------------

def _ranked_brief(r: dict) -> dict:
    return {
        **spot_brief(r["spot"]),
        "distance_m": round(r["distance_m"], 1) if r["distance_m"] is not None else None,
        "score": r["score"],
        "rank_score": r["rank_score"],
    }


def _region_brief(region: Any) -> dict:
    center = None
    if getattr(region, "center", None) is not None:
        from geoalchemy2.shape import to_shape

        p = to_shape(region.center)
        center = {"lat": p.y, "lon": p.x}
    return {
        "id": str(region.id),
        "slug": region.slug,
        "name": region.name,
        "center": center,
    }


def _anchor_point(spots: list[Any], regions: list[Any]) -> dict | None:
    if spots:
        lat, lon = coords(spots[0])
        return {"lat": lat, "lon": lon}
    for r in regions:
        if getattr(r, "center", None) is not None:
            from geoalchemy2.shape import to_shape

            p = to_shape(r.center)
            return {"lat": p.y, "lon": p.x}
    return None


def _with_sport(profile: dict | None, sport: str | None) -> dict | None:
    """Make the active sport visible to the (sport-aware) scorer.

    The scorer reads ``profile['sport']`` to decide *which* sport to score; the
    spatial layer only uses ``sport`` to filter. Without this, a spot would be
    scored/coloured for its first listed sport rather than the selected one.
    """
    if not sport:
        return profile
    return {**(profile or {}), "sport": sport}


def _rank_rows(rows, sport, time_context, profile, db, scorer) -> list[dict]:
    d0 = distance_decay_d0(sport, db)
    ranked = rank_nearby(
        rows, time_context, _with_sport(profile, sport), scorer=scorer, d0_km=d0
    )
    return [_ranked_brief(r) for r in ranked]


# --- orchestration ---------------------------------------------------------

def search(
    query: str,
    *,
    sport: str | None = None,
    time_context: dict | None = None,
    profile: dict | None = None,
    db: Session,
    geocoder: Geocoder,
    scorer: Scorer | None = None,
) -> dict:
    """Resolve a free-text query to ranked spots/regions.

    First the own entity index; if it hits, ranked spots in the vicinity of the
    best match are returned alongside the matched regions. Otherwise the query is
    geocoded: a **point** drives an adaptive radius search, an **area** drives a
    **bounds** query. The geocoded place itself is never returned as a hit.
    """
    scorer = scorer or default_scorer(db)
    ent = search_entities(query, db=db)
    regionen, matched_spots = ent["regionen"], ent["spots"]

    if regionen or matched_spots:
        anchor = _anchor_point(matched_spots, regionen)
        if anchor is not None:
            rows = search_nearby_spots(anchor, sport, db=db)
            spots_out = _rank_rows(rows, sport, time_context, profile, db, scorer)
        else:
            spots_out = [spot_brief(s) for s in matched_spots]
        regions_out = [_region_brief(r) for r in regionen]
        return {
            "regionen": regions_out,
            "spots": spots_out,
            "treffer": len(regions_out) + len(spots_out),
            "resolved": "entities",
        }

    geo = classify_geocode(query, geocoder=geocoder)
    if geo is None:
        return {"regionen": [], "spots": [], "treffer": 0, "resolved": "none"}

    if geo["type"] == "point":
        rows = search_nearby_spots(geo["point"], sport, db=db)
    else:
        rows = bounds_query(geo["bounds"], sport, db=db)
    spots_out = _rank_rows(rows, sport, time_context, profile, db, scorer)
    return {
        "regionen": [],
        "spots": spots_out,
        "treffer": len(spots_out),
        "resolved": geo["type"],
        "geocode": {"type": geo["type"], "name": geo["name"]},
    }


def search_geometry(
    shape: dict,
    *,
    sport: str | None = None,
    time_context: dict | None = None,
    profile: dict | None = None,
    db: Session,
    scorer: Scorer | None = None,
) -> dict:
    """Rank spots inside a drawn circle/rectangle."""
    scorer = scorer or default_scorer(db)
    rows = search_by_geometry(shape, sport, db=db)
    spots_out = _rank_rows(rows, sport, time_context, profile, db, scorer)
    return {"shape": shape, "spots": spots_out, "treffer": len(spots_out)}


def query_map(
    bounds: dict,
    *,
    time_context: dict | None = None,
    sport: str | None = None,
    profile: dict | None = None,
    db: Session,
    scorer: Scorer | None = None,
) -> dict:
    """Pins for a viewport bbox, coloured by value."""
    scorer = scorer or default_scorer(db)
    rows = bounds_query(bounds, sport, db=db)
    pins = build_pins(
        [r[0] for r in rows], time_context, _with_sport(profile, sport), scorer=scorer
    )
    return {"bounds": bounds, "sport": sport, "pins": pins}


def query_portfolio(
    level: str = "region",
    *,
    time_context: dict | None = None,
    sport: str | None = None,
    profile: dict | None = None,
    db: Session,
    scorer: Scorer | None = None,
) -> dict:
    """Portfolio of maps, kept in sync with :func:`query_map`'s pin logic.

    ``level="region"`` returns one pin-map per region; ``level="global"`` returns
    a single map of all spots.
    """
    scorer = scorer or default_scorer(db)
    from app.models import Region, Spot
    from app.public_catalog import PUBLISHED

    profile = _with_sport(profile, sport)
    stmt = select(Spot).where(Spot.status == PUBLISHED)
    if sport:
        stmt = stmt.where(Spot.sports.any(sport))
    spots = list(db.scalars(stmt).all())

    if level == "global":
        pins = build_pins(spots, time_context, profile, scorer=scorer)
        return {"level": level, "sport": sport, "maps": [{"region_id": None, "pins": pins}]}

    region_names = {
        str(r.id): r.name
        for r in db.scalars(select(Region).where(Region.status == PUBLISHED)).all()
    }
    by_region: dict[str, list] = {}
    for s in spots:
        by_region.setdefault(str(s.region_id), []).append(s)

    maps = [
        {
            "region_id": rid,
            "region_name": region_names.get(rid),
            "pins": build_pins(rspots, time_context, profile, scorer=scorer),
        }
        for rid, rspots in by_region.items()
    ]
    return {"level": level, "sport": sport, "maps": maps}


def toggle_sport(
    sport: str | None,
    context: dict,
    *,
    db: Session,
    geocoder: Geocoder | None = None,
    scorer: Scorer | None = None,
) -> dict:
    """Re-run the previous query with a new sport filter (re-rank / re-colour).

    ``context`` carries ``kind`` plus the original parameters. Switching to a wave
    sport drops flatwater-only spots because the spatial ``sports`` filter changes.
    """
    kind = context.get("kind")
    tc = context.get("time_context")
    prof = context.get("profile")

    if kind == "search":
        return search(
            context["query"], sport=sport, time_context=tc, profile=prof,
            db=db, geocoder=geocoder, scorer=scorer,
        )
    if kind == "geometry":
        return search_geometry(
            context["shape"], sport=sport, time_context=tc, profile=prof,
            db=db, scorer=scorer,
        )
    if kind == "map":
        return query_map(
            context["bounds"], time_context=tc, sport=sport, profile=prof,
            db=db, scorer=scorer,
        )
    if kind == "portfolio":
        return query_portfolio(
            context.get("level", "region"), time_context=tc, sport=sport,
            profile=prof, db=db, scorer=scorer,
        )
    raise ValueError(f"unknown toggle context kind: {kind!r}")


# --- Sprint 6: open axes, time-window ranking, region reverse ---------------

def _timewindow_brief(r: dict) -> dict:
    return {**spot_brief(r["spot"]), "coverage": r["coverage"], "intensity": r["intensity"]}


def _area_spots(area: dict, db: Session, sport: str | None) -> list:
    """Resolve an 'area' to a list of spots.

    ``area`` is one of ``{"region_id": …}``, ``{"spot_id": …}``,
    ``{"bounds": {…}}`` or ``{"point": {lat, lon}, "radius_km": r}``. An empty/None
    area is the whole catalogue (v1 = Europe).
    """
    from app.models import Spot
    from app.public_catalog import PUBLISHED

    area = area or {}
    if area.get("region_id"):
        stmt = select(Spot).where(
            Spot.region_id == area["region_id"], Spot.status == PUBLISHED
        )
        if sport:
            stmt = stmt.where(Spot.sports.any(sport))
        return list(db.scalars(stmt).all())
    if area.get("spot_id"):
        spot = db.scalar(
            select(Spot).where(
                Spot.id == area["spot_id"], Spot.status == PUBLISHED
            )
        )
        return [spot] if spot is not None else []
    if area.get("bounds"):
        return [row[0] for row in bounds_query(area["bounds"], sport, db=db)]
    if area.get("point"):
        return [
            row[0]
            for row in search_nearby_spots(
                area["point"], sport, db=db, start_km=area.get("radius_km", 25.0)
            )
        ]
    return catalog_spots(db, sport)  # open place → whole catalogue


def catalog_spots(db: Session, sport: str | None) -> list:
    """All spots in the catalogue (v1 scope = Europe), optionally sport-filtered."""
    from app.models import Spot
    from app.public_catalog import PUBLISHED

    stmt = select(Spot).where(Spot.status == PUBLISHED)
    if sport:
        stmt = stmt.where(Spot.sports.any(sport))
    return list(db.scalars(stmt).all())


def best_spots_in_region(
    region_id,
    *,
    db: Session,
    sport: str | None = None,
    profile: dict | None = None,
    window: dict | None = None,
    limit: int | None = None,
) -> dict:
    """Region → spot zoom: rank a region's spots over a time window (coverage)."""
    from app.search.timewindow import rank_by_timewindow

    spots = _area_spots({"region_id": region_id}, db, sport)
    ranked = rank_by_timewindow(spots, window, sport, _with_sport(profile, sport), db=db)
    out = [_timewindow_brief(r) for r in ranked]
    return {"region_id": str(region_id), "sport": sport, "window": window,
            "spots": out[:limit] if limit else out}


def best_spots_open_place(
    *,
    db: Session,
    sport: str | None = None,
    profile: dict | None = None,
    window: dict | None = None,
    limit: int | None = None,
) -> dict:
    """Open *place*: rank the whole catalogue (Europe) over a time window."""
    from app.search.timewindow import rank_by_timewindow

    spots = catalog_spots(db, sport)
    ranked = rank_by_timewindow(spots, window, sport, _with_sport(profile, sport), db=db)
    out = [_timewindow_brief(r) for r in ranked]
    return {"scope": "europe", "sport": sport, "window": window,
            "spots": out[:limit] if limit else out}


def best_regions_for_window(
    window: dict | None,
    *,
    db: Session,
    sport: str | None = None,
    profile: dict | None = None,
    limit: int | None = None,
) -> dict:
    """Rank regions over a time window by coverage of their *best* spot."""
    from sqlalchemy.orm import selectinload

    from app.scoring.region import region_score_series
    from app.search.timewindow import coverage_intensity, window_weeks
    from app.scoring.params import WEEK_GOOD_THRESHOLD, get_params
    from app.models import Region
    from app.public_catalog import PUBLISHED

    weeks = window_weeks(window)
    thr = get_params(sport, db)["week_good_threshold"] if sport else WEEK_GOOD_THRESHOLD

    ranked = []
    # Eager-load spots so the per-region loop isn't an N+1 of lazy loads.
    regions = db.scalars(
        select(Region)
        .where(Region.status == PUBLISHED)
        .options(selectinload(Region.spots))
    ).all()
    for region in regions:
        public_spots = [s for s in region.spots if s.status == PUBLISHED]
        series = region_score_series(public_spots, sport, profile, db)
        cov, inten = coverage_intensity(series, weeks, thr)
        ranked.append(
            {**_region_brief(region), "coverage": round(cov, 4),
             "intensity": round(inten, 4)}
        )
    ranked.sort(key=lambda r: (-r["coverage"], -r["intensity"], r["name"]))
    return {"sport": sport, "window": window,
            "regions": ranked[:limit] if limit else ranked}


def best_weeks_for_area(
    area: dict,
    *,
    db: Session,
    sport: str | None = None,
    profile: dict | None = None,
    top: int | None = None,
) -> dict:
    """Open *time*: rank the 52 weeks for the spots in an area."""
    from app.search.timewindow import best_weeks_for_area as _best_weeks

    spots = _area_spots(area, db, sport)
    weeks = _best_weeks(spots, sport, _with_sport(profile, sport), db=db, top=top)
    return {"area": area, "sport": sport, "spot_count": len(spots), "weeks": weeks}
