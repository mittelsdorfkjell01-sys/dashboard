"""Local, persistent control plane for a shadow-only LiveWind canary.

The run identifier is operational metadata only; it never enters model or
holdout identities. Control state lives on the verified exact-run mount.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import time
import uuid

from sqlalchemy import text


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def _exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("canary_lock_symlink")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "a+b") as handle:
        if os.name != "nt" and os.fstat(handle.fileno()).st_mode & stat.S_IWOTH:
            raise ValueError("canary_lock_world_writable")
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


class CanaryControl:
    """Atomic lifecycle transitions without deleting jobs, evidence or assets."""

    def __init__(self, cache_root: str | Path):
        self.root = Path(cache_root).resolve()
        self.state_path = self.root / ".live-wind-canary-state.json"
        self.state_lock = self.root / ".live-wind-canary-state.lock"
        self.cycle_lock = self.root / ".live-wind-canary-cycle.lock"

    def _read_unlocked(self) -> dict | None:
        if self.state_path.is_symlink():
            raise ValueError("canary_state_symlink")
        if not self.state_path.exists():
            return None
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        if state.get("schema") != 1 or state.get("status") not in {
            "running", "paused", "failed", "stopped", "completed"
        }:
            raise ValueError("canary_state_invalid")
        return state

    def read(self) -> dict | None:
        with _exclusive_lock(self.state_lock):
            return self._read_unlocked()

    def _write_unlocked(self, state: dict) -> dict:
        temporary = self.root / f".live-wind-canary-{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as stream:
                os.chmod(temporary, 0o600)
                stream.write(json.dumps(state, sort_keys=True).encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_path)
            if os.name != "nt":
                descriptor = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
        return state

    def start(self, *, run_id: str, runner_id: str, cache_id: str,
              now: datetime | None = None) -> dict:
        if not run_id or not runner_id or not cache_id:
            raise ValueError("canary_identity_required")
        instant = now or _utc_now()
        with _exclusive_lock(self.state_lock):
            previous = self._read_unlocked()
            if previous is not None:
                raise ValueError("canary_state_already_exists")
            state = {
                "schema": 1, "run_id": run_id, "runner_id": runner_id,
                "cache_id": cache_id, "status": "running",
                "started_at": instant.isoformat(),
                "deadline_at": (instant + timedelta(hours=72)).isoformat(),
                "last_successful_cycle_at": None, "cycle_count": 0,
                "failed_cycle_count": 0, "process_restart_count": 0,
                "cycle_in_progress": False, "continuity_broken": False,
                "last_error": None,
                "updated_at": instant.isoformat(),
            }
            return self._write_unlocked(state)

    def transition(self, action: str, *, run_id: str,
                   now: datetime | None = None) -> dict:
        target = {"pause": "paused", "resume": "running", "stop": "stopped"}.get(action)
        if target is None:
            raise ValueError("canary_action_invalid")
        with _exclusive_lock(self.state_lock):
            state = self._read_unlocked()
            if state is None or state["run_id"] != run_id:
                raise ValueError("canary_run_identity_mismatch")
            allowed = {"pause": {"running", "failed"},
                       "resume": {"paused", "failed"},
                       "stop": {"running", "paused", "failed"}}
            if state["status"] not in allowed[action]:
                raise ValueError("canary_transition_invalid")
            state = {**state, "status": target,
                     "updated_at": (now or _utc_now()).isoformat()}
            return self._write_unlocked(state)

    def assert_running(self, *, run_id: str) -> dict:
        state = self.read()
        if state is None or state["run_id"] != run_id:
            raise ValueError("canary_run_identity_mismatch")
        if state["status"] != "running":
            raise ValueError(f"canary_not_running:{state['status']}")
        return state

    def begin_cycle(self, *, run_id: str, now: datetime | None = None) -> dict:
        with _exclusive_lock(self.state_lock):
            state = self._read_unlocked()
            if state is None or state["run_id"] != run_id:
                raise ValueError("canary_run_identity_mismatch")
            if state["status"] != "running":
                raise ValueError(f"canary_not_running:{state['status']}")
            if state.get("cycle_in_progress"):
                state["status"] = "failed"
                state["continuity_broken"] = True
                state["process_restart_count"] += 1
                state["last_error"] = "previous_cycle_interrupted"
                state["updated_at"] = (now or _utc_now()).isoformat()
                self._write_unlocked(state)
                raise ValueError("previous_cycle_interrupted")
            state["cycle_in_progress"] = True
            state["cycle_started_at"] = (now or _utc_now()).isoformat()
            state["updated_at"] = state["cycle_started_at"]
            return self._write_unlocked(state)

    def record_cycle(self, *, run_id: str, success: bool,
                     error: str | None = None, metrics: dict | None = None,
                     now: datetime | None = None,
                     maximum_gap_minutes: int = 45) -> dict:
        instant = now or _utc_now()
        with _exclusive_lock(self.state_lock):
            state = self._read_unlocked()
            if state is None or state["run_id"] != run_id:
                raise ValueError("canary_run_identity_mismatch")
            if state["status"] == "stopped":
                state["cycle_in_progress"] = False
                state["updated_at"] = instant.isoformat()
                return self._write_unlocked(state)  # Never reopen a stopped run.
            state["cycle_in_progress"] = False
            if success:
                reference = datetime.fromisoformat(
                    state["last_successful_cycle_at"] or state["started_at"])
                if instant - reference > timedelta(minutes=maximum_gap_minutes):
                    state["status"] = "failed"
                    state["continuity_broken"] = True
                    state["last_error"] = "canary_cycle_gap_exceeded"
                state["cycle_count"] += 1
                state["last_successful_cycle_at"] = instant.isoformat()
                state["last_cycle_metrics"] = metrics or {}
                if (state["status"] == "running"
                        and not state["continuity_broken"]
                        and instant >= datetime.fromisoformat(state["deadline_at"])):
                    state["status"] = "completed"
                elif (state["status"] == "running" and state["continuity_broken"]
                      and instant >= datetime.fromisoformat(state["deadline_at"])):
                    state["status"] = "failed"
                    state["last_error"] = "canary_continuity_not_accepted"
            else:
                state["failed_cycle_count"] += 1
                state["status"] = "failed"
                state["continuity_broken"] = True
                state["last_error"] = error or "cycle_failed"
            state["updated_at"] = instant.isoformat()
            return self._write_unlocked(state)

    def abandon_cycle(self, *, run_id: str, now: datetime | None = None) -> dict:
        """Finish a cooperative pause/stop without counting a failed cycle."""
        with _exclusive_lock(self.state_lock):
            state = self._read_unlocked()
            if state is None or state["run_id"] != run_id:
                raise ValueError("canary_run_identity_mismatch")
            if state["status"] not in {"paused", "stopped"}:
                raise ValueError("canary_abandon_requires_pause_or_stop")
            state["cycle_in_progress"] = False
            state["updated_at"] = (now or _utc_now()).isoformat()
            return self._write_unlocked(state)

    @contextmanager
    def exclusive_cycle(self):
        with _exclusive_lock(self.cycle_lock):
            yield


def run_canary_cycle(control: CanaryControl, *, run_id: str,
                     settings, now: datetime | None = None) -> dict:
    """Execute one bounded, strictly ordered cycle using existing workers."""
    from app.db.session import SessionLocal
    from app.weather.exact_run import ExactRunAssetCache, ExactRunLoader, exact_cache_preflight
    from app.weather.live_wind_holdouts import build_live_wind_holdout_cases
    from app.weather.live_wind_jobs import enqueue_live_wind_cycle, run_live_wind_worker
    from app.weather.live_wind_operations import build_live_wind_operations_report
    from app.weather.model_error import run_station_model_error_analysis
    from app.weather.observation_worker import run_observation_import
    from scripts.exact_run_worker import capture_exact_cycle

    started = time.monotonic()
    instant = now or _utc_now()
    with control.exclusive_cycle():
        control.begin_cycle(run_id=run_id, now=now)
        outcomes: dict = {}
        try:
            loader = ExactRunLoader(ExactRunAssetCache(
                settings.live_wind_exact_run_cache_dir, require_persistent=True,
                expected_id=settings.live_wind_exact_run_cache_id,
                minimum_free_bytes=settings.live_wind_exact_run_min_free_bytes,
            ))
            with SessionLocal() as db:
                stages = (
                    ("capture", lambda: capture_exact_cycle(
                        db, loader, now=instant,
                        limit=settings.live_wind_exact_capture_tile_limit)),
                    ("observations", lambda: run_observation_import(
                        db, limit=settings.weather_observation_cron_batch_size,
                        dry_run=False)),
                    ("residuals", lambda: run_station_model_error_analysis(
                        db, loader, limit=settings.weather_observation_cron_batch_size,
                        dry_run=False, recent_hours=48,
                        skip_exact_attempted=True, require_exact=True)),
                    ("enqueue", lambda: enqueue_live_wind_cycle(db, settings=settings)),
                    ("shadow", lambda: run_live_wind_worker(
                        db, limit=settings.live_wind_worker_batch_size,
                        settings=settings)),
                    ("holdouts", lambda: build_live_wind_holdout_cases(
                        db, loader, candidate_version=settings.live_wind_candidate_version,
                        limit=25)),
                    ("operations", lambda: build_live_wind_operations_report(
                        db, include_rasters=False, settings=settings)),
                )
                for name, operation in stages:
                    control.assert_running(run_id=run_id)
                    if db.scalar(text("SELECT version_num FROM alembic_version")) != "0059_live_wind_holdout_cases":
                        raise RuntimeError("canary_schema_drift")
                    exact_cache_preflight(
                        settings.live_wind_exact_run_cache_dir,
                        expected_id=settings.live_wind_exact_run_cache_id,
                        require_persistent=True,
                        minimum_free_bytes=settings.live_wind_exact_run_min_free_bytes,
                    )
                    result = operation()
                    outcomes[name] = result
                    if result.get("error") or result.get("status") == "failed":
                        raise RuntimeError(f"canary_stage_failed:{name}")
                    if name == "capture" and result.get("status") == "no_locations":
                        raise RuntimeError("canary_no_capture_locations")
                    if name == "shadow" and (result.get("failed") or result.get("lease_lost")):
                        raise RuntimeError("canary_shadow_jobs_failed")
                    if name == "holdouts" and result.get("errors"):
                        raise RuntimeError("canary_holdout_audit_failed")
                    if name == "operations":
                        if not result["product_boundary_audit"]["ok"]:
                            raise RuntimeError("canary_product_boundary_failed")
                        if any(alert.get("severity") == "critical"
                               for doctor in result["doctors"].values()
                               for alert in doctor.get("alerts", [])):
                            raise RuntimeError("canary_doctor_critical")
            summary = {"capture_assets": outcomes["capture"].get("assets", 0),
                       "capture_errors": outcomes["capture"].get("errors", {}),
                       "station_imports": outcomes["observations"].get("persisted", 0),
                       "residuals": outcomes["residuals"].get("persisted", 0),
                       "shadow_jobs": outcomes["shadow"].get("succeeded", 0),
                       "holdout_cases": outcomes["holdouts"].get("inserted", 0),
                       "duration_seconds": round(time.monotonic() - started, 2)}
            state = control.record_cycle(
                run_id=run_id, success=True, metrics=summary,
                maximum_gap_minutes=settings.live_wind_job_late_minutes,
                now=now)
            if state["status"] == "failed":
                return {"status": "failed", "run_id": run_id,
                        "reason": state["last_error"], "summary": summary}
            return {"status": "succeeded", "run_id": run_id, "summary": summary}
        except Exception as exc:
            if isinstance(exc, ValueError) and str(exc) in {
                "canary_not_running:paused", "canary_not_running:stopped"
            }:
                control.abandon_cycle(run_id=run_id, now=now)
                return {"status": "paused_or_stopped", "run_id": run_id}
            detail = str(exc)
            safe_detail = detail if detail.startswith("canary_") else "stage_exception"
            control.record_cycle(run_id=run_id, success=False,
                                 error=f"{type(exc).__name__}:{safe_detail}", now=now)
            raise
