"""ERA5 job triggering / status for the admin path."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

ACTIVE_JOB_STATUSES = ("queued", "processing", "extracting")


def trigger_era5_job(
    spot_id,
    *,
    db: Session,
    client,
    force: bool = False,
    reason: str = "missing",
):
    """Persist a climatology job.

    Normal triggers reuse an active/current job.  A manual calculation and a
    changed grid cell deliberately supersede an active job so they can never
    finish with obsolete inputs.
    """
    from app.era5.cds import request_era5_extract
    from app.era5.freshness import CLIMATOLOGY_ALGORITHM_VERSION
    from app.era5.grid import resolve_grid_cell
    from app.models import Era5Job, Spot

    spot = db.scalar(select(Spot).where(Spot.id == spot_id).with_for_update())
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")

    cell = spot.era5_cell
    if not cell:
        from geoalchemy2.shape import to_shape

        p = to_shape(spot.location)
        cell = resolve_grid_cell(p.y, p.x)
        spot.era5_cell = cell
        db.flush()

    active = db.scalar(
        select(Era5Job)
        .where(Era5Job.spot_id == spot.id, Era5Job.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(Era5Job.created_at.desc())
    )
    replace_active = force and reason in {"manual", "location_changed"}
    if active is not None and not replace_active:
        db.commit()
        return active
    if active is not None:
        active.status = "superseded"
        db.flush()

    job = request_era5_extract(
        spot.id,
        cell,
        db=db,
        client=client,
        force=force,
        job_metadata={
            "reason": reason,
            "attempt_count": 0,
            "next_attempt_at": None,
            "algorithm_version": CLIMATOLOGY_ALGORITHM_VERSION,
        },
    )
    # request_era5_extract commits newly created jobs, but may return an existing
    # derived one. Always end the transaction here so the spot row lock cannot
    # block the synchronous compute session that follows.
    db.commit()
    return job


def supersede_active_jobs(spot_id, *, db: Session, commit: bool = True) -> int:
    """Prevent queued work from writing data for an obsolete grid cell."""
    from app.models import Era5Job

    jobs = db.scalars(
        select(Era5Job).where(
            Era5Job.spot_id == spot_id,
            Era5Job.status.in_(ACTIVE_JOB_STATUSES),
        )
    ).all()
    for job in jobs:
        job.status = "superseded"
    if jobs and commit:
        db.commit()
    return len(jobs)


def get_job_status(spot_id, *, db: Session) -> dict | None:
    """Combined job and stored-snapshot freshness status for one spot."""
    from app.era5.freshness import stale_reasons, state
    from app.models import Era5Job, Spot

    spot = db.get(Spot, spot_id)
    if spot is None:
        return None
    freshness = state(spot)
    reasons = stale_reasons(spot) if freshness == "stale" else []

    job = db.scalar(
        select(Era5Job)
        .where(Era5Job.spot_id == spot_id)
        .order_by(Era5Job.created_at.desc())
    )
    status = freshness
    if job is not None and job.status in ACTIVE_JOB_STATUSES:
        status = job.status
    elif job is not None and job.status == "failed" and freshness != "current":
        status = "failed"
    result = {
        "spot_id": str(spot.id),
        "status": status,
        "freshness_status": freshness,
        "stale_reasons": reasons,
        "generated_at": (spot.climatology or {}).get("generated_at"),
        "window": (spot.climatology or {}).get("window"),
        "error": job.error if job is not None else None,
    }
    if job is not None:
        result.update(
            {
                "job_id": str(job.id),
                "raw_path": job.raw_path,
                "cell": job.cell,
                "attempt_count": (job.params or {}).get("attempt_count", 0),
                "reason": (job.params or {}).get("reason"),
            }
        )
    return result
