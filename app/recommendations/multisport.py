"""Recommendation ranking for the sports the personalized rider engine does not
cover, plus the logged-out "all sports" aggregate.

Kitesurf is ranked by the personalized rider-band engine in
:mod:`app.recommendations.service`. Every other sport — and the cross-sport
aggregate shown to logged-out visitors under "Alle Sportarten" — is ranked here
with the **existing** categorical scoring (gates + magnitude on the forecast
window for ``now``/``next_week``/``region``; the season climatology curve for
``season``). No personal wind band is invented; the only rider input honored is
the sport level, which shifts the ideal band via ``level_offsets``.

The aggregate combines a spot's supported sports with **max** ("best sport
wins"): a spot is ranked by the single sport it is currently best for.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.live.cache import Cache
from app.live.client import OpenMeteoClient
from app.models import Spot
from app.recommendations.service import (
    CACHE_VERSION,
    LocationBucket,
    RecommendationSurface,
    _cache_ttl,
    _spot_coords,
    _with_daylight,
)
from app.scoring.context import spot_editorial
from app.scoring.evaluate import evaluate_conditions
from app.scoring.params import SCORING_PARAMS_VERSION, get_params
from app.search.timewindow import (
    coverage_intensity,
    resolve_time_window,
    spot_week_scores,
    window_weeks,
)

# The sports whose recommendation surfaces this module serves. Kitesurf is
# handled by the personalized engine; the aggregate spans all four.
SCORED_SPORTS = ("windsurf", "wing", "surf")
AGGREGATE_SPORTS = ("kitesurf", "windsurf", "wing", "surf")

# Categorical rating → a bounded utility. "gut" fully counts, "mäßig" half,
# "nein" not at all — the fraction of good daylight hours over the window.
_RATING_SCORE = {"gut": 1.0, "mäßig": 0.5, "nein": 0.0}


def _load_candidates(
    db: Session, *, sports: Sequence[str], region_id: uuid.UUID | None = None
) -> list[Spot]:
    stmt = (
        select(Spot)
        .where(Spot.status == "published", Spot.sports.overlap(list(sports)))
        .options(selectinload(Spot.region))
    )
    if region_id is not None:
        stmt = stmt.where(Spot.region_id == region_id)
    return list(db.scalars(stmt))


def _forecast_days(
    spot: Spot,
    surface: RecommendationSurface,
    *,
    db: Session,
    client: OpenMeteoClient,
    cache: Cache,
) -> list[dict]:
    """The daylight-annotated forecast slice a surface scores over (once/spot)."""
    from app.live.service import get_forecast_series

    series = get_forecast_series(spot.id, 10, db=db, client=client, cache=cache)
    days = list(series.get("days") or [])
    selected = days[2:10] if surface == RecommendationSurface.NEXT_WEEK else days[:2]
    return _with_daylight(selected, _spot_coords(spot))


def _forecast_score(
    spot: Spot, sport: str, days: list[dict], profile: dict | None, params: dict
) -> float:
    """Share of daylight forecast hours rated good (gut=1, mäßig=0.5) for a sport."""
    editorial = spot_editorial(spot)
    good = 0.0
    total = 0
    for day in days:
        for hour in day.get("hours") or []:
            if hour.get("is_day") is False:
                continue
            values = {
                "wind_kt": hour.get("wind"),
                "gust_kt": hour.get("gust"),
                "wind_dir": hour.get("dir"),
                "swell_m": hour.get("swell"),
                "period_s": hour.get("period"),
                "swell_dir": hour.get("swell_dir"),
                "air": hour.get("air"),
                "sst": hour.get("sst"),
                "tide": None,
                "daylight": True,
            }
            rating = evaluate_conditions(values, editorial, profile, sport, params)["rating"]
            good += _RATING_SCORE.get(rating, 0.0)
            total += 1
    return good / total if total else 0.0


def _season_score(
    spot: Spot, sport: str, profile: dict | None, window: dict, params: dict, db: Session
) -> float:
    """Climatology fit over the window — coverage-first, matching the kite path."""
    weeks = window_weeks(window)
    scores = spot_week_scores(spot, sport, profile, params, db)
    coverage, intensity = coverage_intensity(scores, weeks, params["week_good_threshold"])
    return 0.65 * coverage + 0.35 * intensity


def _cache_key(
    *,
    sports: Sequence[str],
    surface: RecommendationSurface,
    region_id: uuid.UUID | None,
    month: int | None,
    weeks: tuple[int, int] | None,
    level: str | None,
    limit: int,
) -> str:
    return ":".join(
        (
            "recommendations-ms",
            f"v{CACHE_VERSION}",
            ",".join(sorted(sports)),
            surface.value,
            str(region_id or "global"),
            str(month or "open"),
            f"{weeks[0]}-{weeks[1]}" if weeks else "open",
            level or "anon",
            str(limit),
            f"params-{SCORING_PARAMS_VERSION}",
        )
    )


def scored_recommendations(
    db: Session,
    *,
    surface: RecommendationSurface,
    sports: Sequence[str],
    client: OpenMeteoClient,
    cache: Cache,
    level: str | None = None,
    region_id: uuid.UUID | None = None,
    month: int | None = None,
    weeks: tuple[int, int] | None = None,
    limit: int = 12,
    now: datetime | None = None,
) -> list[Spot]:
    """Rank spots for one non-kite sport, or the cross-sport aggregate (max).

    ``sports`` holds the sport(s) to rank; a single entry ranks that sport, the
    four-sport set produces the aggregate. ``level`` (a rider's level for the
    single-sport case) shifts the ideal band; ``None`` ranks anonymously.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    key = _cache_key(
        sports=sports, surface=surface, region_id=region_id,
        month=month, weeks=weeks, level=level, limit=limit,
    )
    hit = cache.get(key)
    if isinstance(hit, list):
        return _ordered_spots(db, hit)

    profile = {"level": level} if level else None
    window: dict | None = None
    if surface == RecommendationSurface.SEASON:
        range_input: dict[str, Any] | None = None
        if month is not None:
            range_input = {"month": month}
        elif weeks is not None:
            range_input = {"weeks": list(weeks)}
        window = resolve_time_window("season", range_input)

    params_by_sport = {sport: get_params(sport, db) for sport in sports}
    scored: list[tuple[Spot, float]] = []
    for spot in _load_candidates(db, sports=sports, region_id=region_id):
        spot_sports = [sport for sport in sports if sport in (spot.sports or [])]
        if not spot_sports:
            continue
        if surface == RecommendationSurface.SEASON:
            best = max(
                _season_score(spot, sport, profile, window, params_by_sport[sport], db)
                for sport in spot_sports
            )
        else:
            days = _forecast_days(spot, surface, db=db, client=client, cache=cache)
            best = max(
                _forecast_score(spot, sport, days, profile, params_by_sport[sport])
                for sport in spot_sports
            )
        if best > 0:
            scored.append((spot, best))

    scored.sort(key=lambda item: (-item[1], item[0].name.casefold()))
    ids = [str(spot.id) for spot, _score in scored[:limit]]
    cache.set(key, ids, _cache_ttl(surface))
    return _ordered_spots(db, ids)


def _ordered_spots(db: Session, ids: list[str]) -> list[Spot]:
    parsed = [uuid.UUID(value) for value in ids]
    if not parsed:
        return []
    by_id = {
        spot.id: spot
        for spot in db.scalars(
            select(Spot).where(Spot.id.in_(parsed)).options(selectinload(Spot.region))
        )
    }
    return [by_id[spot_id] for spot_id in parsed if spot_id in by_id]
