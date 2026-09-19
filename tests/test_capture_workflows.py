"""The checked-in capture schedules stay raw-only and fail closed."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_raw_capture_orders_exact_assets_before_observations_and_has_no_analysis():
    workflow = (ROOT / ".github/workflows/live-wind-capture.yml").read_text(
        encoding="utf-8"
    )
    exact = "python -m scripts.exact_run_worker capture"
    observations = "python -m scripts.station_capture_worker observations"
    assert workflow.index(exact) < workflow.index(observations)
    assert "LIVE_WIND_CAPTURE_ENABLED == 'true'" in workflow
    assert "--require-new-job" in workflow
    for forbidden in (
        "exact_run_worker residuals",
        "live_wind_worker",
        "live_wind_holdouts",
        "LIVE_WIND_ENDPOINT",
    ):
        assert forbidden not in workflow


def test_catalog_and_observation_schedules_are_independent():
    catalog = (ROOT / ".github/workflows/station-catalog.yml").read_text(
        encoding="utf-8"
    )
    capture = (ROOT / ".github/workflows/live-wind-capture.yml").read_text(
        encoding="utf-8"
    )
    assert "LIVE_WIND_CAPTURE_CATALOG_ENABLED == 'true'" in catalog
    assert "station_capture_worker catalog" in catalog
    assert "station_capture_worker observations" not in catalog
    assert "station_capture_worker observations" in capture
    assert "station_capture_worker catalog" not in capture
    assert "secrets.LIVE_WIND_CAPTURE_DATABASE_URL" in catalog
    assert "secrets.LIVE_WIND_CAPTURE_DATABASE_URL" in capture
