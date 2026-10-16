"""Process durable weather-field jobs once or as a dedicated worker loop."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import SessionLocal
from app.spatial_fields.doctor import storage_capacity_report
from app.spatial_fields.jobs import run_worker_batch
from app.spatial_fields.storage import configured_field_storage


def run_once(settings) -> dict:
    if not settings.weather_field_pipeline_enabled:
        return {"status": "skipped", "reason": "weather_field_pipeline_disabled"}
    storage = configured_field_storage()
    storage_report, storage_alerts = storage_capacity_report(storage)
    storage_critical = storage_report["status"] == "error"
    with SessionLocal() as db:
        jobs = run_worker_batch(
            db,
            settings=settings,
            storage=storage,
            allowed_kinds=("retention",) if storage_critical else None,
            recover_stalled=not storage_critical,
        )
    if storage_critical:
        return {
            "status": "blocked",
            "reason": "weather_field_storage_critical",
            "storage": storage_report,
            "alerts": storage_alerts,
            "processed": len(jobs),
            "jobs": jobs,
        }
    return {
        "status": "failed" if any(job["status"] == "failed" for job in jobs) else "ok",
        "processed": len(jobs),
        "jobs": jobs,
    }


def run_loop(settings, *, stop_event: threading.Event) -> int:
    while not stop_event.is_set():
        result = run_once(settings)
        print(json.dumps(result, sort_keys=True), flush=True)
        if result["status"] in {"skipped", "blocked"} and result.get("processed", 0) == 0:
            stop_event.wait(settings.weather_field_worker_poll_seconds)
            continue
        # Drain an existing backlog without an artificial pause. When no due
        # job remains, block interruptibly until the next poll.
        if result["processed"] == 0:
            stop_event.wait(settings.weather_field_worker_poll_seconds)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not args.loop:
        result = run_once(settings)
        print(json.dumps(result, sort_keys=True))
        if result["status"] == "failed":
            return 1
        return 2 if result["status"] == "blocked" else 0

    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop_event.set())
    signal.signal(signal.SIGINT, lambda _signum, _frame: stop_event.set())
    return run_loop(settings, stop_event=stop_event)


if __name__ == "__main__":
    raise SystemExit(main())
