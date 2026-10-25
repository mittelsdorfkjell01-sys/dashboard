from types import SimpleNamespace

from app.maintenance.worker import _tasks
from app.maintenance import worker as maintenance_worker
from scripts import weather_field_worker


def test_weather_fields_use_a_dedicated_worker_and_three_hour_discovery(monkeypatch) -> None:
    settings = SimpleNamespace(
        weather_field_discovery_interval_seconds=10_800,
        forecast_refresh_interval_seconds=1_800,
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)

    tasks = _tasks(100.0)
    by_name = {task.name: task for task in tasks}

    assert by_name["weather-fields-enqueue"].interval == 10_800
    assert by_name["weather-fields-health"].interval == 900
    assert by_name["recommendation-warmup"].interval == 600
    assert "weather-fields-worker" not in by_name


def test_dedicated_worker_drains_backlog_before_waiting(monkeypatch, capsys) -> None:
    results = iter(
        (
            {"status": "ok", "processed": 1, "jobs": [{"job_id": "one"}]},
            {"status": "ok", "processed": 0, "jobs": []},
        )
    )
    monkeypatch.setattr(weather_field_worker, "run_once", lambda _settings: next(results))

    class StopAfterWait:
        stopped = False
        waits: list[int] = []

        def is_set(self) -> bool:
            return self.stopped

        def wait(self, seconds: int) -> None:
            self.waits.append(seconds)
            self.stopped = True

    stop = StopAfterWait()
    result = weather_field_worker.run_loop(
        SimpleNamespace(weather_field_worker_poll_seconds=30),
        stop_event=stop,  # type: ignore[arg-type]
    )

    assert result == 0
    assert stop.waits == [30]
    assert len(capsys.readouterr().out.strip().splitlines()) == 2


def test_dedicated_worker_only_runs_retention_when_storage_is_critical(
    monkeypatch,
) -> None:
    settings = SimpleNamespace(weather_field_pipeline_enabled=True)
    storage = object()
    calls = []

    class DBContext:
        def __enter__(self):
            return "db"

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(weather_field_worker, "SessionLocal", DBContext)
    monkeypatch.setattr(
        weather_field_worker, "configured_field_storage", lambda: storage
    )
    monkeypatch.setattr(
        weather_field_worker,
        "storage_capacity_report",
        lambda _storage: (
            {"status": "error", "used_percent": 91.0},
            [{"code": "weather_field_storage_critical", "severity": "critical"}],
        ),
    )

    def run_batch(db, **kwargs):
        calls.append((db, kwargs))
        return [{"job_id": "retention", "kind": "retention", "status": "succeeded"}]

    monkeypatch.setattr(weather_field_worker, "run_worker_batch", run_batch)

    result = weather_field_worker.run_once(settings)

    assert result["status"] == "blocked"
    assert result["reason"] == "weather_field_storage_critical"
    assert result["processed"] == 1
    assert calls == [
        (
            "db",
            {
                "settings": settings,
                "storage": storage,
                "allowed_kinds": ("retention",),
                "recover_stalled": False,
            },
        )
    ]


def test_dedicated_worker_runs_normal_batch_when_storage_is_healthy(
    monkeypatch,
) -> None:
    settings = SimpleNamespace(weather_field_pipeline_enabled=True)
    storage = object()
    calls = []

    class DBContext:
        def __enter__(self):
            return "db"

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(weather_field_worker, "SessionLocal", DBContext)
    monkeypatch.setattr(
        weather_field_worker, "configured_field_storage", lambda: storage
    )
    monkeypatch.setattr(
        weather_field_worker,
        "storage_capacity_report",
        lambda _storage: ({"status": "ok", "used_percent": 40.0}, []),
    )

    def run_batch(db, **kwargs):
        calls.append((db, kwargs))
        return []

    monkeypatch.setattr(weather_field_worker, "run_worker_batch", run_batch)

    result = weather_field_worker.run_once(settings)

    assert result == {"status": "ok", "processed": 0, "jobs": []}
    assert calls == [
        (
            "db",
            {
                "settings": settings,
                "storage": storage,
                "allowed_kinds": None,
                "recover_stalled": True,
            },
        )
    ]


def test_maintenance_health_task_emits_structured_doctor_alert(monkeypatch) -> None:
    report = {
        "status": "error",
        "wind": {"status": "ok"},
        "waves": {"status": "error"},
        "spot_sync": {"status": "degraded"},
        "alerts": [
            {"code": "active_publication_stale", "severity": "critical"},
            {"code": "spot_wave_context_out_of_sync", "severity": "warning"},
        ],
    }
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "app.spatial_fields.storage.configured_field_storage",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.spatial_fields.doctor.build_weather_field_doctor_report",
        lambda *args, **kwargs: report,
    )

    class DBContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(maintenance_worker, "SessionLocal", DBContext)
    logged = []
    monkeypatch.setattr(
        maintenance_worker.logger,
        "error",
        lambda message, **kwargs: logged.append((message, kwargs["extra"])),
    )

    result = maintenance_worker._weather_field_health_monitor()

    assert result == {
        "status": "error",
        "wind": "ok",
        "waves": "error",
        "spot_sync": "degraded",
        "alerts": 2,
    }
    assert logged[0][1]["weather_event"] == "weather_field_doctor"
    assert logged[0][1]["weather_alert_codes"] == [
        "active_publication_stale",
        "spot_wave_context_out_of_sync",
    ]
