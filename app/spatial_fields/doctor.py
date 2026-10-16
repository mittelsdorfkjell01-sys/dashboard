"""Operational doctor for the self-hosted weather-field data plane."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from app.forecast.refresh_worker import load_plan
from app.spatial_fields.monitoring import (
    WIND_FIELD_MODELS,
    wave_field_health,
    weather_field_health,
)


DISK_WARNING_PERCENT = 70.0
DISK_CRITICAL_PERCENT = 80.0


def _alert(
    code: str,
    severity: str,
    component: str,
    **details,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "component": component,
        **details,
    }


def _health_alerts(
    health: dict,
    *,
    component: str,
    require_public: bool,
) -> list[dict]:
    alerts = []
    public_required = require_public and bool(health.get("public_enabled"))
    for issue in health.get("issues", []):
        severity = "critical" if issue.get("severity") == "error" else "warning"
        if issue.get("code") == "no_active_publication" and public_required:
            severity = "critical"
        alerts.append(
            _alert(
                str(issue.get("code", "unknown_health_issue")),
                severity,
                component,
                details={
                    key: value
                    for key, value in issue.items()
                    if key not in {"code", "severity"}
                },
            )
        )
    return alerts


def _existing_storage_path(root: str | Path) -> Path:
    candidate = Path(root).resolve()
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def storage_capacity_report(
    storage, *, disk_usage=shutil.disk_usage
) -> tuple[dict, list[dict]]:
    """Report local field-storage pressure for monitoring and worker admission."""
    root = getattr(storage, "root", None)
    if root is None:
        return {"status": "not_applicable", "backend": type(storage).__name__}, []
    checked_path = _existing_storage_path(root)
    usage = disk_usage(checked_path)
    used_percent = round((usage.used / usage.total) * 100.0, 1) if usage.total else 100.0
    report = {
        "status": "ok",
        "path": str(Path(root)),
        "checked_path": str(checked_path),
        "total_bytes": int(usage.total),
        "used_bytes": int(usage.used),
        "free_bytes": int(usage.free),
        "used_percent": used_percent,
        "warning_percent": DISK_WARNING_PERCENT,
        "critical_percent": DISK_CRITICAL_PERCENT,
    }
    alerts = []
    if used_percent >= DISK_CRITICAL_PERCENT:
        report["status"] = "error"
        alerts.append(
            _alert(
                "weather_field_storage_critical",
                "critical",
                "storage",
                used_percent=used_percent,
            )
        )
    elif used_percent >= DISK_WARNING_PERCENT:
        report["status"] = "degraded"
        alerts.append(
            _alert(
                "weather_field_storage_warning",
                "warning",
                "storage",
                used_percent=used_percent,
            )
        )
    return report, alerts


def build_weather_field_doctor_report(
    db,
    *,
    storage,
    settings,
    now: datetime | None = None,
    require_public: bool = False,
    disk_usage=shutil.disk_usage,
) -> dict:
    """Combine field integrity, scheduler backlog, spot sync and disk pressure."""
    instant = now or datetime.now(timezone.utc)
    wind = weather_field_health(
        db,
        storage=storage,
        settings=settings,
        now=instant,
        model_keys=WIND_FIELD_MODELS,
    )
    waves = wave_field_health(db, storage=storage, settings=settings, now=instant)
    alerts = _health_alerts(
        wind,
        component="wind",
        require_public=require_public,
    )
    alerts.extend(
        _health_alerts(
            waves["primary"],
            component="wave_primary",
            require_public=require_public,
        )
    )
    alerts.extend(
        _health_alerts(
            waves["fallback"],
            component="wave_fallback",
            require_public=require_public,
        )
    )
    alerts.extend(
        _health_alerts(
            waves["extended"],
            component="wave_extended",
            require_public=require_public,
        )
    )

    if require_public:
        if not settings.weather_field_pipeline_enabled:
            alerts.append(
                _alert("weather_field_pipeline_disabled", "critical", "configuration")
            )
        if not settings.weather_field_public_enabled:
            alerts.append(
                _alert("wind_field_public_disabled", "critical", "configuration")
            )
        if not settings.wave_field_public_enabled:
            alerts.append(
                _alert("wave_field_public_disabled", "critical", "configuration")
            )

    spot_sync = {
        "status": "not_applicable",
        "due": 0,
        "wave_context_changed": 0,
        "wave_context": None,
    }
    if settings.wave_field_public_enabled:
        plan = load_plan(db, now=instant, settings=settings)
        changed = len(plan.wave_context_changed_spot_ids)
        spot_sync = {
            "status": "degraded" if changed else "ok",
            "due": len(plan.due_spot_ids),
            "wave_context_changed": changed,
            "wave_context": plan.wave_context,
        }
        if changed:
            alerts.append(
                _alert(
                    "spot_wave_context_out_of_sync",
                    "warning",
                    "spot_forecasts",
                    count=changed,
                    wave_context=plan.wave_context,
                )
            )

    storage_report, storage_alerts = storage_capacity_report(
        storage,
        disk_usage=disk_usage,
    )
    alerts.extend(storage_alerts)
    severities = {item["severity"] for item in alerts}
    status = "error" if "critical" in severities else "degraded" if alerts else "ok"
    return {
        "status": status,
        "checked_at": instant.isoformat(),
        "wind": wind,
        "waves": waves,
        "spot_sync": spot_sync,
        "storage": storage_report,
        "alerts": alerts,
    }
