"""Controlled Europe-wide bootstrap of private FES tide profiles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Spot, TideCalculationRun, TideProfile
from app.public_catalog import PUBLISHED
from app.tides import ALGORITHM_VERSION, MODEL_NAME, MODEL_VERSION
from app.tides.service import _add_revision

MARINE_WATER_TYPES = ("ocean", "sea", "lagoon")


def bootstrap_europe_profiles(
    db: Session,
    *,
    apply: bool,
    limit: int = 25,
    actor: str = "tide-europe-bootstrap",
) -> dict:
    """Enable and queue a bounded batch without ever publishing it."""

    spots = list(db.scalars(
        select(Spot)
        .where(Spot.status == PUBLISHED, Spot.water_type.overlap(list(MARINE_WATER_TYPES)))
        .options(selectinload(Spot.weather_profile))
        .order_by(Spot.id)
    ))
    spot_ids = [spot.id for spot in spots]
    profiles = {
        profile.spot_id: profile
        for profile in db.scalars(select(TideProfile).where(TideProfile.spot_id.in_(spot_ids)))
    } if spot_ids else {}
    active_runs = set(db.scalars(
        select(TideCalculationRun.spot_id).where(
            TideCalculationRun.spot_id.in_(spot_ids),
            TideCalculationRun.status.in_(("queued", "running")),
        )
    )) if spot_ids else set()

    candidates: list[tuple[Spot, TideProfile | None, str]] = []
    counts = {
        "eligible": len(spots),
        "created": 0,
        "enabled": 0,
        "queued": 0,
        "pending": 0,
        "awaiting_review": 0,
        "failed": 0,
        "active": 0,
    }
    for spot in spots:
        profile = profiles.get(spot.id)
        if profile is None:
            candidates.append((spot, None, "create"))
        elif not profile.enabled:
            candidates.append((spot, profile, "enable"))
        elif spot.id in active_runs:
            counts["pending"] += 1
        elif profile.calculation_status == "failed" or profile.anchor_status == "invalid":
            counts["failed"] += 1
        elif profile.anchor_status == "auto_selected":
            counts["awaiting_review"] += 1
        elif profile.anchor_status == "reviewed" and profile.calculation_status == "ready":
            counts["active"] += 1
        elif profile.automatic_anchor is None and profile.manual_anchor is None:
            candidates.append((spot, profile, "queue"))
        else:
            counts["awaiting_review"] += 1

    selected = candidates[:max(0, limit)]
    counts["selected"] = len(selected)
    counts["remaining"] = max(0, len(candidates) - len(selected))
    if not apply:
        counts["dry_run"] = True
        counts["planned"] = [
            {"spot_id": str(spot.id), "spot": spot.name, "action": action}
            for spot, _profile, action in selected
        ]
        return counts

    for spot, profile, action in selected:
        if profile is None:
            profile = TideProfile(
                spot_id=spot.id,
                enabled=True,
                public_enabled=False,
                timezone=getattr(spot.weather_profile, "timezone", None),
                model_name=MODEL_NAME,
                model_version=MODEL_VERSION,
                anchor_status="needs_review",
                quality_status="unavailable",
                calculation_status="queued",
                edited_by=actor,
            )
            db.add(profile)
            db.flush()
            _add_revision(db, profile, "Europaweiter FES-Bootstrap", actor)
            counts["created"] += 1
        elif action == "enable":
            profile.enabled = True
            profile.public_enabled = False
            profile.edited_by = actor
            profile.version += 1
            profile.calculation_status = "queued"
            profile.calculation_error = None
            _add_revision(db, profile, "Für europaweiten FES-Rollout aktiviert", actor)
            counts["enabled"] += 1
        else:
            profile.calculation_status = "queued"
            profile.calculation_error = None

        has_anchor = profile.manual_anchor is not None or profile.automatic_anchor is not None
        action_name = "calculate" if has_anchor else "anchor_and_calculate"
        db.add(TideCalculationRun(
            spot_id=spot.id,
            status="queued",
            requested_by=actor,
            model_name=profile.model_name,
            model_version=profile.model_version,
            algorithm_version=ALGORITHM_VERSION,
            profile_version=profile.version,
            details={"action": action_name, "reason": "europe_rollout"},
        ))
        counts["queued"] += 1

    db.commit()
    counts["dry_run"] = False
    return counts
