"""Freshness rules for stored spot climatologies.

Climatology is a durable snapshot, not live weather.  A snapshot remains usable
while a replacement is queued, but it becomes stale when its rolling data
window, grid cell, smoothing configuration, or derivation algorithm changes.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any

from app.config import get_settings
from app.era5.cds import last_available_years, window_label

CLIMATOLOGY_SCHEMA_VERSION = 1
CLIMATOLOGY_ALGORITHM_VERSION = "2026.1"
CLIMATOLOGY_YEARS = 20


def expected_window(today: date | None = None) -> str:
    return window_label(last_available_years(CLIMATOLOGY_YEARS, today=today))


def stale_reasons(spot: Any, *, today: date | None = None) -> list[str]:
    record = getattr(spot, "climatology", None)
    if not isinstance(record, dict) or not record.get("weeks"):
        return ["missing"]

    reasons: list[str] = []
    if record.get("window") != expected_window(today):
        reasons.append("data_window")
    if record.get("schema_version") != CLIMATOLOGY_SCHEMA_VERSION:
        reasons.append("schema_version")
    if record.get("algorithm_version") != CLIMATOLOGY_ALGORITHM_VERSION:
        reasons.append("algorithm_version")
    if record.get("grid_cell") != getattr(spot, "era5_cell", None):
        reasons.append("grid_cell")
    smoothing = record.get("smoothing") or {}
    if smoothing.get("window_weeks") != get_settings().climatology_smooth_weeks:
        reasons.append("smoothing")
    return reasons


def state(spot: Any, *, today: date | None = None) -> str:
    reasons = stale_reasons(spot, today=today)
    if reasons == ["missing"]:
        return "missing"
    return "stale" if reasons else "current"


def mark_stale(record: dict | None, reason: str) -> dict | None:
    """Mark a usable snapshot stale without deleting its weekly data."""
    if not isinstance(record, dict) or not record.get("weeks"):
        return record
    updated = deepcopy(record)
    freshness = dict(updated.get("freshness") or {})
    reasons = list(freshness.get("reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    freshness.update(
        {
            "status": "stale",
            "reasons": reasons,
            "stale_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    updated["freshness"] = freshness
    return updated


def finalize_record(record: dict, grid_cell: dict) -> dict:
    """Attach the metadata needed to determine future freshness."""
    record["schema_version"] = CLIMATOLOGY_SCHEMA_VERSION
    record["algorithm_version"] = CLIMATOLOGY_ALGORITHM_VERSION
    record["grid_cell"] = deepcopy(grid_cell)
    record["freshness"] = {"status": "current", "reasons": []}
    return record
