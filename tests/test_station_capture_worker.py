"""Fail-closed controls for the non-production raw capture worker."""

from types import SimpleNamespace

import pytest

from scripts.station_capture_worker import validate_capture_environment


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
