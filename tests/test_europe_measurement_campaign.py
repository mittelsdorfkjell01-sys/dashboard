from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.weather.europe_campaign import load_campaign, select_balanced_stations
from app.weather.providers.common import ObservationStation
from app.weather.observation_worker import sync_campaign_stations
from scripts.europe_measurement_status import health_status, status
from scripts.europe_measurement_worker import validate_hosted_environment


def test_campaign_is_exactly_three_weeks_and_shadow_only():
    campaign = load_campaign()
    assert (campaign.ends_at - campaign.starts_at).days == 21
    assert campaign.mode == "shadow"
    assert campaign.public_effect == "none"
    assert campaign.freshness_limit_minutes == 180
    assert campaign.phase(campaign.starts_at) == "active"
    assert campaign.phase(campaign.ends_at) == "ended"


def test_session_status_calls_out_measurement_end():
    report = status(now=datetime(2026, 11, 2, 15, 17, 54, tzinfo=timezone.utc))
    assert report["phase"] == "ended"
    assert "beendet" in report["message"]


def test_hosted_worker_requires_a_dedicated_shadow_database_identity():
    settings = SimpleNamespace(
        database_url="postgresql+psycopg://user:secret@db.invalid/surfwind_measurement_202610",
        app_env="development",
        live_wind_rollout_stage="shadow",
        live_wind_force_baseline=True,
        live_wind_enabled_region_slugs=[],
    )
    identity = validate_hosted_environment(settings, {
        "GITHUB_ACTIONS": "true",
        "EUROPE_WIND_MEASUREMENT_DATABASE_ID": "surfwind_measurement_202610",
    })
    assert identity["runtime"] == "github_actions"
    assert identity["public_effect"] == "none"

    settings.database_url = "postgresql+psycopg://user:secret@db.invalid/production"
    try:
        validate_hosted_environment(settings, {
            "GITHUB_ACTIONS": "true",
            "EUROPE_WIND_MEASUREMENT_DATABASE_ID": "production",
        })
    except ValueError as exc:
        assert str(exc) == "hosted_measurement_database_identity_mismatch"
    else:
        raise AssertionError("production-like database identity must fail closed")


def test_campaign_health_requires_fresh_shadow_evidence():
    campaign = load_campaign()
    report = status(now=campaign.starts_at + timedelta(days=1))
    report["database"] = {
        "stations": 240,
        "observations": 500,
        "latest_observation_at": (
            campaign.starts_at + timedelta(hours=23, minutes=50)
        ).isoformat(),
        "latest_observation_received_at": (
            campaign.starts_at + timedelta(hours=23, minutes=55)
        ).isoformat(),
        "latest_observation_imported_at": (
            campaign.starts_at + timedelta(hours=23, minutes=56)
        ).isoformat(),
        "exact_bundles": 100,
        "residuals": {"degraded": 20},
        "activation_eligible_residuals": 0,
        "database_size_bytes": 100_000_000,
    }
    assert health_status(
        report, now=campaign.starts_at + timedelta(days=1)
    )["status"] == "healthy"

    report["database"]["activation_eligible_residuals"] = 1
    failed = health_status(report, now=campaign.starts_at + timedelta(days=1))
    assert failed["status"] == "failed"
    assert "public_activation_boundary_violated" in failed["failures"]


def test_campaign_health_distinguishes_clock_and_pipeline_timestamps():
    campaign = load_campaign()
    now = campaign.starts_at + timedelta(days=1)
    report = status(now=now)
    report["database"] = {
        "stations": 240,
        "observations": 1,
        "latest_observation_at": (now + timedelta(minutes=10)).isoformat(),
        "latest_observation_received_at": (now + timedelta(minutes=9)).isoformat(),
        "latest_observation_imported_at": (now + timedelta(minutes=8)).isoformat(),
        "exact_bundles": 1,
        "residuals": {"degraded": 1},
        "activation_eligible_residuals": 0,
        "database_size_bytes": 1,
    }

    failed = health_status(report, now=now)
    assert "latest_observation_clock_skew_future" in failed["failures"]
    assert "latest_observation_received_before_observed" in failed["failures"]
    assert "latest_observation_imported_before_received" in failed["failures"]


def test_balanced_station_selection_does_not_fill_one_grid_cell_first():
    stations = [
        ObservationStation(
            provider="eumetnet_esoh",
            station_id=f"a-{index}",
            name="dense",
            latitude=50.1,
            longitude=8.1,
        )
        for index in range(5)
    ] + [
        ObservationStation(
            provider="eumetnet_esoh",
            station_id="b-0",
            name="remote",
            latitude=60.1,
            longitude=20.1,
        )
    ]
    selected = select_balanced_stations(
        stations, bounds=(29.0, 72.0, -30.0, 45.0), limit=2
    )
    assert {item.station_id for item in selected} == {"a-0", "b-0"}


def test_campaign_station_is_persisted_without_a_spot_and_never_approved(db):
    from sqlalchemy import select
    from app.models import WeatherStation

    campaign = load_campaign()
    station = ObservationStation(
        provider="eumetnet_esoh",
        station_id="0-20000-0-test-campaign",
        name="Campaign fixture",
        latitude=48.0,
        longitude=2.0,
        wigos_id="0-20000-0-test-campaign",
        measurement_height_m=10.0,
        license="CC BY 4.0",
        provenance={"source": "fixture", "typical_interval_minutes": 10},
        sensor_metadata={"esoh_wind": {
            "speed_parameter": "wind_speed:10.0:mean:PT10M",
            "direction_parameter": "wind_from_direction:10.0:mean:PT10M",
            "gust_parameter": None,
            "method": "mean",
            "period": "PT10M",
            "period_seconds": 600,
        }},
        source_url="https://example.invalid/station",
        raw_payload={"id": "0-20000-0-test-campaign"},
        received_at=datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc),
    )
    try:
        report = sync_campaign_stations(
            db, [station], campaign_key=campaign.campaign_id, dry_run=False
        )
        stored = db.scalar(select(WeatherStation).where(
            WeatherStation.campaign_key == campaign.campaign_id,
            WeatherStation.provider_station_id == station.station_id,
        ))
        assert report["persisted"] == 1
        assert stored is not None and stored.spot_id is None
        assert not stored.approved and not stored.residual_approved
        assert stored.blocked  # the new metadata epoch still requires review
    finally:
        stored = db.scalar(select(WeatherStation).where(
            WeatherStation.campaign_key == campaign.campaign_id,
            WeatherStation.provider_station_id == station.station_id,
        ))
        if stored is not None:
            db.delete(stored)
            db.commit()
