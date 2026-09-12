"""Sector-producer runner: candidate policy, serving invariance, batch/resume, activation."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import select, text

from app.forecast.gwa_producer import compute_gwa_sectors
from app.forecast.publisher import enqueue, run_job
from app.forecast.sector_runner import _persist_candidate, run_sector_producer
from app.db.session import SessionLocal
from app.live.cache import InMemoryCache
from app.live.public_cache import (
    get_public_forecast,
    public_forecast_key,
    public_live_key,
)
from app.models import (
    ForecastSectorBuild,
    ForecastSnapshot,
    ForecastVerificationScore,
    Region,
    Spot,
    SpotWeatherProfile,
    SpotWeatherSector,
)
from app.weather.physics.manual import select_sector
from app.weather.profiles import WIND_CLIMATOLOGY_V3_NOTE, is_forecast_sector
from app.weather.sector_activation import (
    activate_spot_sectors,
    candidate_variant,
    latest_candidate_version,
)
from app.weather.serving_context import serving_context_hash
from tests.live_helpers import FakeOpenMeteoClient


class _FakeReader:
    mounted = True

    def read(self, lat, lon):
        return 8.0  # mean_GWA @10 m


class _FakeReference:
    def mean_speed(self, lat, lon, window):
        return 6.4  # ratio 1.25


def _ok_result():
    return compute_gwa_sectors(43.66, -1.44, gwa_reader=_FakeReader(), reference=_FakeReference(),
                               grid_cell=[43.75, -1.5])


def _authorize_candidate(db, spot_id, version: int, *, drop: float = 1.0):
    run_id = uuid.uuid4()
    context_hash = serving_context_hash(
        db, spot_id, candidate_version=version
    )
    for variant, mae in (("raw", 2.0), (candidate_variant(version), 2.0 - drop)):
        db.add(ForecastVerificationScore(
            run_id=run_id,
            spot_id=spot_id,
            model_id="consensus",
            variant=variant,
            lead_bucket="0-48h",
            direction_sector=0,
            sample_count=10,
            bias_ms=mae,
            mae_ms=mae,
            rmse_ms=mae,
            gate_context_hash=context_hash,
        ))
    db.commit()
    return run_id


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
    # Omnidirectional: one factor on all 12 sectors, no direction offset.
    assert len({round(r.speed_factor, 4) for r in candidate_rows}) == 1
    assert all(r.direction_offset_deg == 0 for r in candidate_rows)
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
        first = run_sector_producer(
            db,
            producer="gwa",
            spot_ids=[spot.id for spot, _ in spots],
            limit=2,
        )
        assert first["processed"] == 2
        run_sector_producer(
            db,
            producer="gwa",
            spot_ids=[spot.id for spot, _ in spots],
            limit=2,
        )
        # Least-recently-built ordering: the never-built spot is picked before re-runs.
        built = {
            r.spot_id
            for r in db.query(ForecastSectorBuild.spot_id)
            .filter(ForecastSectorBuild.spot_id.in_([spot.id for spot, _ in spots]))
            .all()
        }
        assert {str(b) for b in built} >= ids  # every spot eventually built
    finally:
        db.query(ForecastSectorBuild).filter(
            ForecastSectorBuild.spot_id.in_([spot.id for spot, _ in spots])
        ).delete(synchronize_session=False)
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
    climatology_direction = SpotWeatherSector(
        profile_id=profile.id,
        start_deg=0,
        end_deg=22.5,
        speed_factor=1.0,
        version=1,
        enabled=True,
        note=WIND_CLIMATOLOGY_V3_NOTE,
    )
    db.add(climatology_direction)
    db.commit()
    _persist_candidate(db, runner_spot.id, "gwa", _ok_result())  # candidate v2, disabled
    now = datetime.now(timezone.utc)
    snapshot = ForecastSnapshot(
        spot_id=runner_spot.id,
        generated_at=now,
        valid_until=now + timedelta(hours=3),
        consensus_version="test",
        physics_version="test",
        quality_level="baseline",
        fallback_status="test",
        payload={},
        internal={},
        attributions=[],
        active=True,
    )
    db.add(snapshot)
    db.commit()

    cache = InMemoryCache()
    cache.set(public_live_key(runner_spot.id), {"old": True}, 300)
    cache.set(public_forecast_key(runner_spot.id), {"old": True}, 300)

    version = latest_candidate_version(db, runner_spot.id)
    assert version == 2
    gate_run_id = _authorize_candidate(db, runner_spot.id, version)
    result = activate_spot_sectors(
        db,
        runner_spot.id,
        version,
        actor="test",
        gate_run_id=gate_run_id,
        min_bias_drop=0.5,
        reason="unit",
        cache=cache,
    )
    assert result["activated_version"] == 2 and result["deactivated_versions"] == [1]
    assert result["snapshots_invalidated"] == 1
    assert cache.get(public_live_key(runner_spot.id)) is None
    assert cache.get(public_forecast_key(runner_spot.id)) is None

    db.refresh(snapshot)
    db.refresh(climatology_direction)
    assert snapshot.active is False
    assert climatology_direction.enabled is True
    rows = db.query(SpotWeatherSector).filter_by(profile_id=profile.id).all()
    served = select_sector(255.0, rows)
    assert served.version == 2 and served.enabled is True
    assert all(not r.enabled for r in rows if r.version == 1 and is_forecast_sector(r))
    assert latest_candidate_version(db, runner_spot.id) is None


def test_activation_rejects_an_incomplete_candidate(db, runner_spot):
    profile = SpotWeatherProfile(spot_id=runner_spot.id)
    db.add(profile)
    db.flush()
    db.add(SpotWeatherSector(
        profile_id=profile.id,
        start_deg=0,
        end_deg=30,
        speed_factor=1.1,
        version=1,
        enabled=False,
    ))
    db.commit()

    with pytest.raises(ValueError, match="all 12 canonical"):
        activate_spot_sectors(
            db,
            runner_spot.id,
            1,
            actor="test",
            gate_run_id=uuid.uuid4(),
        )

    assert db.query(SpotWeatherSector).filter_by(profile_id=profile.id, enabled=True).count() == 0


def test_latest_candidate_skips_a_newer_incomplete_version(db, runner_spot):
    profile = SpotWeatherProfile(spot_id=runner_spot.id)
    db.add(profile)
    db.flush()
    _persist_candidate(db, runner_spot.id, "gwa", _ok_result())  # complete v1
    db.add(SpotWeatherSector(
        profile_id=profile.id,
        start_deg=0,
        end_deg=30,
        speed_factor=1.1,
        version=2,
        enabled=False,
    ))
    db.commit()

    assert latest_candidate_version(db, runner_spot.id) == 1


def test_activation_rejects_a_gate_after_candidate_content_changes(
    db, runner_spot, monkeypatch
):
    _persist_candidate(db, runner_spot.id, "gwa", _ok_result())
    db.commit()
    version = latest_candidate_version(db, runner_spot.id)
    gate_run_id = _authorize_candidate(db, runner_spot.id, version)
    row = db.query(SpotWeatherSector).filter_by(
        profile_id=runner_spot.weather_profile.id,
        version=version,
    ).first()
    row.speed_factor = 1.1
    db.commit()

    events = []
    monkeypatch.setattr(
        "app.weather.sector_activation.logger.warning",
        lambda message, **kwargs: events.append((message, kwargs["extra"])),
    )
    with pytest.raises(ValueError, match="context is stale"):
        activate_spot_sectors(
            db,
            runner_spot.id,
            version,
            actor="test",
            gate_run_id=gate_run_id,
        )

    (message, event), = events
    assert message == "weather_sector_gate_rejected"
    assert event["weather_reason_code"] == "stale_serving_context"
    assert event["weather_spot_id"] == str(runner_spot.id)
    assert event["weather_candidate_version"] == version


def test_activation_requires_a_strictly_positive_mae_drop(db, runner_spot):
    _persist_candidate(db, runner_spot.id, "gwa", _ok_result())
    db.commit()
    version = latest_candidate_version(db, runner_spot.id)
    gate_run_id = _authorize_candidate(db, runner_spot.id, version, drop=0.0)

    with pytest.raises(ValueError, match="must be positive"):
        activate_spot_sectors(
            db,
            runner_spot.id,
            version,
            actor="test",
            gate_run_id=gate_run_id,
        )


def test_activation_serializes_with_a_real_inflight_publisher(
    db, runner_spot, monkeypatch
):
    """Exercise the PostgreSQL row lock and cache-generation fence together.

    The publisher reaches its final promotion lock first. A genuinely separate
    activation session must wait on that database lock, then invalidate the
    snapshot and cache generation after publication commits.
    """
    _persist_candidate(db, runner_spot.id, "gwa", _ok_result())
    db.commit()
    version = latest_candidate_version(db, runner_spot.id)
    gate_run_id = _authorize_candidate(db, runner_spot.id, version)
    cache = InMemoryCache()
    job = enqueue(
        db,
        runner_spot.id,
        reason=f"activation-lock-race-{uuid.uuid4()}",
    )

    publisher_holds_lock = threading.Event()
    release_publisher = threading.Event()
    original_generation = __import__(
        "app.forecast.publisher", fromlist=["public_weather_generation"]
    ).public_weather_generation

    def hold_before_publisher_commit(cache_backend, spot_id):
        publisher_holds_lock.set()
        if not release_publisher.wait(timeout=15):
            raise TimeoutError("publisher race test was not released")
        return original_generation(cache_backend, spot_id)

    monkeypatch.setattr(
        "app.forecast.publisher.public_weather_generation",
        hold_before_publisher_commit,
    )

    publisher_result = {}
    activation_result = {}

    def publish():
        try:
            with SessionLocal() as session:
                publisher_result["value"] = run_job(
                    session,
                    job.id,
                    client=FakeOpenMeteoClient(data_days=11),
                    cache=cache,
                )
        except BaseException as exc:  # surfaced in the main test thread below
            publisher_result["error"] = exc

    application_name = f"weather-activation-race-{uuid.uuid4().hex[:12]}"

    def activate():
        try:
            with SessionLocal() as session:
                session.execute(
                    text("select set_config('application_name', :name, true)"),
                    {"name": application_name},
                )
                activation_result["value"] = activate_spot_sectors(
                    session,
                    runner_spot.id,
                    version,
                    actor="concurrency-test",
                    gate_run_id=gate_run_id,
                    cache=cache,
                )
        except BaseException as exc:  # surfaced in the main test thread below
            activation_result["error"] = exc

    publisher_thread = threading.Thread(target=publish, daemon=True)
    activation_thread = threading.Thread(target=activate, daemon=True)
    publisher_thread.start()
    activation_started = False
    try:
        assert publisher_holds_lock.wait(timeout=15), (
            "publisher never reached the serialized promotion section"
        )
        activation_thread.start()
        activation_started = True

        deadline = time.monotonic() + 10
        activation_waited_on_lock = False
        with SessionLocal() as observer:
            while time.monotonic() < deadline:
                activation_waited_on_lock = bool(
                    observer.scalar(
                        text(
                            "select exists ("
                            "select 1 from pg_stat_activity "
                            "where application_name = :name "
                            "and wait_event_type = 'Lock')"
                        ),
                        {"name": application_name},
                    )
                )
                observer.rollback()
                if activation_waited_on_lock:
                    break
                time.sleep(0.02)
        assert activation_waited_on_lock, (
            "activation did not wait on the publisher's PostgreSQL row lock"
        )
    finally:
        release_publisher.set()
        publisher_thread.join(timeout=20)
        if activation_started:
            activation_thread.join(timeout=20)

    assert not publisher_thread.is_alive()
    assert not activation_started or not activation_thread.is_alive()
    assert "error" not in publisher_result, publisher_result.get("error")
    assert "error" not in activation_result, activation_result.get("error")
    assert publisher_result["value"].status == "succeeded"
    assert activation_result["value"]["activated_version"] == version

    db.expire_all()
    active_snapshot = db.scalar(
        select(ForecastSnapshot).where(
            ForecastSnapshot.spot_id == runner_spot.id,
            ForecastSnapshot.active.is_(True),
        )
    )
    assert active_snapshot is None
    assert get_public_forecast(cache, runner_spot.id) is None
    active_versions = {
        row.version
        for row in db.query(SpotWeatherSector).filter_by(
            profile_id=runner_spot.weather_profile.id,
            enabled=True,
        )
        if is_forecast_sector(row)
    }
    assert active_versions == {version}
