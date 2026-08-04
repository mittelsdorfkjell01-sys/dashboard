"""Background ERA5 processing for the admin path.

Turns a *queued* ERA5 job into a derived climatology without waiting for the CLI
batch runner — used as a FastAPI ``BackgroundTask`` so the request returns
immediately. Reuses the tested per-spot pipeline (:func:`app.era5.batch.process_spot`)
and opens its own DB session (the request's session is closed by the time the
background task runs).
"""

from __future__ import annotations

import threading
import time

from sqlalchemy import func, select

from app.config import get_settings
from app.db.session import SessionLocal
from app.era5 import batch
from app.models import Era5Job, Spot


def count_queued(db) -> int:
    """Number of distinct spots with a queued ERA5 job."""
    return int(
        db.scalar(
            select(func.count(func.distinct(Era5Job.spot_id))).where(
                Era5Job.status == "queued"
            )
        )
        or 0
    )


def process_one(spot_id, *, client, raw_dir: str | None = None) -> tuple[str, str]:
    """Process a single spot's climatology in its own session. Never raises."""
    db = SessionLocal()
    try:
        spot = db.get(Spot, spot_id)
        if spot is None:
            return "fail", "unknown spot"
        try:
            return batch.process_spot(
                db, spot, client=client, years=20, force=False, raw_dir=raw_dir
            )
        except Exception as exc:  # keep background work from crashing the worker
            db.rollback()
            return "fail", f"{type(exc).__name__}: {exc}"
    finally:
        db.close()


def compute_now(spot_id, *, client) -> tuple[str, str]:
    """Compute + store a spot's climatology **synchronously and in memory** (no
    on-disk Parquet), in its own session. Serverless-safe — used inline on
    go-live / the manual ERA5 trigger, where FastAPI background tasks don't run
    reliably and pyarrow isn't bundled. Never raises."""
    from app.era5 import pipeline

    db = SessionLocal()
    try:
        spot = db.get(Spot, spot_id)
        if spot is None:
            return "fail", "unknown spot"
        pipeline.derive_and_store(spot, db=db, client=client)
        return "ok", "derived"
    except Exception as exc:  # keep a compute failure from breaking the request
        db.rollback()
        return "fail", f"{type(exc).__name__}: {exc}"
    finally:
        db.close()


def process_queue(*, client, raw_dir: str | None = None, pause: float = 0.0) -> dict[str, int]:
    """Process every spot that has a queued ERA5 job (skips ones already derived).

    ``pause`` sleeps between spots (rate-limit friendly for the startup sweep)."""
    db = SessionLocal()
    try:
        spot_ids = [
            sid
            for (sid,) in db.execute(
                select(Era5Job.spot_id).where(Era5Job.status == "queued").distinct()
            ).all()
        ]
    finally:
        db.close()

    counts = {"ok": 0, "skip": 0, "fail": 0}
    for i, sid in enumerate(spot_ids):
        outcome, _ = process_one(sid, client=client, raw_dir=raw_dir)
        counts[outcome] = counts.get(outcome, 0) + 1
        if pause > 0 and outcome == "ok" and i < len(spot_ids) - 1:
            time.sleep(pause)
    return counts


def _resilient_client():
    from app.era5.openmeteo import OpenMeteoHistoryClient

    return OpenMeteoHistoryClient(http=batch.retrying_http(retries=3, timeout=60.0))


def run_queue_in_background(pause: float = 1.5) -> None:
    """Spawn a daemon thread that drains the ERA5 queue with a resilient client.

    Used at startup so pre-existing queued jobs get computed without any manual
    button — fully in the background.
    """

    def _work() -> None:
        try:
            process_queue(
                client=_resilient_client(),
                raw_dir=get_settings().era5_raw_dir,
                pause=pause,
            )
        except Exception as exc:  # never let the background sweep crash anything
            print(f"[era5] background queue error: {exc}")

    threading.Thread(target=_work, name="era5-queue", daemon=True).start()
