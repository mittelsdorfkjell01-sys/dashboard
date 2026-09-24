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


def test_hosted_station_schedules_need_no_persistent_worker_or_database_secret():
    observations = (ROOT / ".github/workflows/weather-observation-import.yml").read_text(
        encoding="utf-8"
    )
    catalog = (
        ROOT / ".github/workflows/weather-station-catalog-refresh.yml"
    ).read_text(encoding="utf-8")

    assert "runs-on: ubuntu-latest" in observations
    assert "runs-on: ubuntu-latest" in catalog
    assert 'cron: "6,16,26,36,46,56 * * * *"' in observations
    assert 'cron: "22 */6 * * *"' in catalog
    assert "WEATHER_OBSERVATION_IMPORT_ENABLED == 'true'" in observations
    assert "WEATHER_STATION_CATALOG_ENABLED == 'true'" in catalog
    assert "/cron/observations" in observations
    assert "/cron/station-catalog" in catalog
    assert "jq -e" in observations
    assert '(.errors // 0) == 0' in observations
    assert "jq -e" in catalog
    assert '.providers[]?.status' in catalog
    for workflow in (observations, catalog):
        assert "secrets.WEATHER_SHADOW_CRON_SECRET" in workflow
        assert "DATABASE_URL" not in workflow
        assert "REDIS_URL" not in workflow
        assert "self-hosted" not in workflow
        assert "exact_run_worker" not in workflow
        assert "live_wind_worker" not in workflow
        assert "forecast" not in workflow.casefold()


def test_weather_verification_schedule_is_daily_and_fail_closed():
    workflow = (ROOT / ".github/workflows/weather-verification.yml").read_text(
        encoding="utf-8"
    )
    assert 'cron: "38 5 * * *"' in workflow
    assert "WEATHER_VERIFICATION_ENABLED == 'true'" in workflow
    assert "secrets.WEATHER_SHADOW_CRON_SECRET" in workflow
    assert "/cron/verification" in workflow
    assert "forecast_sample_retention" in workflow
    assert "DATABASE_URL" not in workflow


def test_hosted_exact_point_capture_uses_ephemeral_grib_and_persistent_database():
    workflow = (ROOT / ".github/workflows/live-wind-exact-points.yml").read_text(
        encoding="utf-8"
    )
    assert "runs-on: ubuntu-latest" in workflow
    assert 'cron: "1,11,21,31,41,51 * * * *"' in workflow
    assert "LIVE_WIND_POINT_CAPTURE_ENABLED" in workflow
    assert "LIVE_WIND_POINT_DATABASE_URL" in workflow
    assert "RUNNER_TEMP" in workflow
    assert "${{ runner.temp }}" not in workflow
    assert 'cache_dir="$RUNNER_TEMP/live-wind-exact"' in workflow
    assert '>> "$GITHUB_ENV"' in workflow
    assert "self-hosted" not in workflow
    assert "exact_run_worker capture" in workflow
    assert "exact_run_worker residuals" not in workflow
    assert "forecast" not in workflow.casefold()


def test_hosted_residual_job_reads_persisted_points_without_raw_cache():
    workflow = (ROOT / ".github/workflows/live-wind-station-residuals.yml").read_text(
        encoding="utf-8"
    )
    assert "runs-on: ubuntu-latest" in workflow
    assert 'cron: "8,18,28,38,48,58 * * * *"' in workflow
    assert "LIVE_WIND_RESIDUALS_ENABLED" in workflow
    assert "LIVE_WIND_POINT_DATABASE_URL" in workflow
    assert "persisted-residuals" in workflow
    assert "LIVE_WIND_EXACT_RUN_CACHE_DIR" not in workflow
    assert "self-hosted" not in workflow
    assert "forecast" not in workflow.casefold()
