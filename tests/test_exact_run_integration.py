"""Local Postgres/Redis fixture acceptance; no live weather network or public switch."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import uuid

from geoalchemy2 import WKTElement
import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.db.session import SessionLocal
from app.models import (Region, Spot, WeatherLiveWindJob, WeatherObservation,
                        WeatherStation, WeatherStationModelResidual)
from app.weather.exact_run import ExactRunAssetCache, ExactRunLoader, exact_shadow_baseline
from app.weather.live_wind_jobs import claim_live_wind_job, process_live_wind_job
from app.weather.live_wind_analysis import REGIONAL_LIVE_WIND_VERSION
from app.weather.model_error import (calculate_and_persist_station_model_error,
                                     calculate_station_model_error,
                                     persist_station_model_error)
from app.weather.observation_worker import persist_batch
from app.weather.providers.common import normalize_observation
from app.weather.station_selection import select_stations_for_spot
from app.live.live_wind import load_station_residual_inputs
from tests.test_exact_run import FakeGfs, FakeIcon


def test_import_exact_residual_cross_tile_shadow_and_replay(db, tmp_path, monkeypatch):
    import redis

    redis_client = redis.Redis.from_url(Settings().redis_url, socket_connect_timeout=1)
    try:
        assert redis_client.ping()
    except redis.RedisError:
        pytest.fail("Redis is required for Exact-Run integration acceptance")

    current = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    observed = current.replace(minute=max(0, current.minute - 5))
    first_seen = observed - timedelta(minutes=1)
    run = current.replace(hour=current.hour - current.hour % 6,
                          minute=0) - timedelta(hours=6)
    lead = int((observed - run).total_seconds() // 3600)
    suffix = uuid.uuid4().hex[:12]
    region = Region(slug=f"exact-e2e-{suffix}", name=f"Exact E2E {suffix}",
                    country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"exact-e2e-{suffix}", name=f"Exact E2E Spot {suffix}",
                region_id=region.id, location=WKTElement("POINT(10.2 54.2)", srid=4326),
                status="published", sports=["wind"], water_type=["sea"])
    db.add(spot)
    db.flush()
    station = WeatherStation(
        spot_id=spot.id, provider="dwd", provider_station_id=f"fixture-{suffix}",
        latitude=54.2, longitude=9.9, measurement_height_m=10,
        active=True, approved=True, blocked=False,
        representativeness_status="passed", setting_class="coastal",
    )
    db.add(station)
    db.commit()

    extra_stations = []
    for index, longitude in enumerate((10.35, 10.65), start=2):
        other = WeatherStation(
            spot_id=spot.id, provider="dwd",
            provider_station_id=f"fixture-{suffix}-{index}",
            latitude=54.2, longitude=longitude, measurement_height_m=10,
            active=True, approved=True, blocked=False,
            representativeness_status="passed", setting_class="coastal",
        )
        db.add(other)
        extra_stations.append(other)
    db.commit()

    fake_gfs, fake_icon = FakeGfs(), FakeIcon()
    loader = ExactRunLoader(ExactRunAssetCache(tmp_path), gfs=fake_gfs, icon=fake_icon)
    try:
        row = normalize_observation(
            provider="dwd", station_id=station.provider_station_id,
            observed_at=observed, received_at=current, imported_at=current,
            wind_speed_ms=12, wind_direction_deg=270, provider_quality="good",
            latitude=54.2, longitude=9.9, measurement_height_m=10,
            license="fixture-only", provenance={"fixture": suffix},
        )
        assert row.import_status == "accepted"
        imported = persist_batch(db, station, [row], dry_run=False)
        assert imported["persisted"] == 1
        observation = db.scalar(select(WeatherObservation).where(
            WeatherObservation.station_id == station.id))
        assert observation is not None

        interrupted_key = loader.cache.asset_key(
            model="gfs-0p25", run_at=run, valid_at=run+timedelta(hours=lead),
            dataset_version="GFS 0.25", field="10m_wind_uv",
            domain="gfs-tile:0,10,50,60",
        )
        interrupted_manifest = loader.cache._manifest_path(interrupted_key)
        interrupted_manifest.parent.mkdir(parents=True, exist_ok=True)
        interrupted_manifest.with_name(
            f"{interrupted_key}.part-killed-worker").write_bytes(b"incomplete")

        for longitude in (9.9, 10.2):
            report = loader.capture(run_at=run, forecast_hours=(lead, lead + 1),
                                    latitude=54.2, longitude=longitude,
                                    now=first_seen)
            assert not report["errors"]
        assert interrupted_manifest.is_file()
        station_baseline = loader(station, observation)
        station_bundle = loader.bundle(valid_at=observed, latitude=54.2,
                                       longitude=9.9, as_of=observed)
        target_bundle = loader.bundle(valid_at=current, latitude=54.2,
                                      longitude=10.2, as_of=current)
        assert station_bundle.dataset_bundle_hash == target_bundle.dataset_bundle_hash
        assert station_bundle.bundle_hash != target_bundle.bundle_hash
        assert {p.asset_content_hashes for p in station_baseline.points} != {
            p.asset_content_hashes for p in loader.sample(
                target_bundle, latitude=54.2, longitude=10.2).points
        }
        residual = calculate_and_persist_station_model_error(
            db, station, observation, station_baseline, analyzed_at=current)
        db.commit()
        assert residual.qc_status in {"accepted", "degraded"}
        assert residual.activation_eligible
        assert residual.dataset_bundle_hash == target_bundle.dataset_bundle_hash
        assert residual.sample_hash
        assert residual.residual_vector["u_ms"] == pytest.approx(
            residual.measurement_vector["u_ms"] - residual.expected_station_vector["u_ms"])
        for other in extra_stations:
            other_row = normalize_observation(
                provider="dwd", station_id=other.provider_station_id,
                observed_at=observed, received_at=current, imported_at=current,
                wind_speed_ms=12, wind_direction_deg=270, provider_quality="good",
                latitude=54.2, longitude=other.longitude, measurement_height_m=10,
                license="fixture-only", provenance={"fixture": suffix},
            )
            assert persist_batch(db, other, [other_row], dry_run=False)["persisted"] == 1
            other_observation = db.scalar(select(WeatherObservation).where(
                WeatherObservation.station_id == other.id))
            other_result = calculate_and_persist_station_model_error(
                db, other, other_observation, loader(other, other_observation),
                analyzed_at=current)
            db.commit()
            assert other_result.activation_eligible
            assert other_result.dataset_bundle_hash == residual.dataset_bundle_hash
        selection = select_stations_for_spot(db, spot.id, now=current,
                                             wind_direction_deg=270)
        exact_inputs = load_station_residual_inputs(
            db, selection, target_model_ids=("gfs-0p25", "icon-eu"),
            target_dataset_bundle_hash=target_bundle.dataset_bundle_hash,
            target_dataset_manifest=target_bundle.dataset_manifest,
        )
        assert len(exact_inputs) == 3 and all(item.model_compatible for item in exact_inputs)
        changed_manifest = {**target_bundle.dataset_manifest,
                            "eligibility_class": "availability_unproven"}
        mismatch_diagnostics = {}
        assert not load_station_residual_inputs(
            db, selection, target_model_ids=("gfs-0p25", "icon-eu"),
            target_dataset_bundle_hash=target_bundle.dataset_bundle_hash,
            target_dataset_manifest=changed_manifest,
            diagnostics_out=mismatch_diagnostics,
        )
        assert mismatch_diagnostics["residual_rejection_reasons"] == {
            "dataset_manifest_incompatible": 3,
        }
        stored = db.scalar(select(WeatherStationModelResidual).where(
            WeatherStationModelResidual.observation_id == observation.id))
        original_hash = stored.dataset_bundle_hash
        stored.dataset_bundle_hash = "0" * 64
        db.flush()
        mismatch_diagnostics = {}
        assert len(load_station_residual_inputs(
            db, selection, target_model_ids=("gfs-0p25", "icon-eu"),
            target_dataset_bundle_hash=target_bundle.dataset_bundle_hash,
            target_dataset_manifest=target_bundle.dataset_manifest,
            diagnostics_out=mismatch_diagnostics,
        )) == 2
        assert mismatch_diagnostics["residual_rejection_reasons"] == {
            "dataset_bundle_hash_mismatch": 1,
        }
        stored.dataset_bundle_hash = original_hash
        original_sample_hash = stored.sample_hash
        stored.sample_hash = "0" * 64
        db.flush()
        mismatch_diagnostics = {}
        assert len(load_station_residual_inputs(
            db, selection, target_model_ids=("gfs-0p25", "icon-eu"),
            target_dataset_bundle_hash=target_bundle.dataset_bundle_hash,
            target_dataset_manifest=target_bundle.dataset_manifest,
            diagnostics_out=mismatch_diagnostics,
        )) == 2
        assert mismatch_diagnostics["residual_rejection_reasons"] == {
            "sample_hash_mismatch": 1,
        }
        stored.sample_hash = original_sample_hash
        db.commit()

        # Simulate the boundary between residual persistence and the later
        # shadow worker: no in-process ORM state is carried over.
        db.close()

        job = WeatherLiveWindJob(
            spot_id=spot.id, region_id=region.id, region_key=region.slug,
            cycle_at=current, rollout_stage="shadow",
            analysis_version=REGIONAL_LIVE_WIND_VERSION,
            status="queued", available_at=current,
        )
        db.add(job)
        db.commit()

        def attempt_claim(_):
            with SessionLocal() as worker_db:
                claimed = claim_live_wind_job(worker_db, now=current)
                return str(claimed.id) if claimed is not None else None

        with ThreadPoolExecutor(max_workers=2) as pool:
            claimed_ids = list(pool.map(attempt_claim, range(2)))
        assert claimed_ids.count(str(job.id)) == 1
        assert claimed_ids.count(None) == 1
        db.refresh(job)
        assert job.status == "processing" and job.worker_token is not None

        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return current if tz is not None else current.replace(tzinfo=None)

        monkeypatch.setattr("app.weather.live_wind_jobs.datetime", FrozenDatetime)
        monkeypatch.setattr("app.weather.exact_run.ExactRunLoader", lambda _cache: loader)
        result = process_live_wind_job(
            db, job, settings=Settings(app_env="test", live_wind_rollout_stage="shadow",
                                       live_wind_exact_run_cache_dir=str(tmp_path)))
        assert result["status"] == "succeeded", result
        db.refresh(job)
        assert job.diagnostics["activation_eligible"]
        assert job.diagnostics["dataset_bundle_hash"] == residual.dataset_bundle_hash
        assert job.diagnostics["sample_hash"] != residual.sample_hash
        assert job.diagnostics["baseline_source"] == "exact_run_bundle"
        assert job.diagnostics["forbidden_inputs"] == [
            "raw_station_measurement", "forecast_output"]
        assert job.result_payload["status"] == "station_adjusted"
        assert job.station_count >= 2
        assert any(item.get("observation_id") == str(observation.id)
                   and item.get("analysis_id") == residual.analysis_id
                   and not item.get("exclusion_reasons")
                   for item in job.result_payload.get("station_contributions", []))
        assert all(source.get("source") != "open_meteo_current"
                   for source in job.result_payload.get("sources", []))

        # Replay both imports and immutable evidence; the completed job is not
        # claimed/published again, even after a simulated worker restart.
        assert persist_batch(db, station, [row], dry_run=False)["persisted"] == 0
        second_capture = loader.capture(run_at=run, forecast_hours=(lead, lead + 1),
                                        latitude=54.2, longitude=9.9, now=first_seen)
        assert second_capture["cache_hits"] == 6
        target_replay = loader.capture(run_at=run, forecast_hours=(lead, lead + 1),
                                       latitude=54.2, longitude=10.2, now=first_seen)
        assert target_replay["cache_hits"] == 6
        assert len(list((tmp_path / "manifests").glob("*/*.json"))) == 8
        second = calculate_and_persist_station_model_error(
            db, station, observation, loader(station, observation), analyzed_at=current)
        db.commit()
        assert second.analysis_id == residual.analysis_id
        assert second.sample_hash == residual.sample_hash
        assert second.residual_vector == residual.residual_vector
        assert db.scalar(select(func.count()).select_from(WeatherObservation).where(
            WeatherObservation.station_id == station.id)) == 1
        assert db.scalar(select(func.count()).select_from(WeatherStationModelResidual).where(
            WeatherStationModelResidual.observation_id == observation.id)) == 1
        assert db.scalar(select(func.count()).select_from(WeatherLiveWindJob).where(
            WeatherLiveWindJob.spot_id == spot.id)) == 1
        repeated_target, repeated_bundle = exact_shadow_baseline(
            loader, db.get(Spot, spot.id), at=current)
        assert repeated_bundle.dataset_bundle_hash == target_bundle.dataset_bundle_hash
        assert repeated_target["_exact_sample_hash"] == job.diagnostics["sample_hash"]
        assert repeated_target["model_baseline_u_ms"] == pytest.approx(
            job.result_payload["model_baseline_u_ms"])
        assert repeated_target["model_baseline_v_ms"] == pytest.approx(
            job.result_payload["model_baseline_v_ms"])
        assert claim_live_wind_job(db, now=current) is None
    finally:
        db.rollback()
        db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()


@pytest.mark.parametrize("failure", [
    "gfs_missing", "icon_missing", "cache_corrupted",
    "historical_availability_unproven", "legacy_capture_time",
])
def test_exact_failures_persist_only_ineligible_evidence(db, tmp_path, failure):
    current = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    observed = current.replace(minute=max(0, current.minute - 5))
    run = current.replace(hour=current.hour - current.hour % 6,
                          minute=0) - timedelta(hours=6)
    lead = int((observed - run).total_seconds() // 3600)
    suffix = uuid.uuid4().hex[:12]
    region = Region(slug=f"exact-failure-{suffix}", name=f"Exact Failure {suffix}",
                    country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"exact-failure-{suffix}", name=f"Exact Failure Spot {suffix}",
                region_id=region.id, location=WKTElement("POINT(10.2 54.2)", srid=4326),
                status="published", sports=["wind"])
    db.add(spot)
    db.flush()
    station = WeatherStation(
        spot_id=spot.id, provider="dwd", provider_station_id=f"fixture-{suffix}",
        latitude=54.2, longitude=10.2, active=True, approved=True,
        blocked=False, representativeness_status="passed",
    )
    db.add(station)
    db.commit()
    try:
        row = normalize_observation(
            provider="dwd", station_id=station.provider_station_id,
            observed_at=observed, received_at=current, imported_at=current,
            wind_speed_ms=12, wind_direction_deg=270, provider_quality="good",
            latitude=54.2, longitude=10.2,
        )
        assert persist_batch(db, station, [row], dry_run=False)["persisted"] == 1
        observation = db.scalar(select(WeatherObservation).where(
            WeatherObservation.station_id == station.id))
        gfs, icon = FakeGfs(), FakeIcon()
        if failure == "gfs_missing":
            gfs.fail = True
        if failure == "icon_missing":
            icon.download = lambda _url: (_ for _ in ()).throw(RuntimeError("offline"))
        loader = ExactRunLoader(ExactRunAssetCache(tmp_path), gfs=gfs, icon=icon)
        captured_at = (observed + timedelta(minutes=1)
                       if failure == "historical_availability_unproven"
                       else observed - timedelta(minutes=1))
        loader.capture(run_at=run, forecast_hours=(lead, lead + 1),
                       latitude=54.2, longitude=10.2, now=captured_at)
        if failure == "cache_corrupted":
            bundle = loader.bundle(valid_at=observed, latitude=54.2,
                                   longitude=10.2, as_of=observed)
            asset = bundle.members["gfs-0p25"]["assets"][0]
            loader.cache._object_path(asset["content_sha256"]).write_bytes(b"truncated")
        baseline = loader(station, observation)
        if failure == "legacy_capture_time":
            baseline = replace(baseline, baseline_version="exact-run-bundle-v1",
                               points=tuple(point.model_copy(update={
                                   "baseline_version": "exact-run-bundle-v1"
                               }) for point in baseline.points))
        result = calculate_station_model_error(
            station, observation, baseline, analyzed_at=current)
        assert result.qc_status in {"rejected", "unavailable"}
        assert not result.activation_eligible
        persist_station_model_error(db, result)
        db.commit()
        stored = db.scalar(select(WeatherStationModelResidual).where(
            WeatherStationModelResidual.observation_id == observation.id))
        assert stored is not None and not stored.activation_eligible
        assert stored.qc_status in {"rejected", "unavailable"}
        assert db.scalar(select(func.count()).select_from(WeatherStationModelResidual).where(
            WeatherStationModelResidual.observation_id == observation.id)) == 1
    finally:
        db.rollback()
        db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()
