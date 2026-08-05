"""Similarity orchestration: find_similar_spots (3 modes) + find_alternatives."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.scoring import Scorer, default_scorer, distance_decay_d0
from app.scoring.context import primary_sport
from app.scoring.engine import _week_of
from app.scoring.params import SCORING_PARAMS_V1, WEEK_GOOD_THRESHOLD, get_params
from app.search.pins import coords, spot_brief
from app.search.ranking import rank_nearby
from app.search.timewindow import spot_week_scores
from app.similarity.character import character_distance
from app.similarity.season import season_distance_spots

MODE_CHARACTER = "charakter"
MODE_SEASON = "saison"
MODE_BOTH = "beides"
_MODES = {MODE_CHARACTER, MODE_SEASON, MODE_BOTH}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _same(a: Any, b: Any) -> bool:
    return a is b or getattr(a, "id", None) == getattr(b, "id", object())


# --- pure cores ------------------------------------------------------------

def find_similar_core(
    target: Any,
    candidates: list[Any],
    mode: str,
    sport: str | None = None,
    profile: dict | None = None,
    *,
    char_weight: float = 0.5,
) -> list[dict]:
    """Rank candidates by similarity to ``target`` (ascending distance)."""
    if mode not in _MODES:
        raise ValueError(f"unknown mode: {mode!r}")
    results: list[dict] = []
    for cand in candidates:
        if _same(cand, target):
            continue
        char = season = None
        if mode in (MODE_CHARACTER, MODE_BOTH):
            char = character_distance(target, cand, sport)
        if mode in (MODE_SEASON, MODE_BOTH):
            season = season_distance_spots(target, cand, sport, profile)
        if mode == MODE_CHARACTER:
            dist = char
        elif mode == MODE_SEASON:
            dist = season
        else:
            dist = round(char_weight * char + (1 - char_weight) * season, 4)
        results.append({"spot": cand, "distance": dist, "character": char, "season": season})
    results.sort(key=lambda r: (r["distance"], getattr(r["spot"], "name", "")))
    return results


def find_alternatives_core(
    target: Any,
    candidates: list[Any],
    week: int,
    sport: str | None,
    profile: dict | None,
    *,
    scorer: Scorer,
    d0_km: float,
    threshold: float,
    db: Any | None = None,
) -> list[dict]:
    """Character-similar spots that *run* in ``week``, ranked score × distance."""
    tlat, tlon = coords(target)
    prof = {**(profile or {}), "sport": sport} if sport else profile

    items: list[tuple[Any, float]] = []
    char_by_id: dict[Any, float] = {}
    for cand in candidates:
        if _same(cand, target):
            continue
        scores = spot_week_scores(cand, sport, profile, db=db)
        if scores[week - 1] < threshold:  # only spots running in the window
            continue
        clat, clon = coords(cand)
        items.append((cand, haversine_m(tlat, tlon, clat, clon)))
        char_by_id[id(cand)] = character_distance(target, cand, sport)

    ranked = rank_nearby(items, {"week": week}, prof, scorer=scorer, d0_km=d0_km)
    for r in ranked:
        r["character"] = char_by_id.get(id(r["spot"]))
    return ranked


# --- serialisation ---------------------------------------------------------

def _similar_brief(r: dict) -> dict:
    return {
        **spot_brief(r["spot"]),
        "distance": r["distance"],
        "character": r["character"],
        "season": r["season"],
    }


def _alt_brief(r: dict) -> dict:
    return {
        **spot_brief(r["spot"]),
        "distance_m": round(r["distance_m"], 1) if r["distance_m"] is not None else None,
        "score": r["score"],
        "rank_score": r["rank_score"],
        "character": r["character"],
    }


# --- DB wrappers -----------------------------------------------------------

def _load_spot(db: Session, spot_id):
    from app.models import Spot
    from app.public_catalog import PUBLISHED

    spot = db.scalar(
        select(Spot).where(Spot.id == spot_id, Spot.status == PUBLISHED)
    )
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    return spot


def _candidates(db: Session, sport: str | None) -> list:
    from app.models import Spot
    from app.public_catalog import PUBLISHED

    stmt = select(Spot).where(Spot.status == PUBLISHED)
    if sport:
        stmt = stmt.where(Spot.sports.any(sport))
    return list(db.scalars(stmt).all())


def find_similar_spots(
    spot_id,
    mode: str = MODE_CHARACTER,
    sport: str | None = None,
    profile: dict | None = None,
    *,
    db: Session,
    limit: int | None = None,
) -> dict:
    """Spots similar to ``spot_id`` by character / season / both."""
    target = _load_spot(db, spot_id)
    candidates = _candidates(db, sport)
    results = find_similar_core(target, candidates, mode, sport, profile)
    out = [_similar_brief(r) for r in results]
    return {"spot_id": str(target.id), "mode": mode, "sport": sport,
            "results": out[:limit] if limit else out}


def find_alternatives(
    spot_id,
    time_context: dict | None = None,
    sport: str | None = None,
    profile: dict | None = None,
    *,
    db: Session,
    scorer: Scorer | None = None,
    limit: int | None = None,
) -> dict:
    """Character-similar spots running in the time window, ranked score × distance."""
    target = _load_spot(db, spot_id)
    sport = sport or primary_sport(target)
    scorer = scorer or default_scorer(db)
    week = _week_of(time_context)
    d0 = distance_decay_d0(sport, db)
    threshold = (
        get_params(sport, db)["week_good_threshold"]
        if sport in SCORING_PARAMS_V1
        else WEEK_GOOD_THRESHOLD
    )
    candidates = _candidates(db, sport)
    ranked = find_alternatives_core(
        target, candidates, week, sport, profile,
        scorer=scorer, d0_km=d0, threshold=threshold, db=db,
    )
    out = [_alt_brief(r) for r in ranked]
    return {"spot_id": str(target.id), "sport": sport, "week": week,
            "alternatives": out[:limit] if limit else out}
