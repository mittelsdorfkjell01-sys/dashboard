"""Online recommendation quality metrics with stable audience segmentation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def recommendation_quality(db, *, days: int = 30) -> dict:
    from app.models import RecommendationLog, UserEvent

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    logs = list(db.scalars(
        select(RecommendationLog)
        .where(RecommendationLog.created_at >= start)
        .order_by(RecommendationLog.created_at)
    ))
    events = list(db.scalars(
        select(UserEvent)
        .where(
            UserEvent.created_at >= start,
            UserEvent.type.in_((
                "impression", "click", "favorite_add", "session_checkin"
            )),
        )
        .order_by(UserEvent.created_at)
    ))

    by_key: dict[tuple[object, str], list] = defaultdict(list)
    by_id = {row.id: row for row in logs}
    for row in logs:
        by_key[(row.spot_id, row.surface)].append(row)

    counters: dict[tuple[str, str, int], dict[str, object]] = defaultdict(
        lambda: {
            "impressions": set(), "clicks": set(), "favorites": set(),
            "checkins": set(), "worthwhile": set(), "outcomes": set(),
        }
    )

    def actor(event) -> str:
        return f"user:{event.app_user_id}" if event.app_user_id else f"anon:{event.anon_id}"

    for event in events:
        log = by_id.get(event.recommendation_log_id)
        if log is None and event.spot_id is not None and event.surface:
            candidates = by_key.get((event.spot_id, event.surface), [])
            log = next((
                candidate
                for candidate in reversed(candidates)
                if candidate.created_at <= event.created_at
                and candidate.created_at >= event.created_at - timedelta(hours=72)
                and (
                    candidate.app_user_id == event.app_user_id
                    if event.app_user_id is not None
                    else candidate.app_user_id is None
                )
            ), None)
        if log is None:
            continue
        group = counters[(log.surface, log.audience_segment, log.params_version)]
        identity = (actor(event), str(event.spot_id), str(log.id))
        if event.type == "impression":
            group["impressions"].add(identity)
        elif event.type == "click":
            group["clicks"].add(identity)
        elif event.type == "favorite_add":
            group["favorites"].add(identity)
        elif event.type == "session_checkin":
            group["checkins"].add(identity)
            outcome = (event.context or {}).get("outcome")
            if outcome in {"worthwhile", "not_worthwhile"}:
                group["outcomes"].add(identity)
                if outcome == "worthwhile":
                    group["worthwhile"].add(identity)

    rows = []
    for (surface, segment, version), values in sorted(counters.items()):
        impressions = len(values["impressions"])
        clicks = len(values["clicks"] & values["impressions"])
        favorites = len(values["favorites"] & values["impressions"])
        checkins = len(values["checkins"] & values["impressions"])
        outcomes = len(values["outcomes"])
        worthwhile = len(values["worthwhile"])
        rows.append({
            "surface": surface,
            "audience": segment,
            "params_version": version,
            "impressions": impressions,
            "ctr": _rate(clicks, impressions),
            "favorite_rate": _rate(favorites, impressions),
            "checkin_rate": _rate(checkins, impressions),
            "worthwhile_share": _rate(worthwhile, outcomes),
            "checkins_with_outcome": outcomes,
        })
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "rows": rows,
        "totals": {
            "recommendation_calculations": len(logs),
            "events": len(events),
        },
    }
