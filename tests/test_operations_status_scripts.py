from __future__ import annotations

import json
from types import SimpleNamespace

from scripts import backtest_status, infrastructure_status, vercel_config_audit


def test_backtest_status_is_read_only_and_parses_latest_run(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            stdout=json.dumps(
                [{
                    "workflowName": "Europe Wind Measurement",
                    "status": "completed",
                    "conclusion": "success",
                    "createdAt": "2026-10-28T15:23:17Z",
                    "url": "https://example.invalid/run",
                }]
            )
        )

    monkeypatch.setattr(backtest_status.subprocess, "run", run)
    result = backtest_status.workflow_status("europe-wind-measurement.yml")
    assert result["conclusion"] == "success"
    assert calls[0][:3] == ["gh", "run", "list"]
    assert not {"run", "cancel", "rerun", "workflow"} & set(calls[0][3:])


def test_infrastructure_strict_contract(monkeypatch):
    responses = iter(
        [
            {"path": "/health/live", "status": 200},
            {"path": "/health/ready", "status": 200},
            {"path": "/spots/version", "status": 200, "catalog_version": "same"},
            {"path": "/auth/me", "status": 404},
            {"path": "/admin/overview", "status": 404},
            {"path": "/health/live", "status": 200},
            {"path": "/health/ready", "status": 200},
            {"path": "/spots/version", "status": 200, "catalog_version": "same"},
            {"path": "/auth/me", "status": 401},
            {"path": "/admin/overview", "status": 401},
        ]
    )
    monkeypatch.setattr(infrastructure_status, "probe", lambda *_args: next(responses))
    assert infrastructure_status.main(["--strict"]) == 0


def test_vercel_audit_reports_only_key_presence_and_safe_metadata(monkeypatch):
    expected = sorted(vercel_config_audit.EXPECTED_ENV["dashboard"])
    payloads = iter(
        [
            {"id": "hidden", "buildCommand": None, "link": {"productionBranch": "main"}},
            {"envs": [{"key": key, "target": ["production"], "value": "secret"} for key in expected]},
            {"domains": [{"name": "dashboardsurfwind.vercel.app"}]},
        ]
    )
    monkeypatch.setattr(vercel_config_audit, "_get", lambda *_args: next(payloads))
    result = vercel_config_audit.audit_project("dashboard", token="hidden", team="hidden")
    assert result["ok"] is True
    assert "secret" not in json.dumps(result)
