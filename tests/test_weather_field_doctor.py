from collections import namedtuple
from datetime import datetime, timezone
from types import SimpleNamespace

from app.spatial_fields.doctor import build_weather_field_doctor_report
from app.spatial_fields.storage import LocalFieldObjectStorage, MemoryFieldObjectStorage
from scripts import weather_field_doctor


NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
DiskUsage = namedtuple("DiskUsage", "total used free")


def _settings(**overrides):
    values = {
        "weather_field_pipeline_enabled": True,
        "weather_field_public_enabled": True,
        "wave_field_public_enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _health(*, status="ok", public=True, issues=None):
    return {
        "status": status,
        "public_enabled": public,
        "issues": list(issues or []),
    }


def test_doctor_escalates_field_failures_and_reports_spot_context_drift(monkeypatch):
    wind = _health()
    primary = _health(
        status="error",
        issues=[{"code": "active_manifest_missing", "severity": "error"}],
    )
    fallback = _health(
        status="degraded",
        issues=[{"code": "worker_jobs_failed", "severity": "warning", "count": 2}],
    )
    monkeypatch.setattr(
        "app.spatial_fields.doctor.weather_field_health",
        lambda *args, **kwargs: wind,
    )
    monkeypatch.setattr(
        "app.spatial_fields.doctor.wave_field_health",
        lambda *args, **kwargs: {
            "status": "error",
            "public_enabled": True,
            "primary": primary,
            "fallback": fallback,
            "extended": _health(),
        },
    )
    monkeypatch.setattr(
        "app.spatial_fields.doctor.load_plan",
        lambda *args, **kwargs: SimpleNamespace(
            due_spot_ids=("one", "two"),
            wave_context_changed_spot_ids=("two",),
            wave_context="context-1",
        ),
    )

    report = build_weather_field_doctor_report(
        object(),
        storage=MemoryFieldObjectStorage(),
        settings=_settings(),
        now=NOW,
        require_public=True,
    )

    alerts = {item["code"]: item for item in report["alerts"]}
    assert report["status"] == "error"
    assert alerts["active_manifest_missing"]["severity"] == "critical"
    assert alerts["worker_jobs_failed"]["severity"] == "warning"
    assert alerts["spot_wave_context_out_of_sync"]["count"] == 1
    assert report["spot_sync"] == {
        "status": "degraded",
        "due": 2,
        "wave_context_changed": 1,
        "wave_context": "context-1",
    }


def test_doctor_fails_closed_when_public_products_are_required(monkeypatch):
    disabled = _health(status="degraded", public=False)
    monkeypatch.setattr(
        "app.spatial_fields.doctor.weather_field_health",
        lambda *args, **kwargs: disabled,
    )
    monkeypatch.setattr(
        "app.spatial_fields.doctor.wave_field_health",
        lambda *args, **kwargs: {
            "status": "degraded",
            "public_enabled": False,
            "primary": disabled,
            "fallback": disabled,
            "extended": disabled,
        },
    )

    report = build_weather_field_doctor_report(
        object(),
        storage=MemoryFieldObjectStorage(),
        settings=_settings(
            weather_field_pipeline_enabled=False,
            weather_field_public_enabled=False,
            wave_field_public_enabled=False,
        ),
        now=NOW,
        require_public=True,
    )

    codes = {item["code"] for item in report["alerts"]}
    assert report["status"] == "error"
    assert {
        "weather_field_pipeline_disabled",
        "wind_field_public_disabled",
        "wave_field_public_disabled",
    } <= codes
    assert report["spot_sync"]["status"] == "not_applicable"


def test_doctor_warns_and_fails_for_local_storage_pressure(monkeypatch, tmp_path):
    healthy = _health()
    monkeypatch.setattr(
        "app.spatial_fields.doctor.weather_field_health",
        lambda *args, **kwargs: healthy,
    )
    monkeypatch.setattr(
        "app.spatial_fields.doctor.wave_field_health",
        lambda *args, **kwargs: {
            "status": "ok",
            "public_enabled": False,
            "primary": healthy,
            "fallback": healthy,
            "extended": healthy,
        },
    )
    storage = LocalFieldObjectStorage(tmp_path, public_base_url="/fields")
    settings = _settings(wave_field_public_enabled=False)

    warning = build_weather_field_doctor_report(
        object(),
        storage=storage,
        settings=settings,
        now=NOW,
        disk_usage=lambda _path: DiskUsage(100, 75, 25),
    )
    critical = build_weather_field_doctor_report(
        object(),
        storage=storage,
        settings=settings,
        now=NOW,
        disk_usage=lambda _path: DiskUsage(100, 85, 15),
    )

    assert warning["status"] == "degraded"
    assert warning["storage"]["used_percent"] == 75.0
    assert warning["alerts"][-1]["code"] == "weather_field_storage_warning"
    assert critical["status"] == "error"
    assert critical["alerts"][-1]["code"] == "weather_field_storage_critical"


def test_doctor_cli_returns_two_for_critical_alerts(monkeypatch, capsys):
    report = {
        "status": "error",
        "alerts": [{"code": "active_publication_stale", "severity": "critical"}],
    }

    class DBContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(weather_field_doctor, "SessionLocal", DBContext)
    monkeypatch.setattr(weather_field_doctor, "get_settings", lambda: object())
    monkeypatch.setattr(
        weather_field_doctor,
        "configured_field_storage",
        lambda: object(),
    )
    monkeypatch.setattr(
        weather_field_doctor,
        "build_weather_field_doctor_report",
        lambda *args, **kwargs: report,
    )

    exit_code = weather_field_doctor.main(
        ["--require-public", "--fail-on-alert"]
    )

    assert exit_code == 2
    assert '"active_publication_stale"' in capsys.readouterr().out
