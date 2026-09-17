"""Operator-only 72-hour staging canary control (never a public rollout)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys

from app.config import get_settings
from app.weather.live_wind_canary import CanaryControl, run_canary_cycle
from scripts.exact_run_preflight import run_preflight


def _preflight(checksum: str) -> dict:
    result = run_preflight(canary=True, persistence_mode="verify",
                           expected_probe_sha256=checksum)
    if result["status"] != "ready":
        raise ValueError("canary_preflight_failed:" + ",".join(result["errors"]))
    return result


def _run_bounded_cycle(control: CanaryControl, run_id: str, cfg) -> dict:
    def timed_out(_signum, _frame):
        raise TimeoutError("canary_cycle_900_second_limit")

    previous = signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(900)
    try:
        return run_canary_cycle(control, run_id=run_id, settings=cfg)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=(
        "preflight", "migrate-check", "canary-start", "canary-status",
        "canary-pause", "canary-resume", "canary-stop", "canary-dry-run",
        "canary-cycle", "canary-report", "canary-retry",
    ))
    parser.add_argument("--expected-probe-sha256")
    args = parser.parse_args()
    command = args.command
    if command in {"canary-status", "canary-pause", "canary-stop"}:
        cache_root = os.environ.get("LIVE_WIND_EXACT_RUN_CACHE_DIR", "").strip()
        if not cache_root or not Path(cache_root).is_absolute():
            raise SystemExit("absolute_cache_root_required_for_kill_switch")
        if not Path(cache_root).is_dir() or (
            sys.platform.startswith("linux") and not os.path.ismount(cache_root)
        ):
            raise SystemExit("canary_cache_mount_unavailable_workers_fail_closed")
        control = CanaryControl(cache_root)
        if command == "canary-status":
            state = control.read()
            result = {"status": "canary_not_started" if state is None else state["status"],
                      "canary": state}
        else:
            run_id = os.environ.get("LIVE_WIND_CANARY_ID", "").strip()
            if not run_id:
                raise SystemExit("LIVE_WIND_CANARY_ID_required")
            result = control.transition(
                "pause" if command == "canary-pause" else "stop", run_id=run_id)
        print(json.dumps(result, sort_keys=True, default=str))
        return
    cfg = get_settings()
    checksum = args.expected_probe_sha256 or os.environ.get("LIVE_WIND_CANARY_PROBE_SHA256")
    if command in {"preflight", "migrate-check", "canary-dry-run", "canary-start",
                   "canary-resume", "canary-cycle", "canary-retry"} and not checksum:
        raise SystemExit("expected_probe_sha256_required")
    if command in {"preflight", "migrate-check", "canary-dry-run", "canary-start",
                   "canary-resume", "canary-cycle", "canary-retry"}:
        proof = _preflight(checksum)
    else:
        proof = None
    if command in {"preflight", "migrate-check", "canary-dry-run"}:
        print(json.dumps({"status": "ready", "mode": command,
                          "canary_started": False,
                          "migration_head": proof["checks"]["migration_head"],
                          "cache": proof["checks"]["cache"],
                          "persistence": proof["checks"]["persistence"]},
                         sort_keys=True, default=str))
        return
    if not cfg.live_wind_canary_mode or not cfg.live_wind_exact_run_cache_dir:
        raise SystemExit("canary_mode_and_cache_required")
    control = CanaryControl(cfg.live_wind_exact_run_cache_dir)
    run_id = os.environ.get("LIVE_WIND_CANARY_ID", "").strip()
    if command == "canary-report":
        from app.db.session import SessionLocal
        from app.weather.live_wind_operations import build_live_wind_operations_report

        with SessionLocal() as db:
            operations = build_live_wind_operations_report(db, include_rasters=False,
                                                            settings=cfg)
        print(json.dumps({"canary": control.read(), "operations": operations},
                         sort_keys=True, default=str))
        return
    if not run_id:
        raise SystemExit("LIVE_WIND_CANARY_ID_required")
    if command == "canary-start":
        if not sys.platform.startswith("linux"):
            raise SystemExit("canary_requires_linux")
        control.start(run_id=run_id,
                      runner_id=os.environ["LIVE_WIND_CANARY_RUNNER_ID"],
                      cache_id=cfg.live_wind_exact_run_cache_id)
        result = _run_bounded_cycle(control, run_id, cfg)
    elif command == "canary-resume":
        result = control.transition("resume", run_id=run_id)
    elif command == "canary-cycle":
        result = _run_bounded_cycle(control, run_id, cfg)
    elif command == "canary-retry":
        state = control.read()
        if not state or state["run_id"] != run_id or state["status"] != "failed":
            raise SystemExit("canary_retry_requires_failed_run")
        if not str(state.get("last_error") or "").startswith((
            "ConnectionError:", "TimeoutError:", "OperationalError:",
        )):
            raise SystemExit("canary_retry_requires_manual_review_and_resume")
        failed_at = datetime.fromisoformat(state["updated_at"])
        if (datetime.now(timezone.utc) - failed_at).total_seconds() > cfg.live_wind_cycle_minutes * 60:
            raise SystemExit("historical_window_retry_forbidden")
        control.transition("resume", run_id=run_id)
        result = _run_bounded_cycle(control, run_id, cfg)
    else:
        raise AssertionError(command)
    print(json.dumps(result, sort_keys=True, default=str))
    if result.get("status") == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        detail = str(exc)
        safe_detail = detail if detail.startswith((
            "canary_", "previous_cycle_interrupted", "historical_window_",
        )) else "internal_error"
        print(json.dumps({"status": "failed",
                          "reason": f"{type(exc).__name__}:{safe_detail}"}, sort_keys=True))
        raise SystemExit(1) from exc
