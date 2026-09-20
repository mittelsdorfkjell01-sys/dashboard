"""Fail-closed controls for the non-production raw capture worker."""

from types import SimpleNamespace

import pytest

from datetime import datetime, timezone

from scripts.station_capture_worker import capture_health, validate_capture_environment


def _settings(**overrides):
    values = {
        "app_env": "development",
        "live_wind_rollout_stage": "shadow",
        "live_wind_force_baseline": True,
        "live_wind_enabled_region_slugs": [],
        "database_url": (
            "postgresql+psycopg://capture.invalid/surfwind_capture_northsea"
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _environment(**overrides):
    values = {
        "LIVE_WIND_CAPTURE_AUTHORIZED": "true",
        "LIVE_WIND_CAPTURE_MODE": "raw_only",
        "LIVE_WIND_CAPTURE_ENVIRONMENT_ID": "surfwind_capture_northsea",
        "LIVE_WIND_RUNNER_ID": "runner-northsea-1",
        "LIVE_WIND_RUNNER_JOB_ID": "job-2",
    }
    values.update(overrides)
    return values


def test_capture_environment_accepts_only_explicit_nonproduction_raw_identity():
    result = validate_capture_environment(_settings(), _environment())
    assert result == {
        "environment_id": "surfwind_capture_northsea",
        "runner_id": "runner-northsea-1",
        "runner_job_id": "job-2",
        "mode": "raw_only",
        "rollout_stage": "shadow",
        "public_effect": "none",
    }


@pytest.mark.parametrize(
    ("settings", "environment", "error"),
    [
        (_settings(app_env="production"), _environment(), "nonproduction"),
        (_settings(live_wind_rollout_stage="pilot"), _environment(), "shadow"),
        (_settings(live_wind_force_baseline=False), _environment(), "baseline"),
        (_settings(live_wind_enabled_region_slugs=["x"]), _environment(), "allowlist"),
        (_settings(), _environment(LIVE_WIND_CAPTURE_AUTHORIZED="false"), "authorized"),
        (_settings(), _environment(LIVE_WIND_CAPTURE_MODE="analysis"), "raw_only"),
        (
            _settings(),
            _environment(LIVE_WIND_CAPTURE_ENVIRONMENT_ID="surfwind_capture_other"),
            "database_identity",
        ),
        (_settings(), _environment(LIVE_WIND_RUNNER_JOB_ID=""), "runner_identity"),
    ],
)
def test_capture_environment_fails_closed(settings, environment, error):
    with pytest.raises(ValueError, match=error):
        validate_capture_environment(settings, environment)


def test_capture_health_keeps_provider_gaps_separate():
    now = datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)
    report = {
        "continuous_capture": {"cycle_status": {
            "observations:dwd": {"last_success_at": "2026-09-19T23:50:00+00:00", "failures_24h": 0},
        }},
        "catalogs": {"dwd": {"last_success_at": "2026-09-19T02:00:00+00:00", "age_hours": 22}},
        "providers": {"dwd": {"operational_observations_24h": 3, "latest_observation_age_minutes": 15}},
        "provider_cursors": {"dwd": {"paused": False}},
    }

    health = capture_health(report, now=now)

    assert health["status"] == "alert"
    assert not [item for item in health["alerts"] if item.get("provider") == "dwd"]
    assert {item["code"] for item in health["alerts"] if item.get("provider") == "dmi"} == {
        "catalog_never_succeeded",
        "operational_observation_missing",
        "observation_stale",
        "observation_cycle_late",
    }
