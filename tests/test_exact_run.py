"""Deterministic exact-run evidence tests; no external weather service required."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
import uuid

import pytest

from app.forecast.contracts import GridPoint, NormalizedModelValue
from app.forecast.providers import DwdIconProvider
from app.config import Settings
from app.weather.exact_run import (
    EXACT_BUNDLE_VERSION,
    ExactAssetError,
    ExactRunAssetCache,
    ExactRunLoader,
    exact_shadow_baseline,
    gfs_tile,
    compatible_dataset_manifests,
    exact_cache_preflight,
)
from app.weather.model_error import StationModelBaseline, calculate_station_model_error
from app.weather.live_wind_rollout import verification_evidence_reasons
from app.weather.vectors import uv_to_wind, wind_to_uv


UTC = timezone.utc
RUN = datetime(2026, 9, 16, 6, tzinfo=UTC)
OBS = RUN + timedelta(hours=6, minutes=30)
FIRST_SEEN = RUN + timedelta(hours=6, minutes=10)


class FakeGfs:
    def __init__(self):
        self.downloads = 0
        self.fail = False

    def subset_source(self, run_at, hour, bounds):
        return f"fixture:gfs:{run_at.isoformat()}:{hour}:{bounds}", {}

    def download_subset(self, run_at, hour, bounds):
        self.downloads += 1
        if self.fail:
            raise RuntimeError("offline")
        return self.subset_source(run_at, hour, bounds)[0], b"GRIB" + json.dumps({
            "hour": hour, "u": 8.0 if hour == 6 else 10.0, "v": -1.0,
        }).encode() + b"7777"

    def parse_grib(self, data, request, hour):
        value = json.loads(data[4:-4])
        speed, direction = uv_to_wind(value["u"], value["v"])
        return NormalizedModelValue(
            provider="NOAA/NCEP", model="gfs-0p25", dataset_version="GFS 0.25",
            model_run=request.run_at, valid_at=request.run_at+timedelta(hours=hour),
            fetched_at=FIRST_SEEN,
            grid_point=GridPoint(latitude=round(request.latitude*4)/4,
                                 longitude=round(request.longitude*4)/4, distance_km=0),
            horizontal_resolution_km=25, horizon_hours=hour,
            u_ms=value["u"], v_ms=value["v"], speed_ms=speed,
            direction_deg=direction, source_key="fixture:gfs",
        )


class FakeIcon:
    def __init__(self):
        self.downloads = 0

    def file_url(self, model, run_at, field, hour):
        return f"fixture:icon:{run_at.isoformat()}:{field}:{hour}"

    def download(self, url):
        self.downloads += 1
        field, hour = url.rsplit(":", 2)[-2:]
        value = (6.0 if int(hour) == 6 else 8.0) if field == "u_10m" else -1.0
        return b"GRIB" + json.dumps({"value": value}).encode() + b"7777"

    def nearest_exact_grid(self, data, latitude, longitude):
        return json.loads(data[4:-4])["value"], round(latitude*4)/4, round(longitude*4)/4


def loader(tmp_path):
    gfs, icon = FakeGfs(), FakeIcon()
    return ExactRunLoader(ExactRunAssetCache(tmp_path), gfs=gfs, icon=icon), gfs, icon


def capture_pair(exact_loader, *, first_seen=FIRST_SEEN, run=RUN):
    return exact_loader.capture(run_at=run, forecast_hours=(6, 7),
                                latitude=54.2, longitude=10.2, now=first_seen)


def test_exact_bundle_is_first_seen_as_of_and_idempotently_cached(tmp_path):
    exact_loader, gfs, icon = loader(tmp_path)
    assert capture_pair(exact_loader)["assets"] == 6
    before = exact_loader.bundle(valid_at=OBS, latitude=54.2, longitude=10.2,
                                 as_of=FIRST_SEEN-timedelta(seconds=1))
    assert not before.activation_eligible
    assert set(before.statuses.values()) == {"run_not_available_as_of_observation"}
    after = exact_loader.bundle(valid_at=OBS, latitude=54.2, longitude=10.2,
                                as_of=OBS)
    assert after.activation_eligible
    assert after.version == EXACT_BUNDLE_VERSION
    assert len(after.members["icon-eu"]["assets"]) == 4
    assert len(after.members["gfs-0p25"]["assets"]) == 2
    assert capture_pair(exact_loader)["cache_hits"] == 6
    assert (gfs.downloads, icon.downloads) == (2, 4)
    assert after.bundle_hash == exact_loader.bundle(
        valid_at=OBS-timedelta(minutes=15), latitude=54.2, longitude=10.2,
        as_of=OBS,
    ).bundle_hash


def test_station_and_target_share_exact_bundle_and_uv_residual(tmp_path, monkeypatch):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    station = SimpleNamespace(
        id=uuid.uuid4(), latitude=54.2, longitude=10.2,
        active=True, approved=True, blocked=False,
        representativeness_status="passed",
    )
    measured_u, measured_v = wind_to_uv(12, 270)
    observation = SimpleNamespace(
        id=uuid.uuid4(), station_id=station.id, observed_at=OBS,
        wind_speed_ms=12, wind_direction_deg=270,
        wind_u_ms=measured_u, wind_v_ms=measured_v,
        wind_gust_ms=None, gust_period_seconds=None,
        provider_quality="good", import_status="accepted",
    )
    sampled = exact_loader(station, observation)
    assert sampled.activation_eligible
    assert len(sampled.points) == 4
    assert all(point.available_at <= OBS for point in sampled.points)
    assert all(point.sampling_method == "nearest_grid" for point in sampled.points)
    result = calculate_station_model_error(
        station, observation, sampled, analyzed_at=OBS+timedelta(minutes=1),
    )
    assert result.qc_status in {"accepted", "degraded"}
    assert result.baseline_bundle_hash == sampled.bundle_hash
    assert result.activation_eligible
    assert result.residual_vector["u_ms"] == pytest.approx(
        result.measurement_vector["u_ms"]-result.expected_station_vector["u_ms"]
    )
    repeated = calculate_station_model_error(
        station, observation, exact_loader(station, observation),
        analyzed_at=OBS+timedelta(minutes=2),
    )
    assert repeated.analysis_id == result.analysis_id
    assert repeated.residual_vector == result.residual_vector
    monkeypatch.setattr("app.live.service._spot_coords", lambda _: (54.3, 10.3))
    baseline, target_bundle = exact_shadow_baseline(
        exact_loader, SimpleNamespace(weather_profile=None), at=OBS,
    )
    assert target_bundle.bundle_hash == sampled.bundle_hash
    assert baseline["_exact_bundle_hash"] == sampled.bundle_hash
    assert baseline["status"] == "baseline"
    assert baseline["sources"][0]["source"] == "exact_run_bundle"

    # An exact bundle cannot silently degrade to one model at the station.
    distant = StationModelBaseline(
        points=tuple(point.model_copy(update={"grid_distance_km": 500.0})
                     if point.model_id == "icon-eu" else point for point in sampled.points),
        expected_model_ids=sampled.expected_model_ids,
        baseline_version=sampled.baseline_version,
        bundle_hash=sampled.bundle_hash,
        bundle_manifest=sampled.bundle_manifest,
        dataset_bundle_hash=sampled.dataset_bundle_hash,
        dataset_manifest=sampled.dataset_manifest,
        activation_eligible=True,
        member_statuses=sampled.member_statuses,
    )
    rejected = calculate_station_model_error(
        station, observation, distant, analyzed_at=OBS+timedelta(minutes=1),
    )
    assert rejected.qc_status == "unavailable"
    assert "model_grid_too_distant:icon-eu" in rejected.qc_reasons


def test_different_tiles_share_dataset_but_not_assets_or_samples(tmp_path, monkeypatch):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    exact_loader.capture(run_at=RUN, forecast_hours=(6, 7), latitude=54.2,
                         longitude=9.9, now=FIRST_SEEN)
    station_bundle = exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                         longitude=9.9, as_of=OBS)
    target_bundle = exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                        longitude=10.2, as_of=OBS)
    assert station_bundle.activation_eligible and target_bundle.activation_eligible
    assert station_bundle.dataset_bundle_hash == target_bundle.dataset_bundle_hash
    assert station_bundle.bundle_hash != target_bundle.bundle_hash
    station = exact_loader.sample(station_bundle, latitude=54.2, longitude=9.9)
    target = exact_loader.sample(target_bundle, latitude=54.2, longitude=10.2)
    assert {p.asset_content_hashes for p in station.points} != {
        p.asset_content_hashes for p in target.points
    }
    assert {p.sample_hash for p in station.points} != {p.sample_hash for p in target.points}


def test_legacy_cache_manifest_cannot_prove_availability(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    asset = exact_loader.bundle(valid_at=OBS, latitude=54.2, longitude=10.2,
                                as_of=OBS).members["gfs-0p25"]["assets"][0]
    path = exact_loader.cache._manifest_path(asset["key"])
    legacy = json.loads(path.read_text(encoding="utf-8"))
    for name in ("first_seen_at", "retrieval_started_at", "retrieval_completed_at",
                 "availability_basis", "asset_content_hash"):
        legacy.pop(name, None)
    path.write_text(json.dumps(legacy), encoding="utf-8")
    assert not exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                   longitude=10.2, as_of=OBS).activation_eligible


def test_interrupted_download_orphan_is_ignored_on_restart(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    key = exact_loader.cache.asset_key(
        model="gfs-0p25", run_at=RUN, valid_at=RUN+timedelta(hours=6),
        dataset_version="GFS 0.25", field="10m_wind_uv",
        domain="gfs-tile:10,20,50,60",
    )
    manifest = exact_loader.cache._manifest_path(key)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    orphan = manifest.with_name(f"{key}.part-interrupted")
    orphan.write_bytes(b"incomplete")
    restarted, _, _ = loader(tmp_path)
    restarted.capture(run_at=RUN, forecast_hours=(6,), latitude=54.2,
                      longitude=10.2, now=FIRST_SEEN)
    assert manifest.is_file()
    assert len(list(manifest.parent.glob(f"{key}.json"))) == 1
    assert restarted.cache.read(key) is not None
    assert restarted.capture(run_at=RUN, forecast_hours=(6,), latitude=54.2,
                             longitude=10.2, now=FIRST_SEEN)["cache_hits"] == 3


def test_persistent_runner_rejects_unmounted_cache(tmp_path):
    assert exact_cache_preflight(tmp_path)["persistent_mount_verified"] is False
    with pytest.raises(ValueError, match="exact_run_cache_not_a_linux_mount"):
        exact_cache_preflight(tmp_path, require_persistent=True,
                              expected_id="fixture-cache")


def test_completion_after_observation_does_not_prove_availability(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    asset = exact_loader.bundle(valid_at=OBS, latitude=54.2, longitude=10.2,
                                as_of=OBS).members["gfs-0p25"]["assets"][0]
    path = exact_loader.cache._manifest_path(asset["key"])
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["retrieval_completed_at"] = (OBS+timedelta(minutes=1)).isoformat()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                   longitude=10.2, as_of=OBS).activation_eligible


@pytest.mark.parametrize("member,field,value", [
    ("gfs-0p25", "provider", "other"),
    ("gfs-0p25", "run_at", "2026-09-16T00:00:00+00:00"),
    ("gfs-0p25", "dataset_version", "GFS-other"),
    ("gfs-0p25", "valid_times", ["2026-09-16T12:00:00+00:00"]),
    ("icon-eu", "required_fields", ["u_10m"]),
])
def test_manifest_compatibility_rejects_semantic_differences(tmp_path, member, field, value):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    manifest = exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                   longitude=10.2, as_of=OBS).dataset_manifest
    modified = json.loads(json.dumps(manifest))
    modified["members"][member][field] = value
    assert not compatible_dataset_manifests(manifest, modified)
    modified = json.loads(json.dumps(manifest))
    modified["eligibility_class"] = "availability_unproven"
    assert not compatible_dataset_manifests(manifest, modified)


def test_station_result_rejects_point_from_another_run(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    station = SimpleNamespace(id=uuid.uuid4(), latitude=54.2, longitude=10.2,
                              active=True, approved=True, blocked=False,
                              representativeness_status="passed")
    u_ms, v_ms = wind_to_uv(12, 270)
    observation = SimpleNamespace(id=uuid.uuid4(), station_id=station.id,
                                  observed_at=OBS, wind_speed_ms=12,
                                  wind_direction_deg=270, wind_u_ms=u_ms,
                                  wind_v_ms=v_ms, provider_quality="good",
                                  import_status="accepted")
    baseline = exact_loader(station, observation)
    wrong = replace(baseline, points=(
        baseline.points[0].model_copy(update={"model_run_at": RUN-timedelta(hours=6)}),
        *baseline.points[1:],
    ))
    result = calculate_station_model_error(station, observation, wrong,
                                           analyzed_at=OBS+timedelta(minutes=1))
    assert result.qc_status == "rejected"
    assert "dataset_point_mismatch" in result.qc_reasons


def test_legacy_v1_baseline_is_invalid_for_activation(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    station = SimpleNamespace(id=uuid.uuid4(), latitude=54.2, longitude=10.2,
                              active=True, approved=True, blocked=False,
                              representativeness_status="passed")
    u_ms, v_ms = wind_to_uv(12, 270)
    observation = SimpleNamespace(id=uuid.uuid4(), station_id=station.id,
                                  observed_at=OBS, wind_speed_ms=12,
                                  wind_direction_deg=270, wind_u_ms=u_ms,
                                  wind_v_ms=v_ms, provider_quality="good",
                                  import_status="accepted")
    baseline = exact_loader(station, observation)
    legacy = replace(baseline, baseline_version="exact-run-bundle-v1",
                     points=tuple(point.model_copy(update={
                         "baseline_version": "exact-run-bundle-v1"
                     }) for point in baseline.points))
    result = calculate_station_model_error(station, observation, legacy,
                                           analyzed_at=OBS+timedelta(minutes=1))
    assert result.qc_status == "rejected"
    assert not result.activation_eligible
    assert "legacy_capture_time_baseline" in result.qc_reasons


def test_dependency_outages_fail_preflight_closed(tmp_path, monkeypatch):
    from scripts import exact_run_preflight as preflight
    from sqlalchemy import create_engine

    monkeypatch.setattr(preflight, "get_settings", lambda: Settings(
        app_env="test", live_wind_exact_run_cache_dir=str(tmp_path),
        database_url="postgresql+psycopg://surf:surf@127.0.0.1:1/surfwind_test",
        redis_url="redis://127.0.0.1:1/0",
    ))
    unreachable_engine = create_engine(
        "postgresql+psycopg://surf:surf@127.0.0.1:1/surfwind_test",
        connect_args={"connect_timeout": 1},
    )
    monkeypatch.setattr(preflight, "engine", unreachable_engine)
    try:
        report = preflight.run_preflight(require_test_database=True)
    finally:
        unreachable_engine.dispose()
    assert report["status"] == "failed"
    assert any(reason.startswith("postgresql_unavailable") for reason in report["errors"])
    assert any(reason.startswith("redis_unavailable") for reason in report["errors"])


def test_cache_preflight_rejects_redirected_directory(tmp_path):
    import pytest
    from app.weather.exact_run import exact_cache_preflight

    target = tmp_path / "cache"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink_or_redirected"):
        exact_cache_preflight(alias)


def test_canary_preflight_rejects_non_linux_even_with_dependencies_down(tmp_path, monkeypatch):
    from scripts import exact_run_preflight as preflight

    monkeypatch.setattr(preflight, "get_settings", lambda: Settings(
        app_env="test", live_wind_exact_run_cache_dir=str(tmp_path),
        database_url="postgresql+psycopg://surf:surf@127.0.0.1:1/surfwind_test",
        redis_url="redis://127.0.0.1:1/0",
    ))
    monkeypatch.setattr(preflight.platform, "system", lambda: "Windows")
    monkeypatch.setenv("LIVE_WIND_ENDPOINT", "https://production.example/cron/live-wind")
    result = preflight.run_preflight(canary=True)
    assert result["status"] == "failed"
    assert "canary_requires_linux" in result["errors"]
    assert "canary_staging_database_identity_mismatch" in result["errors"]
    assert "canary_persistence_not_verified" in result["errors"]
    assert "canary_nonlocal_endpoint:LIVE_WIND_ENDPOINT" in result["errors"]


def test_cache_probe_survives_separate_process_and_checks_external_checksum(tmp_path):
    import json
    import os
    import subprocess
    import sys
    import pytest

    if os.name != "posix":
        pytest.skip("POSIX flock and separate Linux worker processes required")
    code = (
        "import json,os; from scripts.exact_run_preflight import cache_persistence_probe; "
        "print(json.dumps(cache_persistence_probe(os.environ['PROBE_CACHE'], "
        "mode=os.environ['PROBE_MODE'], expected_id='cache-1', "
        "require_new_job=os.environ['PROBE_MODE']=='verify', "
        "expected_sha256=os.environ.get('PROBE_SHA'))))"
    )
    env = {**os.environ, "PROBE_CACHE": str(tmp_path),
           "LIVE_WIND_CANARY_RUNNER_ID": "runner-1",
           "LIVE_WIND_RUNNER_JOB_ID": "job-1", "PROBE_MODE": "create"}
    created = json.loads(subprocess.check_output([sys.executable, "-c", code], env=env, text=True))
    env.update({"LIVE_WIND_RUNNER_JOB_ID": "job-2", "PROBE_MODE": "verify",
                "PROBE_SHA": created["checksum_sha256"]})
    verified = json.loads(subprocess.check_output([sys.executable, "-c", code], env=env, text=True))
    assert verified["checksum_sha256"] == created["checksum_sha256"]
    assert verified["runner_job_restart_verified"] is True
    assert verified["host_restart_verified"] is False
    env["PROBE_SHA"] = "0" * 64
    assert subprocess.run([sys.executable, "-c", code], env=env,
                          capture_output=True, text=True).returncode != 0


def test_cross_run_bracket_and_missing_provider_do_not_fallback(tmp_path):
    exact_loader, _, icon = loader(tmp_path)
    exact_loader.capture(run_at=RUN, forecast_hours=(6,),
                         latitude=54.2, longitude=10.2, now=FIRST_SEEN)
    exact_loader.capture(run_at=RUN+timedelta(hours=6), forecast_hours=(1,),
                         latitude=54.2, longitude=10.2, now=FIRST_SEEN)
    bundle = exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                 longitude=10.2, as_of=OBS)
    assert not bundle.activation_eligible
    assert all(status == "cross_run_interpolation_rejected" for status in bundle.statuses.values())
    icon.download = lambda _: (_ for _ in ()).throw(RuntimeError("offline"))
    report = exact_loader.capture(run_at=RUN, forecast_hours=(7,),
                                  latitude=54.2, longitude=10.2, now=FIRST_SEEN)
    assert "icon-eu" in report["errors"]
    assert not exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                   longitude=10.2, as_of=OBS).activation_eligible


def test_newer_run_seen_after_observation_is_not_retroactively_selected(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    earlier = exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                  longitude=10.2, as_of=OBS)
    newer_run = RUN + timedelta(hours=6)
    exact_loader.capture(run_at=newer_run, forecast_hours=(0, 1),
                         latitude=54.2, longitude=10.2,
                         now=OBS+timedelta(hours=1))
    late_import = exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                      longitude=10.2, as_of=OBS)
    assert late_import.bundle_hash == earlier.bundle_hash
    assert all(member["run_at"] == RUN.isoformat()
               for member in late_import.members.values())


def test_exact_valid_time_uses_single_point_per_model(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    exact_loader.capture(run_at=RUN, forecast_hours=(6,),
                         latitude=54.2, longitude=10.2, now=FIRST_SEEN)
    at = RUN + timedelta(hours=6, minutes=20)
    valid = RUN + timedelta(hours=6)
    bundle = exact_loader.bundle(valid_at=valid, latitude=54.2,
                                 longitude=10.2, as_of=at)
    assert bundle.activation_eligible
    assert all(member["valid_times"] == [valid.isoformat()]
               for member in bundle.members.values())
    sampled = exact_loader.sample(bundle, latitude=54.2, longitude=10.2)
    assert len(sampled.points) == 2


def test_direction_crossing_interpolates_vectors_not_angles(tmp_path):
    exact_loader, gfs, icon = loader(tmp_path)
    original_gfs = gfs.download_subset

    def gfs_crossing(run_at, hour, bounds):
        source, _ = original_gfs(run_at, hour, bounds)
        u, v = wind_to_uv(10, 359 if hour == 6 else 1)
        return source, b"GRIB" + json.dumps({"hour": hour, "u": u, "v": v}).encode() + b"7777"

    def icon_crossing(url):
        field, hour = url.rsplit(":", 2)[-2:]
        u, v = wind_to_uv(10, 359 if int(hour) == 6 else 1)
        value = u if field == "u_10m" else v
        return b"GRIB" + json.dumps({"value": value}).encode() + b"7777"

    gfs.download_subset = gfs_crossing
    icon.download = icon_crossing
    capture_pair(exact_loader)
    station = SimpleNamespace(latitude=54.2, longitude=10.2)
    observation = SimpleNamespace(observed_at=OBS)
    sampled = exact_loader(station, observation)
    from app.weather.model_error import DEFAULT_MODEL_ERROR_POLICY, _interpolate_member
    for model in ("gfs-0p25", "icon-eu"):
        member, error = _interpolate_member(
            [point for point in sampled.points if point.model_id == model],
            OBS, policy=DEFAULT_MODEL_ERROR_POLICY,
        )
        assert error is None
        speed, direction = uv_to_wind(member.u_ms, member.v_ms)
        assert speed == pytest.approx(10, abs=0.01)
        assert min(direction, 360-direction) < 0.01


def test_cache_failure_does_not_publish_and_corruption_is_visible(tmp_path):
    exact_loader, gfs, _ = loader(tmp_path)
    gfs.fail = True
    report = exact_loader.capture(run_at=RUN, forecast_hours=(6,),
                                  latitude=54.2, longitude=10.2, now=FIRST_SEEN)
    assert "gfs-0p25" in report["errors"]
    assert not exact_loader.bundle(valid_at=RUN+timedelta(hours=6),
                                   latitude=54.2, longitude=10.2,
                                   as_of=OBS).activation_eligible
    gfs.fail = False
    capture_pair(exact_loader)
    bundle = exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                 longitude=10.2, as_of=OBS)
    asset = bundle.members["gfs-0p25"]["assets"][0]
    exact_loader.cache._object_path(asset["content_sha256"]).write_bytes(b"corrupt")
    sampled = exact_loader.sample(bundle, latitude=54.2, longitude=10.2)
    assert not sampled.activation_eligible
    assert sampled.member_statuses["gfs-0p25"] == "checksum_mismatch"


def test_malformed_grib_is_not_published_as_an_exact_asset(tmp_path):
    exact_loader, gfs, _ = loader(tmp_path)
    gfs.download_subset = lambda run_at, hour, bounds: ("fixture:html", b"<html>error</html>")
    report = exact_loader.capture(run_at=RUN, forecast_hours=(6,),
                                  latitude=54.2, longitude=10.2, now=FIRST_SEEN)
    assert report["errors"]["gfs-0p25"][0]["status"] == "cache_incomplete"
    assert not exact_loader.bundle(valid_at=RUN+timedelta(hours=6),
                                   latitude=54.2, longitude=10.2,
                                   as_of=OBS).activation_eligible


def test_bundle_manifest_copy_and_tamper_detection(tmp_path):
    exact_loader, _, _ = loader(tmp_path)
    capture_pair(exact_loader)
    bundle = exact_loader.bundle(valid_at=OBS, latitude=54.2,
                                 longitude=10.2, as_of=OBS)
    external = bundle.manifest()
    external["members"].clear()
    assert bundle.members
    bundle.members["gfs-0p25"]["run_id"] = "tampered"
    sampled = exact_loader.sample(bundle, latitude=54.2, longitude=10.2)
    assert not sampled.activation_eligible
    assert set(sampled.member_statuses.values()) == {"checksum_mismatch"}


def test_parallel_capture_has_one_writer_and_stable_manifest(tmp_path):
    exact_loader, gfs, _ = loader(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assets = list(pool.map(lambda _: exact_loader.cache.capture(
            model="gfs-0p25", run_at=RUN, valid_at=RUN+timedelta(hours=6),
            field="10m_wind_uv", domain="gfs-tile:10,20,50,60",
            source_id="fixture:one", provider="NOAA", grid_definition="fixture",
            downloader=lambda: b"one", now=FIRST_SEEN,
        ), range(4)))
    assert len({asset.content_sha256 for asset in assets}) == 1
    assert len({asset.available_at for asset in assets}) == 1
    assert sum(asset.cache_hit for asset in assets) == 3
    assert gfs.downloads == 0
    with pytest.raises(ExactAssetError, match="checksum_mismatch"):
        exact_loader.cache.capture(
            model="gfs-0p25", run_at=RUN, valid_at=RUN+timedelta(hours=6),
            field="10m_wind_uv", domain="gfs-tile:10,20,50,60",
            source_id="fixture:one", provider="NOAA", grid_definition="fixture",
            downloader=lambda: b"changed", now=FIRST_SEEN, refresh=True,
        )
    assert exact_loader.cache.conflicted(assets[0].key)
    assert exact_loader.bundle(valid_at=RUN+timedelta(hours=6),
                               latitude=54.2, longitude=10.2,
                               as_of=OBS).statuses["gfs-0p25"] == "checksum_mismatch"


def test_gfs_tile_is_canonical_across_dateline():
    assert gfs_tile(54.2, -1.8) == gfs_tile(54.2, 358.2)


def test_western_longitude_grid_is_normalized_without_changing_source_cell(tmp_path):
    exact_loader, gfs, _ = loader(tmp_path)
    original_parse = gfs.parse_grib

    def western_parse(data, request, hour):
        value = original_parse(data, request, hour)
        return value.model_copy(update={
            "grid_point": GridPoint(latitude=54.25, longitude=358.25, distance_km=0),
        })

    gfs.parse_grib = western_parse
    exact_loader.capture(run_at=RUN, forecast_hours=(6,),
                         latitude=54.2, longitude=-1.8, now=FIRST_SEEN)
    bundle = exact_loader.bundle(valid_at=RUN+timedelta(hours=6),
                                 latitude=54.2, longitude=-1.8, as_of=OBS)
    sampled = exact_loader.sample(bundle, latitude=54.2, longitude=-1.8)
    point = next(point for point in sampled.points if point.model_id == "gfs-0p25")
    assert point.longitude == pytest.approx(-1.75)
    assert point.source_cells["u"]["source_cell"][1] == pytest.approx(358.25)


def test_legacy_capture_time_evidence_cannot_pass_activation_gate():
    evidence = SimpleNamespace(
        policy={"baseline_source": "capture_time_nowcast"},
        matched_samples=1000, distinct_days=30, distinct_stations=100,
        metrics={"activation": {"uv_mae_drop_ms": 2.0, "ci_lower_ms": 1.0}},
    )
    db = SimpleNamespace(scalar=lambda _: evidence)
    cfg = Settings(
        live_wind_require_verification_evidence=True,
        live_wind_verification_context_hash="fixture",
    )
    assert "legacy_capture_time_baseline" in verification_evidence_reasons(db, settings=cfg)


def test_internal_icon_sampler_decodes_a_real_small_grib_message():
    eccodes = pytest.importorskip("eccodes")
    gid = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        count = eccodes.codes_get(gid, "numberOfPoints")
        eccodes.codes_set_array(gid, "values", [7.5] * count)
        message = eccodes.codes_get_message(gid)
    finally:
        eccodes.codes_release(gid)
    value, lat, lon = DwdIconProvider.nearest_exact_grid(message, 54.0, 10.0)
    assert value == pytest.approx(7.5)
    assert abs(lat-54.0) <= 2.0
    assert abs(lon-10.0) <= 2.0
