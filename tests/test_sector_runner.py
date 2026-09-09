"""Sector-producer runner: candidate policy, serving invariance, batch/resume, activation."""

from __future__ import annotations

import uuid

import pytest
from geoalchemy2 import WKTElement

from app.forecast.gwa_producer import SECTOR_COUNT, WeibullSector, compute_gwa_sectors
from app.forecast.sector_runner import _persist_candidate, run_sector_producer
from app.models import ForecastSectorBuild, Region, Spot, SpotWeatherProfile, SpotWeatherSector
from app.weather.physics.manual import select_sector
from app.weather.sector_activation import activate_spot_sectors, latest_candidate_version


class _FakeReader:
    mounted = True

    def read(self, lat, lon):
        return [WeibullSector(8.0, 1.0) for _ in range(SECTOR_COUNT)]  # mean 8.0


class _FakeReference:
    def sector_mean_speeds(self, lat, lon, window):
        return [6.4] * SECTOR_COUNT  # ratio 1.25


def _ok_result():
    return compute_gwa_sectors(43.66, -1.44, gwa_reader=_FakeReader(), reference=_FakeReference(),
                               grid_cell=[43.75, -1.5])


def _spot(db, *, lon=-1.44, lat=43.66):
    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"rn-region-{suffix}", name=f"RN Region {suffix}",
                    normalized_name=f"rn region {suffix}", country="FR", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"rn-spot-{suffix}", name=f"RN Spot {suffix}",
                normalized_name=f"rn spot {suffix}", region_id=region.id,
                location=WKTElement(f"POINT({lon} {lat})", srid=4326),
                sports=["wind"], water_type=["sea"], status="published")
    db.add(spot)
    db.commit()
    return spot, region


@pytest.fixture
def runner_spot(db):
    spot, region = _spot(db)
    yield spot
    db.query(SpotWeatherSector).delete()
    db.query(ForecastSectorBuild).delete()
    prof = db.query(SpotWeatherProfile).filter_by(spot_id=spot.id).one_or_none()
    if prof:
        db.delete(prof)
    db.delete(spot)
    db.flush()
    db.delete(region)
    db.commit()


# --- the critical serving-invariance guarantee ----------------------------


def test_writing_candidates_does_not_change_the_served_sector(db, runner_spot):
    profile = SpotWeatherProfile(spot_id=runner_spot.id)
    db.add(profile)
    db.flush()
    # Active served version (enabled) around 270 deg.
    db.add(SpotWeatherSector(profile_id=profile.id, start_deg=240, end_deg=270, speed_factor=1.30,
                             version=1, enabled=True, note='{"method":"gwa_over_reference"}'))
    db.commit()
    served_before = select_sector(255.0, db.query(SpotWeatherSector).filter_by(profile_id=profile.id).all())

    status, version = _persist_candidate(db, runner_spot.id, "gwa", _ok_result())
    db.commit()
    assert status == "candidate_written" and version == 2

    rows = db.query(SpotWeatherSector).filter_by(profile_id=profile.id).all()
    candidate_rows = [r for r in rows if r.version == 2]
    assert len(candidate_rows) == 12 and all(not r.enabled for r in candidate_rows)  # candidates disabled
    served_after = select_sector(255.0, rows)
    # A newer *disabled* version must not shadow the active one.
    assert served_after.version == 1 == served_before.version
    assert served_after.speed_factor == pytest.approx(1.30)


def test_persist_is_hash_idempotent(db, runner_spot):
    first_status, first_version = _persist_candidate(db, runner_spot.id, "gwa", _ok_result())
    db.commit()
    second_status, second_version = _persist_candidate(db, runner_spot.id, "gwa", _ok_result())
    db.commit()
    assert first_status == "candidate_written"
    assert second_status == "unchanged" and second_version == first_version
    build = db.query(ForecastSectorBuild).filter_by(spot_id=runner_spot.id, producer="gwa").one()
    assert build.content_hash and build.version == first_version


# --- status skips (never store neutral factors) ---------------------------


def test_unmounted_gwa_records_status_and_writes_no_factors(db, runner_spot):
    summary = run_sector_producer(db, producer="gwa", spot_ids=[runner_spot.id])
    assert summary["statuses"] == {"gwa_not_mounted": 1}
    assert db.query(SpotWeatherSector).count() == 0
    build = db.query(ForecastSectorBuild).filter_by(spot_id=runner_spot.id, producer="gwa").one()
    assert build.status == "gwa_not_mounted" and build.content_hash is None


def test_microscale_is_inert_while_provider_is_a_stub(db, runner_spot):
    summary = run_sector_producer(db, producer="microscale", spot_ids=[runner_spot.id])
    assert summary["statuses"] == {"microscale_unavailable": 1}
    assert db.query(SpotWeatherSector).count() == 0


def test_dry_run_writes_nothing(db, runner_spot):
    summary = run_sector_producer(db, producer="gwa", spot_ids=[runner_spot.id], dry_run=True)
    assert summary["dry_run"] is True
    assert db.query(ForecastSectorBuild).count() == 0
    assert db.query(SpotWeatherSector).count() == 0


# --- batch / resume --------------------------------------------------------


def test_batch_is_resumable_and_drains_all_spots(db):
    spots = [_spot(db) for _ in range(3)]
    ids = {str(s.id) for s, _ in spots}
    try:
        first = run_sector_producer(db, producer="gwa", limit=2)
        assert first["processed"] == 2
        run_sector_producer(db, producer="gwa", limit=2)
        # Least-recently-built ordering: the never-built spot is picked before re-runs.
        built = {r.spot_id for r in db.query(ForecastSectorBuild.spot_id).all()}
        assert {str(b) for b in built} >= ids  # every spot eventually built
    finally:
        db.query(ForecastSectorBuild).delete()
        for spot, region in spots:
            db.delete(spot)
            db.flush()
            db.delete(region)
        db.commit()


# --- activation is the only enable path ------------------------------------


def test_activation_enables_one_version_and_disables_the_previous(db, runner_spot):
    profile = SpotWeatherProfile(spot_id=runner_spot.id)
    db.add(profile)
    db.flush()
    db.add(SpotWeatherSector(profile_id=profile.id, start_deg=240, end_deg=270, speed_factor=1.10,
                             version=1, enabled=True, note='{"method":"gwa_over_reference"}'))
    db.commit()
    _persist_candidate(db, runner_spot.id, "gwa", _ok_result())  # candidate v2, disabled
    db.commit()

    version = latest_candidate_version(db, runner_spot.id)
    assert version == 2
    result = activate_spot_sectors(db, runner_spot.id, version, actor="test", reason="unit")
    assert result["activated_version"] == 2 and result["deactivated_versions"] == [1]

    rows = db.query(SpotWeatherSector).filter_by(profile_id=profile.id).all()
    served = select_sector(255.0, rows)
    assert served.version == 2 and served.enabled is True
    assert all(not r.enabled for r in rows if r.version == 1)
