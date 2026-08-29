"""Manual, side-effect-free weather monitoring evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

SECRET_PATTERN = re.compile(r"(?i)(password|token|secret|api[_-]?key|authorization)=?[^\s,;]*")


def safe_error_class(error: BaseException) -> str:
    return error.__class__.__name__


def incident_fingerprint(check: str, error_class: str) -> str:
    return hashlib.sha256(f"weather-monitor:v1:{check}:{error_class}".encode()).hexdigest()[:20]


def sanitize(value: object) -> object:
    if isinstance(value, dict):
        return {key: ("[redacted]" if SECRET_PATTERN.search(str(key)) else sanitize(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return SECRET_PATTERN.sub("[redacted]", value)
    return value


def evaluate(snapshot: dict) -> dict:
    """Evaluate a supplied snapshot; fetching production state is intentionally separate."""
    required = ("liveness", "readiness", "schema", "catalog_version", "canary_contract")
    checks = {name: snapshot.get(name, "unknown") for name in required}
    errors = []
    for name, state in checks.items():
        if state not in ("ok", "degraded"):
            errors.append({"check": name, "state": state, "fingerprint": incident_fingerprint(name, str(state))})
    return sanitize({
        "contract_version": "weather-monitor-v1",
        "status": "ok" if not errors else "error",
        "checks": checks,
        "weather": snapshot.get("weather", {}),
        "providers": snapshot.get("providers", {}),
        "budget": snapshot.get("budget", {}),
        "forecast_cycle": snapshot.get("forecast_cycle", {}),
        "incidents": errors,
        "slo": {name: "pending_evidence" for name in (
            "api_availability_99_5", "detection_under_15m", "atmosphere_fresh_99",
            "no_unmarked_stale", "measurement_under_30m", "observation_runs_99",
            "all_values_sourced", "calibration_holdout_improves")},
    })


class IncidentDeduplicator:
    """Adapter-friendly dedupe; a later GitHub writer can be injected and mocked."""
    def __init__(self, store):
        self.store = store

    def publish_once(self, incident: dict) -> bool:
        fingerprint = incident["fingerprint"]
        if self.store.exists(fingerprint):
            return False
        self.store.create({"title": f"Weather check failed: {incident['check']}", "fingerprint": fingerprint})
        return True

