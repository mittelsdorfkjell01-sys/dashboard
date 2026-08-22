"""Queue and drain wind climatology for the complete published catalogue."""

from __future__ import annotations

import json
import time

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import WindClimatologyRun
from app.wind_climatology.service import backfill, process


def _process_pending() -> tuple[int, int, int]:
    with SessionLocal() as db:
        queued = backfill(db, limit=None)
        pending_ids = list(db.scalars(select(WindClimatologyRun.id).where(WindClimatologyRun.status == "pending").order_by(WindClimatologyRun.created_at)))
    ready = 0
    failed = 0
    for run_id in pending_ids:
        with SessionLocal() as db:
            run = process(db, run_id)
            if run.status == "ready":
                ready += 1
            else:
                failed += 1

    return len(queued), ready, failed


def main() -> dict:
    queued_total = ready_total = failed = 0
    attempts = 0
    for attempts in range(1, 4):
        queued, ready, failed = _process_pending()
        queued_total += queued
        ready_total += ready
        if failed == 0:
            break
        # The archive provider may temporarily throttle a catalogue-wide run.
        # Completed spots are idempotently skipped on the next pass.
        time.sleep(60)

    result = {
        "status": "complete" if failed == 0 else "complete_with_failures",
        "attempts": attempts,
        "newly_queued": queued_total,
        "processed": ready_total + failed,
        "ready": ready_total,
        "failed": failed,
    }
    print(json.dumps(result))
    if failed:
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    main()
