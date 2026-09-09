"""WP6 measurement calibration: shrinkage prior->posterior and the sector worker."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from geoalchemy2 import WKTElement

from app.models import (
    Region,
    Spot,
    SpotWeatherProfile,
    SpotWeatherSector,
    WeatherForecastSample,
    WeatherObservation,
    WeatherStation,
)
from app.weather.sector_calibration import (
    MIN_SECTOR_SAMPLES,
    SHRINKAGE_K,
    recalibrate_spot_sectors,
    sector_measured_factor,
    shrink_factor,
)


# --- pure shrinkage --------------------------------------------------------


def test_shrink_factor_endpoints_and_halfway():
    assert shrink_factor(1.2, 1.6, 0) == 1.2                      # no data -> prior
    assert shrink_factor(1.2, 1.6, int(SHRINKAGE_K)) == pytest.approx(1.4)  # n=k -> halfway
    assert shrink_factor(1.2, 1.6, 100000) == pytest.approx(1.6, abs=1e-3)  # lots -> measured


def test_sector_measured_factor_needs_minimum_samples():
    few = [(15.0, 10.0)] * (MIN_SECTOR_SAMPLES - 1)
    assert sector_measured_factor(few) is None
    enough = [(15.0, 10.0)] * MIN_SECTOR_SAMPLES
    factor, n = sector_measured_factor(enough)
    assert factor == pytest.approx(1.5) and n == MIN_SECTOR_SAMPLES


def test_sector_measured_factor_ignores_nonpositive_model_speed():
    assert sector_measured_factor([(10.0, 0.0)] * MIN_SECTOR_SAMPLES) is None


# --- DB worker -------------------------------------------------------------


@pytest.fixture
def calib_spot(db):
    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"cal-region-{suffix}", name=f"Cal Region {suffix}",
                    normalized_name=f"cal region {suffix}", country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"cal-spot-{suffix}", name=f"Cal Spot {suffix}",
                normalized_name=f"cal spot {suffix}", region_id=region.id,
                location=WKTElement("POINT(8.5 54.5)", srid=4326),
                sports=["wind"], water_type=["sea"], status="published")
    db.add(spot)
    db.flush()
    station = WeatherStation(spot_id=spot.id, provider="dwd", provider_station_id="00099",
                             name="Ref", latitude=54.5, longitude=8.5, active=True,
                             approved=True, representativeness_status="passed")
    db.add(station)
    profile = SpotWeatherProfile(spot_id=spot.id)
    db.add(profile)
    db.flush()
    for i in range(12):  # neutral prior (factor 1.0) for every 30-degree sector
        db.add(SpotWeatherSector(profile_id=profile.id, start_deg=i * 30, end_deg=(i * 30 + 30) % 360,
                                 speed_factor=1.0, version=1, enabled=True,
                                 note='{"method":"gwa_over_reference"}'))
    db.commit()
    yield spot, station, profile
    db.query(SpotWeatherSector).delete()
    db.query(WeatherObservation).delete()
    db.query(WeatherForecastSample).delete()
    db.delete(db.get(SpotWeatherProfile, profile.id))
    db.delete(db.get(WeatherStation, station.id))
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


def _seed_matched_series(db, spot, station, *, obs_speed, model_speed, direction, count=12):
    now = datetime.now(timezone.utc)
    for i in range(count):
        valid = now - timedelta(hours=i + 1)
        db.add(WeatherObservation(station_id=station.id, observed_at=valid, wind_speed_ms=obs_speed,
                                  wind_direction_deg=direction, provider_quality="1", import_status="accepted"))
        db.add(WeatherForecastSample(spot_id=spot.id, model_id="icon", issued_at=valid - timedelta(hours=5),
                                     valid_at=valid, lead_hours=5, wind_speed_ms=model_speed,
                                     wind_direction_deg=direction))
    db.commit()


def test_posterior_shrinks_prior_towards_measurement(db, calib_spot):
    spot, station, profile = calib_spot
    # Model 10 m/s vs observed 15 m/s in the 270 deg sector (index 9): measured 1.5.
    _seed_matched_series(db, spot, station, obs_speed=15.0, model_speed=10.0, direction=270.0)
    outcome = recalibrate_spot_sectors(db, spot.id, lookback_days=30)
    assert outcome["status"] == "ok" and outcome["version"] == 2 and outcome["calibrated"] == 1

    db.expire_all()
    v2 = {int(s.start_deg // 30): s for s in db.query(SpotWeatherSector).filter_by(
        profile_id=profile.id, version=2).all()}
    expected = 1.0 + (1.5 - 1.0) * (12 / (12 + SHRINKAGE_K))  # shrinkage blend
    assert v2[9].speed_factor == pytest.approx(round(expected, 4))
    assert v2[9].speed_factor < 1.5  # shrunk towards prior, not the raw measurement
    assert v2[0].speed_factor == 1.0  # a sector with no data carries the prior
    # version 1 prior is never deleted
    assert db.query(SpotWeatherSector).filter_by(profile_id=profile.id, version=1).count() == 12


def test_idempotent_when_measurements_unchanged(db, calib_spot):
    spot, station, _ = calib_spot
    _seed_matched_series(db, spot, station, obs_speed=15.0, model_speed=10.0, direction=270.0)
    first = recalibrate_spot_sectors(db, spot.id, lookback_days=30)
    second = recalibrate_spot_sectors(db, spot.id, lookback_days=30)
    assert first["version"] == 2
    assert second["status"] == "idempotent" and second["version"] == 2


def test_insufficient_measurements_writes_nothing(db, calib_spot):
    spot, station, profile = calib_spot
    _seed_matched_series(db, spot, station, obs_speed=15.0, model_speed=10.0, direction=270.0,
                         count=MIN_SECTOR_SAMPLES - 1)
    outcome = recalibrate_spot_sectors(db, spot.id, lookback_days=30)
    assert outcome["status"] == "insufficient_measurements" and outcome["written"] == 0
    assert db.query(SpotWeatherSector).filter_by(profile_id=profile.id).count() == 12  # only the prior
