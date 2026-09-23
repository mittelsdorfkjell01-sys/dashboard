"""Privacy-safe social signal for kitesurf recommendation ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import uuid

from sqlalchemy import select


@dataclass(frozen=True, slots=True)
class SocialResult:
    score: float
    group_size: int
    positive_count: int
    available: bool


def bayesian_positive_share(
    signals: Iterable[tuple[str, bool]],
    *,
    min_group_size: int,
    prior_mean: float = 0.5,
    prior_strength: float = 5.0,
) -> SocialResult:
    """Shrink one latest binary signal per actor and enforce k-anonymity."""
    latest: dict[str, bool] = {}
    for actor, positive in signals:
        latest[str(actor)] = bool(positive)
    n = len(latest)
    positives = sum(latest.values())
    if n < min_group_size:
        return SocialResult(prior_mean, n, positives, False)
    score = (prior_strength * prior_mean + positives) / (prior_strength + n)
    return SocialResult(max(0.0, min(1.0, score)), n, positives, True)


def social_score_for_spot(
    db,
    *,
    spot_id: uuid.UUID,
    sport: str,
    level: str,
    min_group_size: int,
    band_fingerprint: str | None = None,
    similar_band: bool = False,
) -> SocialResult:
    return social_scores_for_spots(
        db,
        spot_ids=[spot_id],
        sport=sport,
        level=level,
        min_group_size=min_group_size,
        band_fingerprint=band_fingerprint,
        similar_band=similar_band,
    )[spot_id]


def social_scores_for_spots(
    db,
    *,
    spot_ids: Iterable[uuid.UUID],
    sport: str,
    level: str,
    min_group_size: int,
    band_fingerprint: str | None = None,
    similar_band: bool = False,
) -> dict[uuid.UUID, SocialResult]:
    """Aggregate favorites, worthwhile check-ins, and published 4+ ratings.

    Signals are reduced to one value per account. Check-ins win over ratings,
    which win over favorites, so a frequent user cannot dominate an aggregate.
    """
    from app.admin.constants import LEVELS
    from app.models import (
        Favorite,
        RecommendationLog,
        RiderProfile,
        RiderSportProfile,
        SpotRating,
        UserEvent,
    )

    spot_ids = list(dict.fromkeys(spot_ids))
    if not spot_ids:
        return {}
    try:
        index = LEVELS.index(level)
    except ValueError:
        index = LEVELS.index("advanced")
    allowed = LEVELS[max(0, index - 1) : min(len(LEVELS), index + 2)]
    actor_ids = set(db.scalars(
        select(RiderProfile.app_user_id)
        .join(RiderSportProfile, RiderSportProfile.rider_profile_id == RiderProfile.id)
        .where(
            RiderSportProfile.sport == sport,
            RiderSportProfile.level.in_(allowed),
        )
    ).all())
    if similar_band and band_fingerprint and actor_ids:
        matching = set(db.scalars(
            select(RecommendationLog.app_user_id)
            .where(
                RecommendationLog.app_user_id.in_(actor_ids),
                RecommendationLog.profile_fingerprint == band_fingerprint,
            )
            .distinct()
        ).all())
        actor_ids.intersection_update(matching)
    if not actor_ids:
        unavailable = bayesian_positive_share([], min_group_size=min_group_size)
        return {spot_id: unavailable for spot_id in spot_ids}

    by_spot: dict[uuid.UUID, dict[uuid.UUID, bool]] = {
        spot_id: {} for spot_id in spot_ids
    }
    for found_spot, actor in db.execute(
        select(Favorite.spot_id, Favorite.app_user_id).where(
            Favorite.spot_id.in_(spot_ids),
            Favorite.app_user_id.in_(actor_ids),
        )
    ).all():
        by_spot[found_spot][actor] = True
    for found_spot, actor, stars in db.execute(
        select(SpotRating.spot_id, SpotRating.app_user_id, SpotRating.stars).where(
            SpotRating.spot_id.in_(spot_ids),
            SpotRating.app_user_id.in_(actor_ids),
            SpotRating.status == "published",
        ).order_by(SpotRating.created_at)
    ).all():
        if actor is not None:
            by_spot[found_spot][actor] = int(stars) >= 4
    for found_spot, actor, context in db.execute(
        select(UserEvent.spot_id, UserEvent.app_user_id, UserEvent.context).where(
            UserEvent.spot_id.in_(spot_ids),
            UserEvent.app_user_id.in_(actor_ids),
            UserEvent.type == "session_checkin",
        ).order_by(UserEvent.created_at)
    ).all():
        outcome = (context or {}).get("outcome")
        if actor is not None and outcome in {"worthwhile", "not_worthwhile"}:
            by_spot[found_spot][actor] = outcome == "worthwhile"
    return {
        spot_id: bayesian_positive_share(
            ((str(actor), positive) for actor, positive in by_spot[spot_id].items()),
            min_group_size=min_group_size,
        )
        for spot_id in spot_ids
    }
