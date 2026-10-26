"""Bounded forecast reads for recommendation ranking.

Public recommendation requests must never fan out to weather providers.  The
forecast publisher already persists one active, serving-ready snapshot per
spot; ranking reads those snapshots in one query and treats missing/stale rows
as unavailable.  Local development may still use the legacy live fallback so
the small seed catalogue remains useful without running the publisher worker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.forecast.publisher import MAX_PUBLIC_STALE
from app.models import ForecastSnapshot


def provider_fallback_allowed() -> bool:
    """Only local databases may fetch provider data on the request path."""
    return get_settings().database_target == "local"


def persisted_forecast_days(
    db: Session,
    spot_ids: Iterable[uuid.UUID],
    *,
    now: datetime | None = None,
) -> dict[uuid.UUID, list[dict]]:
    """Load usable active forecast days for many spots with one DB query."""
    ids = list(dict.fromkeys(spot_ids))
    if not ids:
        return {}
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = instant - MAX_PUBLIC_STALE
    rows = db.scalars(
        select(ForecastSnapshot)
        .where(
            ForecastSnapshot.spot_id.in_(ids),
            ForecastSnapshot.active.is_(True),
            ForecastSnapshot.valid_until >= cutoff,
        )
        .order_by(ForecastSnapshot.generated_at.desc())
    ).all()
    result: dict[uuid.UUID, list[dict]] = {}
    for row in rows:
        # Defensive first-row-wins ordering also survives historical databases
        # that predate the one-active-snapshot invariant.
        if row.spot_id in result or not isinstance(row.payload, dict):
            continue
        days = row.payload.get("days")
        if not isinstance(days, list):
            continue
        usable = [day for day in days if isinstance(day, dict) and day.get("hours")]
        if usable:
            result[row.spot_id] = usable
    return result
