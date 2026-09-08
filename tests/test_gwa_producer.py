"""WP3 Task 3: GWA sector-factor producer — pure arithmetic, status paths, persistence."""

from __future__ import annotations

import math
import uuid

import pytest
from geoalchemy2 import WKTElement

from app.forecast.gwa_producer import (
    SECTOR_COUNT,
    WeibullSector,
    bin_mean_speeds,
    compute_gwa_sectors,
    persist_gwa_sectors,
    weibull_mean,
)
from app.models import Region, Spot, SpotWeatherProfile, SpotWeatherSector


class FakeReader:
    def __init__(self, sectors, *, mounted=True):
        self.mounted = mounted
        self._sectors = sectors

    def read(self, lat, lon):
        return self._sectors


class FakeReference:
    def __init__(self, means):
        self._means = means

    def sector_mean_speeds(self, lat, lon, window):
        return self._means


class FakeSlope:
    def __init__(self, gradients):
        self._gradients = gradients

    def sector_gradients(self, lat, lon):
        return self._gradients


def _uniform(a=8.0, k=1.0):
    return [WeibullSector(a, k) for _ in range(SECTOR_COUNT)]


# --- pure arithmetic -------------------------------------------------------


def test_weibull_mean_matches_closed_form():
    assert weibull_mean(8.0, 1.0) == pytest.approx(8.0)  # gamma(2) == 1
    assert weibull_mean(10.0, 2.0) == pytest.approx(10.0 * math.gamma(1.5))
    assert math.isnan(weibull_mean(0.0, 2.0))


def test_factor_is_gwa_over_reference_and_clamped():
    reader = FakeReader(_uniform(a=8.0, k=1.0))            # mean_gwa == 8.0
    reference = FakeReference([6.4] * SECTOR_COUNT)         # ratio 1.25
    result = compute_gwa_sectors(0.0, 0.0, gwa_reader=reader, reference=reference)
    assert result.status == "ok" and result.enabled is True
    assert all(s.speed_factor == pytest.approx(1.25) for s in result.sectors)
    assert all(s.saturated is False and s.confidence == "ok" for s in result.sectors)


def test_factor_saturates_at_hull_and_flags():
    reader = FakeReader(_uniform(a=12.0, k=1.0))           # mean_gwa == 12.0
    reference = FakeReference([6.0] * SECTOR_COUNT)         # ratio 2.0 -> clamp 1.60
    result = compute_gwa_sectors(0.0, 0.0, gwa_reader=reader, reference=reference)
    assert all(s.speed_factor == pytest.approx(1.60) and s.saturated for s in result.sectors)


def test_zero_or_nan_reference_stays_neutral_low_confidence():
    reader = FakeReader(_uniform())
    means = [6.4] * SECTOR_COUNT
    means[0] = 0.0
    means[1] = float("nan")
    result = compute_gwa_sectors(0.0, 0.0, gwa_reader=reader, reference=FakeReference(means))
    assert result.sectors[0].speed_factor == 1.0 and result.sectors[0].confidence == "low"
    assert result.sectors[1].speed_factor == 1.0 and result.sectors[1].confidence == "low"


def test_steep_slope_marks_low_confidence_without_dropping_factor():
    gradients = [0.0] * SECTOR_COUNT
    gradients[4] = 0.5  # > 0.30
    result = compute_gwa_sectors(
        0.0, 0.0, gwa_reader=FakeReader(_uniform()), reference=FakeReference([6.4] * SECTOR_COUNT),
        slope_provider=FakeSlope(gradients),
    )
    assert result.sectors[4].confidence == "low"
    assert result.sectors[4].speed_factor == pytest.approx(1.25)  # factor still computed
    assert result.sectors[0].confidence == "ok"


# --- status paths (never invented values) ----------------------------------


def test_unmounted_raster_returns_neutral_status():
    result = compute_gwa_sectors(
        0.0, 0.0, gwa_reader=FakeReader(_uniform(), mounted=False),
        reference=FakeReference([6.4] * SECTOR_COUNT),
    )
    assert result.status == "gwa_not_mounted" and result.enabled is False
    assert all(s.speed_factor == 1.0 for s in result.sectors)


def test_nodata_cell_returns_neutral_status():
    result = compute_gwa_sectors(
        0.0, 0.0, gwa_reader=FakeReader(None), reference=FakeReference([6.4] * SECTOR_COUNT),
    )
    assert result.status == "gwa_nodata"
    assert all(s.speed_factor == 1.0 for s in result.sectors)


def test_reference_unavailable_returns_status():
    result = compute_gwa_sectors(0.0, 0.0, gwa_reader=FakeReader(_uniform()), reference=FakeReference(None))
    assert result.status == "reference_unavailable"


# --- binning ---------------------------------------------------------------


def test_bin_mean_speeds_puts_easterly_wind_in_sector_three():
    # from-east (90 deg): u=-s, v=0 -> sector index 3.
    means = bin_mean_speeds([-10.0, -10.0], [0.0, 0.0])
    assert means[3] == pytest.approx(10.0)
    assert math.isnan(means[0])


# --- persistence -----------------------------------------------------------


@pytest.fixture
def gwa_spot(db):
    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"gwa-region-{suffix}", name=f"GWA Region {suffix}",
                    normalized_name=f"gwa region {suffix}", country="FR", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"gwa-spot-{suffix}", name=f"GWA Spot {suffix}",
                normalized_name=f"gwa spot {suffix}", region_id=region.id,
                location=WKTElement("POINT(-1.44 43.66)", srid=4326),
                sports=["wind"], water_type=["sea"], status="published")
    db.add(spot)
    db.commit()
    yield spot
    db.query(SpotWeatherSector).delete()
    profile = db.query(SpotWeatherProfile).filter_by(spot_id=spot.id).one_or_none()
    if profile:
        db.delete(profile)
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


def _ok_result():
    return compute_gwa_sectors(
        43.66, -1.44, gwa_reader=FakeReader(_uniform(a=8.0, k=1.0)),
        reference=FakeReference([6.4] * SECTOR_COUNT), grid_cell=[43.75, -1.5],
    )


def test_persist_writes_twelve_versioned_rows_and_is_idempotent(db, gwa_spot):
    result = _ok_result()
    first = persist_gwa_sectors(db, gwa_spot.id, result)
    assert first == {"status": "ok", "written": 12, "version": 1, "reason": "written"}

    rows = db.query(SpotWeatherSector).join(SpotWeatherProfile).filter(
        SpotWeatherProfile.spot_id == gwa_spot.id).all()
    assert len(rows) == 12
    assert all(r.enabled and r.direction_offset_deg == 0 for r in rows)
    assert all(r.speed_factor == pytest.approx(1.25) for r in rows)

    # Identical input -> no new version.
    again = persist_gwa_sectors(db, gwa_spot.id, _ok_result())
    assert again["reason"] == "idempotent" and again["version"] == 1

    # A changed result bumps the version.
    changed = compute_gwa_sectors(
        43.66, -1.44, gwa_reader=FakeReader(_uniform(a=8.8, k=1.0)),
        reference=FakeReference([6.4] * SECTOR_COUNT), grid_cell=[43.75, -1.5])
    bumped = persist_gwa_sectors(db, gwa_spot.id, changed)
    assert bumped["version"] == 2 and bumped["written"] == 12


def test_reference_unavailable_never_writes(db, gwa_spot):
    result = compute_gwa_sectors(43.66, -1.44, gwa_reader=FakeReader(_uniform()), reference=FakeReference(None))
    outcome = persist_gwa_sectors(db, gwa_spot.id, result)
    assert outcome["written"] == 0 and outcome["reason"] == "no_write"
    assert db.query(SpotWeatherSector).join(SpotWeatherProfile).filter(
        SpotWeatherProfile.spot_id == gwa_spot.id).count() == 0


def test_unmounted_persists_disabled_neutral_rows(db, gwa_spot):
    result = compute_gwa_sectors(
        43.66, -1.44, gwa_reader=FakeReader(_uniform(), mounted=False),
        reference=FakeReference([6.4] * SECTOR_COUNT))
    outcome = persist_gwa_sectors(db, gwa_spot.id, result)
    assert outcome["written"] == 12
    rows = db.query(SpotWeatherSector).join(SpotWeatherProfile).filter(
        SpotWeatherProfile.spot_id == gwa_spot.id).all()
    assert all(not r.enabled and r.speed_factor == 1.0 for r in rows)
