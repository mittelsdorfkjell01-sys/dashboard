"""Persistent exact point evidence; all provider bytes are fixture-generated."""

from datetime import timedelta
from contextlib import nullcontext
from types import SimpleNamespace
import uuid

from sqlalchemy import select

from app.models import WeatherExactModelBundle, WeatherExactModelPoint
from app.weather.exact_points import (
    PersistedStationBaselineLoader,
    load_persisted_exact_baseline,
    persist_exact_point_bundle,
)
from app.weather.live_wind_operations import _exact_point_doctor
from tests.test_exact_run import FIRST_SEEN, OBS, capture_pair, loader


def _sample(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    bundle = exact_loader.bundle(
        valid_at=OBS, latitude=54.2, longitude=10.2, as_of=OBS
    )
    return exact_loader.sample(bundle, latitude=54.2, longitude=10.2)


def test_exact_point_bundle_persists_idempotently_and_loads_as_of(db, tmp_path):
    target_id = uuid.uuid4()
    sampled = _sample(tmp_path)
    first = persist_exact_point_bundle(
        db,
        target_kind="station",
        target_id=target_id,
        latitude=54.2,
        longitude=10.2,
        sampled_for_at=FIRST_SEEN,
        captured_at=FIRST_SEEN,
        baseline=sampled,
    )
    second = persist_exact_point_bundle(
        db,
        target_kind="station",
        target_id=target_id,
        latitude=54.2,
        longitude=10.2,
        sampled_for_at=FIRST_SEEN,
        captured_at=FIRST_SEEN,
        baseline=sampled,
    )
    db.commit()

    assert first["bundle_inserted"] == 1
    assert first["points_inserted"] == 4
    assert second["bundle_inserted"] == 0
    assert second["points_inserted"] == 0
    hidden = load_persisted_exact_baseline(
        db,
        target_kind="station",
        target_id=target_id,
        at=OBS,
        as_of=FIRST_SEEN - timedelta(seconds=1),
    )
    assert not hidden.activation_eligible
    restored = load_persisted_exact_baseline(
        db,
        target_kind="station",
        target_id=target_id,
        at=OBS,
        as_of=OBS,
    )
    assert restored.activation_eligible
    assert restored.bundle_hash == sampled.bundle_hash
    assert restored.dataset_bundle_hash == sampled.dataset_bundle_hash
    assert [point.model_dump() for point in restored.points] == [
        point.model_dump() for point in sampled.points
    ]
    doctor = _exact_point_doctor(db, now=OBS)
    assert doctor["bundles"] >= 1
    assert doctor["points"] >= 4
    assert doctor["latest_capture_at"] is not None


def test_persisted_station_loader_never_fetches_or_uses_late_evidence(db, tmp_path):
    target_id = uuid.uuid4()
    sampled = _sample(tmp_path)
    persist_exact_point_bundle(
        db,
        target_kind="station",
        target_id=target_id,
        latitude=54.2,
        longitude=10.2,
        sampled_for_at=FIRST_SEEN,
        captured_at=FIRST_SEEN,
        baseline=sampled,
    )
    db.commit()
    station = SimpleNamespace(id=target_id)
    observation = SimpleNamespace(observed_at=OBS)
    restored = PersistedStationBaselineLoader(db)(station, observation)
    assert restored.activation_eligible

    point = db.scalar(
        select(WeatherExactModelPoint)
        .join(
            WeatherExactModelBundle,
            WeatherExactModelBundle.id == WeatherExactModelPoint.bundle_id,
        )
        .where(WeatherExactModelBundle.target_id == target_id)
        .limit(1)
    )
    point.sample_hash = "0" * 64
    db.commit()
    rejected = PersistedStationBaselineLoader(db)(station, observation)
    assert not rejected.activation_eligible
    assert not rejected.points


def test_ineligible_or_malformed_bundle_is_not_persisted(db, tmp_path):
    sampled = _sample(tmp_path)
    invalid = sampled.__class__(
        **{**sampled.__dict__, "activation_eligible": False}
    )
    result = persist_exact_point_bundle(
        db,
        target_kind="spot",
        target_id=uuid.uuid4(),
        latitude=54.2,
        longitude=10.2,
        sampled_for_at=FIRST_SEEN,
        captured_at=FIRST_SEEN,
        baseline=invalid,
    )
    assert result == {
        "status": "ineligible", "bundle_inserted": 0, "points_inserted": 0
    }


def test_capture_cycle_persists_bounded_station_and_spot_points(monkeypatch):
    from scripts import exact_run_worker

    station_id, spot_id = uuid.uuid4(), uuid.uuid4()

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class Db:
        calls = 0
        committed = False

        def execute(self, _query):
            self.calls += 1
            return Result(
                [(station_id, 54.2, 10.2)]
                if self.calls == 1
                else [(spot_id, 54.3, 10.3)]
            )

        def begin_nested(self):
            return nullcontext()

        def commit(self):
            self.committed = True

    class Loader:
        def capture(self, **_kwargs):
            return {
                "assets": 6, "cache_hits": 0, "cache_misses": 6,
                "errors": {}, "provider_duration_ms": {},
            }

        def bundle(self, **_kwargs):
            return object()

        def sample(self, _bundle, **_kwargs):
            return object()

    persisted = []

    def persist(_db, **kwargs):
        persisted.append((kwargs["target_kind"], kwargs["target_id"]))
        return {
            "status": "persisted", "bundle_inserted": 1, "points_inserted": 4
        }

    monkeypatch.setattr(exact_run_worker, "persist_exact_point_bundle", persist)
    database = Db()
    report = exact_run_worker.capture_exact_cycle(
        database, Loader(), now=OBS, limit=1, point_limit=2
    )
    assert set(persisted) == {("station", station_id), ("spot", spot_id)}
    assert report["point_samples"] == {
        "targets": 2, "bundles_inserted": 2, "points_inserted": 8,
        "ineligible": 0, "errors": 0,
    }
    assert database.committed
