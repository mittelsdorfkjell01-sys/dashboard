"""Consolidated operations view.

One place that answers the operator's questions without log access: which spots
have current/stale/missing/failed climatology, how deep the job queue is, and
what the recent ERA5 runs did (status, duration, error category). Reads the
existing ``Era5Job`` rows and freshness state — it starts no work and defines no
new pipeline.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.era5_worker import climatology_summary, count_queued
from app.models import Era5Job, Spot


def _error_category(error: str | None) -> str | None:
    """Coarse, log-free classification so an operator sees *why* a run failed."""
    if not error:
        return None
    e = error.lower()
    if any(k in e for k in ("quota", "rate limit", "429", "too many")):
        return "quota"
    if any(k in e for k in ("coordinate", "grid", "cell", "land", "sea")):
        return "coordinates"
    if any(k in e for k in ("valid", "schema", "parse")):
        return "validation"
    if any(k in e for k in ("timeout", "network", "unavailable", "connection", "http", "provider")):
        return "provider"
    return "unknown"


def _duration_s(job: Era5Job) -> float | None:
    if job.started_at and job.completed_at:
        return round((job.completed_at - job.started_at).total_seconds(), 1)
    return None


def recent_jobs(db: Session, *, limit: int = 25) -> list[dict]:
    jobs = db.scalars(
        select(Era5Job).order_by(Era5Job.created_at.desc()).limit(limit)
    ).all()
    spot_ids = [j.spot_id for j in jobs if j.spot_id is not None]
    names: dict = {}
    if spot_ids:
        for s in db.scalars(select(Spot).where(Spot.id.in_(spot_ids))).all():
            names[s.id] = s.name
    out: list[dict] = []
    for j in jobs:
        params = j.params or {}
        out.append({
            "job_id": str(j.id),
            "spot_id": str(j.spot_id) if j.spot_id else None,
            "spot_name": names.get(j.spot_id),
            "status": j.status,
            "error": j.error,
            "error_category": _error_category(j.error),
            "reason": params.get("reason"),
            "attempt_count": params.get("attempt_count", 0),
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "duration_s": _duration_s(j),
        })
    return out


def _job_status_counts(db: Session) -> dict[str, int]:
    """Latest job per spot, grouped by status — the operational snapshot."""
    jobs = db.scalars(select(Era5Job).order_by(Era5Job.created_at.desc())).all()
    latest: dict = {}
    for j in jobs:
        if j.spot_id is not None and j.spot_id not in latest:
            latest[j.spot_id] = j.status
    counts: dict[str, int] = {}
    for status in latest.values():
        counts[status] = counts.get(status, 0) + 1
    return counts


def operations_summary(db: Session) -> dict:
    return {
        "freshness": climatology_summary(db),  # {missing, stale, current, failed}
        "queue_depth": count_queued(db),
        "job_status": _job_status_counts(db),
        "recent_jobs": recent_jobs(db),
        # When a fix becomes visible publicly (from the known schedule + edge cache;
        # see vercel.json cron + app/api/_http_cache.py).
        "public_update": {
            "climatology_cron": "täglich 04:15 UTC",
            "edge_cache": "Öffentliche Listen/Detail ≤ 10 s; Top-Spots bis 6 h (Edge-Cache).",
        },
    }
