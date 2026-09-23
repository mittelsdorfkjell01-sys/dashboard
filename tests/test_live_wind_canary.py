"""Lifecycle checks do not need a runner, network or database."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.weather.live_wind_canary import CanaryControl, run_canary_cycle
from app.config import Settings


NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)


def test_canary_configuration_forces_shadow_baseline_and_local_database():
    staging = "postgresql+psycopg://surf:surf@localhost:5432/surfwind_staging_test"
    with pytest.raises(ValueError, match="Canary requires"):
        Settings(database_url=staging, live_wind_canary_mode=True)
    with pytest.raises(ValueError, match="Canary requires"):
        Settings(database_url="postgresql+psycopg://surf:surf@db.example:5432/staging",
                 live_wind_canary_mode=True, live_wind_force_baseline=True)
    cfg = Settings(database_url=staging, live_wind_canary_mode=True,
                   live_wind_rollout_stage="shadow",
                   live_wind_force_baseline=True)
    assert cfg.live_wind_rollout_stage == "shadow"


def test_canary_pause_resume_stop_preserve_control_and_do_not_reopen(tmp_path):
    evidence = tmp_path / "immutable-evidence-placeholder"
    evidence.write_text("preserve", encoding="utf-8")
    control = CanaryControl(tmp_path)
    started = control.start(run_id="run-a", runner_id="runner-a",
                            cache_id="cache-a", now=NOW)
    assert started["status"] == "running"
    assert control.transition("pause", run_id="run-a", now=NOW)["status"] == "paused"
    with pytest.raises(ValueError, match="canary_not_running"):
        control.assert_running(run_id="run-a")
    assert control.transition("resume", run_id="run-a", now=NOW)["status"] == "running"
    control.record_cycle(run_id="run-a", success=True, metrics={"shadow_jobs": 2},
                         now=NOW + timedelta(minutes=10))
    stopped = control.transition("stop", run_id="run-a", now=NOW + timedelta(minutes=11))
    assert stopped["status"] == "stopped"
    assert control.record_cycle(run_id="run-a", success=True,
                                now=NOW + timedelta(hours=73))["status"] == "stopped"
    assert control.read()["cycle_count"] == 1
    assert evidence.read_text(encoding="utf-8") == "preserve"
    with pytest.raises(ValueError, match="canary_transition_invalid"):
        control.transition("resume", run_id="run-a")


def test_canary_failure_is_paused_until_explicit_resume(tmp_path):
    control = CanaryControl(tmp_path)
    control.start(run_id="run-b", runner_id="runner-a", cache_id="cache-a", now=NOW)
    failed = control.record_cycle(run_id="run-b", success=False,
                                  error="leakage_audit_failed", now=NOW + timedelta(minutes=1))
    assert failed["status"] == "failed"
    assert failed["failed_cycle_count"] == 1
    with pytest.raises(ValueError, match="canary_not_running"):
        control.assert_running(run_id="run-b")
    assert control.transition("resume", run_id="run-b")["status"] == "running"


def test_canary_state_is_not_replaced_or_restarted(tmp_path):
    control = CanaryControl(tmp_path)
    control.start(run_id="run-a", runner_id="runner-a", cache_id="cache-a", now=NOW)
    with pytest.raises(ValueError, match="canary_state_already_exists"):
        control.start(run_id="run-b", runner_id="runner-a", cache_id="cache-a")
    with pytest.raises(ValueError, match="canary_run_identity_mismatch"):
        control.transition("stop", run_id="run-b")


def test_72_hour_label_requires_continuous_successful_cycles(tmp_path):
    control = CanaryControl(tmp_path)
    control.start(run_id="run-c", runner_id="runner-a", cache_id="cache-a", now=NOW)
    discontinuous = control.record_cycle(
        run_id="run-c", success=True, now=NOW + timedelta(hours=73),
        maximum_gap_minutes=45)
    assert discontinuous["status"] == "failed"
    assert discontinuous["last_error"] == "canary_cycle_gap_exceeded"
    assert discontinuous["continuity_broken"] is True
    control.transition("resume", run_id="run-c", now=NOW + timedelta(hours=73))
    later = control.record_cycle(run_id="run-c", success=True,
                                 now=NOW + timedelta(hours=73, minutes=10))
    assert later["status"] == "failed"
    assert later["last_error"] == "canary_continuity_not_accepted"


def test_interrupted_cycle_requires_manual_recovery(tmp_path):
    control = CanaryControl(tmp_path)
    control.start(run_id="run-restart", runner_id="runner-a",
                  cache_id="cache-a", now=NOW)
    control.begin_cycle(run_id="run-restart", now=NOW)
    with pytest.raises(ValueError, match="previous_cycle_interrupted"):
        control.begin_cycle(run_id="run-restart", now=NOW + timedelta(minutes=10))
    state = control.read()
    assert state["status"] == "failed"
    assert state["process_restart_count"] == 1


def test_cooperative_pause_keeps_jobs_and_does_not_count_failure(tmp_path):
    control = CanaryControl(tmp_path)
    control.start(run_id="run-pause", runner_id="runner-a",
                  cache_id="cache-a", now=NOW)
    control.begin_cycle(run_id="run-pause", now=NOW)
    control.transition("pause", run_id="run-pause", now=NOW)
    state = control.abandon_cycle(run_id="run-pause", now=NOW)
    assert state["status"] == "paused"
    assert state["cycle_in_progress"] is False
    assert state["failed_cycle_count"] == 0


def test_stop_kill_switch_does_not_require_database_or_valid_settings(
    tmp_path, monkeypatch, capsys,
):
    from scripts import live_wind_canary as cli
    import sys

    control = CanaryControl(tmp_path)
    control.start(run_id="run-stop", runner_id="runner-a",
                  cache_id="cache-a", now=NOW)
    monkeypatch.setenv("LIVE_WIND_EXACT_RUN_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("LIVE_WIND_CANARY_ID", "run-stop")
    monkeypatch.setattr(cli.os.path, "ismount", lambda _path: True)
    monkeypatch.setattr(cli, "get_settings", lambda: (_ for _ in ()).throw(
        AssertionError("settings must not be read")))
    monkeypatch.setattr(sys, "argv", ["live_wind_canary", "canary-stop"])
    cli.main()
    assert control.read()["status"] == "stopped"
    assert '"status": "stopped"' in capsys.readouterr().out


def test_cycle_orders_existing_workers_and_never_touches_forecast(tmp_path, monkeypatch):
    from app.db import session
    from app.weather import exact_run, live_wind_holdouts, live_wind_jobs
    from app.weather import live_wind_operations, model_error, observation_worker
    from scripts import exact_run_worker

    calls = []

    class Db:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def scalar(self, _query):
            from app.db.schema import EXPECTED_DB_REVISION

            return EXPECTED_DB_REVISION

    monkeypatch.setattr(session, "SessionLocal", Db)
    monkeypatch.setattr(exact_run, "ExactRunAssetCache", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(exact_run, "ExactRunLoader", lambda *_args: object())
    monkeypatch.setattr(exact_run, "exact_cache_preflight", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(exact_run_worker, "capture_exact_cycle",
                        lambda *_args, **_kwargs: calls.append("capture") or {"assets": 1})
    monkeypatch.setattr(observation_worker, "run_observation_import",
                        lambda *_args, **_kwargs: calls.append("observations") or {"persisted": 1})
    monkeypatch.setattr(model_error, "run_station_model_error_analysis",
                        lambda *_args, **_kwargs: calls.append("residuals") or {"persisted": 1})
    monkeypatch.setattr(live_wind_jobs, "enqueue_live_wind_cycle",
                        lambda *_args, **_kwargs: calls.append("enqueue") or {"enqueued": 1})
    monkeypatch.setattr(live_wind_jobs, "run_live_wind_worker",
                        lambda *_args, **_kwargs: calls.append("shadow") or {"succeeded": 1})
    monkeypatch.setattr(live_wind_holdouts, "build_live_wind_holdout_cases",
                        lambda *_args, **_kwargs: calls.append("holdouts") or {"inserted": 1})
    monkeypatch.setattr(live_wind_operations, "build_live_wind_operations_report",
                        lambda *_args, **_kwargs: calls.append("operations") or {
                            "product_boundary_audit": {"ok": True},
                            "doctors": {"providers": {"alerts": []},
                                        "scheduler": {"alerts": []}},
                        })
    settings = SimpleNamespace(
        live_wind_exact_run_cache_dir=str(tmp_path),
        live_wind_exact_run_cache_id="cache-a",
        live_wind_exact_run_min_free_bytes=0,
        live_wind_exact_capture_tile_limit=1,
        weather_observation_cron_batch_size=1,
        live_wind_worker_batch_size=1,
        live_wind_candidate_version="candidate-a",
        live_wind_job_late_minutes=45,
    )
    control = CanaryControl(tmp_path)
    control.start(run_id="run-d", runner_id="runner-a", cache_id="cache-a", now=NOW)
    result = run_canary_cycle(control, run_id="run-d", settings=settings,
                              now=NOW + timedelta(minutes=1))
    assert result["status"] == "succeeded"
    assert calls == ["capture", "observations", "residuals", "enqueue",
                     "shadow", "holdouts", "operations"]
    assert control.read()["cycle_count"] == 1
    monkeypatch.setattr(live_wind_operations, "build_live_wind_operations_report",
                        lambda *_args, **_kwargs: {
                            "product_boundary_audit": {"ok": False},
                            "doctors": {"providers": {"alerts": []}},
                        })
    with pytest.raises(RuntimeError, match="canary_product_boundary_failed"):
        run_canary_cycle(control, run_id="run-d", settings=settings,
                         now=NOW + timedelta(minutes=2))
    assert control.read()["status"] == "failed"
