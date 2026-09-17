from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

from geoalchemy2 import WKTElement
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import (
    Region, Spot, WeatherLiveWindHoldoutCase, WeatherLiveWindJob,
    WeatherObservation, WeatherStation,
)
from app.weather.exact_run import ExactRunAssetCache, ExactRunLoader
from app.weather.exact_run import (
    EXACT_DATASET_MANIFEST_VERSION, EXACT_LOADER_VERSION, EXACT_BUNDLE_VERSION,
    EXPECTED_MODELS,
)
from app.weather.live_wind_holdouts import (
    _engine_hash, _hash, _station_history_reasons, _training_reasons, audit_holdout_inputs,
    audit_persisted_case, build_live_wind_holdout_cases, exclude_target_dependence,
    holdout_status,
    verify_persisted_holdouts,
)
from app.weather.live_wind_analysis import REGIONAL_LIVE_WIND_VERSION
from app.weather.live_wind_operations import _holdout_readiness
from app.weather.live_wind_verification import LiveWindVerificationPolicy
from app.config import Settings
from app.weather.model_error import calculate_and_persist_station_model_error
from app.weather.observation_worker import persist_batch
from app.weather.providers.common import normalize_observation
from tests.test_exact_run import FakeGfs, FakeIcon

AT = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)


def station(*, latitude=54.0, wigos=None, group=None, dependent=()):
    return SimpleNamespace(
        id=uuid.uuid4(), provider="test", provider_station_id=uuid.uuid4().hex,
        wigos_id=wigos, icao_id=None, latitude=latitude, longitude=8.0,
        elevation_m=10.0, provenance={"correlation_group": group,
                                      "dependent_station_ids": list(dependent)},
        created_at=AT - timedelta(hours=1), updated_at=AT - timedelta(hours=1),
    )


def manifest():
    members = {
        model: {
            "provider": model, "model": model, "run_at": (AT - timedelta(hours=6)).isoformat(),
            "dataset_version": "v1", "valid_times": [AT.isoformat()],
            "forecast_leads_hours": [6], "required_fields": ["u", "v"],
            "source_objects": [model], "source_revision": None,
        }
        for model in EXPECTED_MODELS
    }
    return {
        "schema_version": EXACT_DATASET_MANIFEST_VERSION,
        "loader_version": EXACT_LOADER_VERSION,
        "required_models": list(EXPECTED_MODELS),
        "eligibility_class": "captured_before_observation",
        "availability_basis": "first_seen_capture", "members": members,
    }


def row(peer, *, received=AT, created=AT, dataset=None, eligible=True,
        source_observation_ids=()):
    dataset = dataset or manifest()
    observation = SimpleNamespace(
        id=uuid.uuid4(), observed_at=AT - timedelta(minutes=5),
        received_at=received, imported_at=received,
    )
    sample = {"dataset_bundle_hash": _hash(dataset), "coordinate": [54.3, 8.0]}
    residual = SimpleNamespace(
        id=uuid.uuid4(), analyzed_at=created, created_at=created,
        qc_status="accepted", activation_eligible=eligible,
        baseline_version=EXACT_BUNDLE_VERSION,
        dataset_bundle_hash=_hash(dataset), dataset_manifest=dataset,
        sample_hash=_hash(sample), sample_manifest=sample,
        model_members=[{"source_product": "raw_model",
                        "source_observation_ids": list(source_observation_ids)}],
    )
    return peer, observation, residual


def audit(target, rows):
    dataset = manifest()
    return audit_holdout_inputs(
        target_station=target, residual_rows=rows, cutoff=AT,
        target_dataset_hash=_hash(dataset), target_manifest=dataset,
    )


def test_target_duplicate_dependency_and_correlation_are_removed_before_engine():
    target = station(wigos="TARGET", group="a")
    duplicate = station(latitude=54.4, wigos="TARGET")
    dependent = station(latitude=54.5, dependent=(str(target.id),))
    correlated = station(latitude=54.6, group="a")
    nearby = station(latitude=54.05)
    independent = station(latitude=54.8)
    accepted, excluded = audit(target, [
        row(target), row(duplicate), row(dependent), row(correlated),
        row(nearby), row(independent),
    ])
    assert {str(item[0].id) for item in accepted} == {str(independent.id)}
    reasons = {item["station_id"]: item["reasons"] for item in excluded}
    assert "target_station" in reasons[str(target.id)]
    assert "target_api_duplicate" in reasons[str(duplicate.id)]
    assert "dependent_station" in reasons[str(dependent.id)]
    assert "target_correlation_group" in reasons[str(correlated.id)]
    assert "target_correlation_group" in reasons[str(nearby.id)]


def test_target_and_aliases_are_removed_before_station_selection():
    target = station(wigos="TARGET")
    duplicate = station(latitude=54.6, wigos="TARGET")
    nearby = station(latitude=54.05)
    independent = station(latitude=54.8)
    selected, excluded = exclude_target_dependence(
        [target, duplicate, nearby, independent], target,
    )
    assert [item.id for item in selected] == [independent.id]
    assert {item["station_id"] for item in excluded} == {
        str(target.id), str(duplicate.id), str(nearby.id),
    }


def test_station_history_flags_stuck_jump_and_unknown_standard():
    target = station()
    target.measurement_height_m = 10
    target.provenance = {}
    rows = [SimpleNamespace(observed_at=AT - timedelta(minutes=minute),
                            wind_u_ms=5.0, wind_v_ms=0.0) for minute in (0, 15, 30)]

    class Db:
        def scalars(self, _statement):
            return SimpleNamespace(all=lambda: rows)

    reasons = _station_history_reasons(Db(), target, rows[0], AT)
    assert "measurement_standard_unproven" in reasons
    assert "station_wind_stuck" in reasons
    target.provenance = {"measurement_standard": "fixture-wmo"}
    rows[0].wind_u_ms = 45.0
    rows[1].observed_at = AT - timedelta(minutes=5)
    reasons = _station_history_reasons(Db(), target, rows[0], AT)
    assert "station_wind_jump" in reasons


def test_late_or_unknown_availability_and_noneligible_residual_are_excluded():
    target = station()
    late = row(station(latitude=54.5), received=AT + timedelta(minutes=1))
    unknown = row(station(latitude=54.6), received=None)
    late_model = row(station(latitude=54.7), created=AT + timedelta(minutes=1))
    legacy = row(station(latitude=54.8), eligible=False)
    accepted, excluded = audit(target, [late, unknown, late_model, legacy])
    assert not accepted
    reasons = [reason for item in excluded for reason in item["reasons"]]
    assert "station_available_after_cutoff" in reasons
    assert "station_received_at_unproven" in reasons
    assert "residual_available_after_cutoff" in reasons
    assert "residual_not_activation_eligible" in reasons


def test_station_metadata_changed_after_cutoff_is_not_replayed_as_historical_fact():
    target = station()
    peer = station(latitude=54.5)
    peer.updated_at = AT + timedelta(minutes=1)
    accepted, excluded = audit(target, [row(peer)])
    assert not accepted
    assert "station_metadata_after_cutoff" in excluded[0]["reasons"]


def test_different_dataset_and_observation_derived_model_are_excluded():
    target = station()
    other = manifest()
    other["members"][EXPECTED_MODELS[0]]["dataset_version"] = "v2"
    unproven = row(station(latitude=54.7))
    unproven[2].model_members = []
    accepted, excluded = audit(target, [
        row(station(latitude=54.5), dataset=other),
        row(station(latitude=54.6), source_observation_ids=("hidden",)),
        unproven,
    ])
    assert not accepted
    reasons = [reason for item in excluded for reason in item["reasons"]]
    assert "dataset_bundle_hash_mismatch" in reasons
    assert "dataset_manifest_incompatible" in reasons
    assert "observation_derived_model_input" in reasons
    assert "adjusted_model_input_forbidden" in reasons


def test_training_proof_requires_reviewed_manifest_embargo_and_disjoint_day():
    version = "candidate-v1"
    end = AT - timedelta(days=2)
    proof = {
        "candidate_version": version, "training_window_end": end.isoformat(),
        "frozen_at": (end + timedelta(hours=1)).isoformat(),
        "training_weather_blocks": [],
        "training_sources": [{"source_id": "regional-live-wind-engine", "content_hash": _engine_hash(),
                              "last_observed_at": (end - timedelta(days=1)).isoformat(),
                              "weather_blocks": []}],
        "lineage_complete": True, "reviewed": True,
    }
    proof["training_source_hash"] = _hash(proof["training_sources"])
    assert _training_reasons(None, version, AT) == ["training_boundary_unproven"]
    assert _training_reasons(proof, version, AT) == []
    assert _training_reasons(proof, version, end + timedelta(hours=12)) == ["training_embargo"]
    proof["training_weather_blocks"] = [str(int(AT.timestamp()) // 86400)]
    proof["training_sources"][0]["weather_blocks"] = proof["training_weather_blocks"]
    proof["training_source_hash"] = _hash(proof["training_sources"])
    assert _training_reasons(proof, version, AT) == ["training_boundary_unproven"]


def test_empty_persistent_builder_and_status_are_safe(db):
    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    result = build_live_wind_holdout_cases(
        db, None, candidate_version="empty-fixture", limit=5,
        since=future, until=future + timedelta(hours=1), dry_run=True,
    )
    assert result["selected"] == result["inserted"] == 0
    assert holdout_status(db, candidate_version="empty-fixture")["cases"] == {}


def test_persisted_audit_detects_target_and_late_station_input():
    dataset = manifest()
    value = {
        "analysis_cutoff_at": AT.isoformat(),
        "station_observed_at": (AT - timedelta(minutes=5)).isoformat(),
        "dataset_manifest": dataset, "dataset_bundle_hash": _hash(dataset),
        "target_station_id": "target", "target_observation_id": "hidden",
        "residuals": [{"residual_id": "r1", "station_id": "target",
                       "observation_id": "hidden", "observed_at": AT.isoformat()}],
        "residual_availability": [{
            "residual_id": "r1", "station_id": "target",
            "observed_at": AT.isoformat(), "received_at": (AT + timedelta(minutes=1)).isoformat(),
            "imported_at": AT.isoformat(), "residual_created_at": AT.isoformat(),
        }],
        "target_model_members": {},
        "exact_bundle_manifest": {"members": {}},
    }
    reasons = audit_persisted_case(value)
    assert "target_leakage" in reasons
    assert "received_at_after_or_unknown_cutoff" in reasons
    assert "target_model_manifest_missing" in reasons


def test_persisted_audit_allows_postselection_quality_exclusion():
    value = {
        "analysis_cutoff_at": AT.isoformat(),
        "station_observed_at": AT.isoformat(),
        "target_station_id": "target", "target_observation_id": "hidden",
        "target_station_metadata_updated_at": (AT - timedelta(minutes=1)).isoformat(),
        "excluded": [{"station_id": "peer", "reasons": ["station_history_unproven"]}],
        "station_selection": {"candidates": [{"station_id": "peer"}]},
    }
    assert "target_in_station_selection" not in audit_persisted_case(value)
    value["excluded"][0]["reasons"] = ["target_api_duplicate"]
    assert "target_in_station_selection" in audit_persisted_case(value)


def test_real_exact_residuals_build_immutable_idempotent_case(db, tmp_path):
    observed = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=10)
    received = datetime.now(timezone.utc)
    cutoff = received + timedelta(minutes=2)
    run = observed.replace(hour=observed.hour - observed.hour % 6,
                           minute=0, second=0, microsecond=0) - timedelta(hours=6)
    lead = int((observed - run).total_seconds() // 3600)
    suffix = uuid.uuid4().hex[:10]
    region = Region(slug=f"holdout-{suffix}", name="Holdout Fixture", country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"holdout-{suffix}", name="Holdout Fixture", region_id=region.id,
                location=WKTElement("POINT(10 54)", srid=4326), status="published",
                sports=["wind"], water_type=["sea"])
    db.add(spot)
    db.flush()
    target = WeatherStation(
        spot_id=spot.id, provider="dwd", provider_station_id=f"target-{suffix}",
        latitude=54.0, longitude=10.0, elevation_m=10, measurement_height_m=10,
        setting_class="coastal", active=True, approved=True, blocked=False,
        representativeness_status="passed", provenance={"measurement_standard": "fixture-wmo"},
    )
    peer = WeatherStation(
        spot_id=spot.id, provider="dwd", provider_station_id=f"peer-{suffix}",
        latitude=54.4, longitude=10.2, elevation_m=10, measurement_height_m=10,
        setting_class="coastal", active=True, approved=True, blocked=False,
        representativeness_status="passed", provenance={"measurement_standard": "fixture-wmo"},
    )
    db.add_all((target, peer))
    db.commit()
    loader = ExactRunLoader(ExactRunAssetCache(tmp_path), gfs=FakeGfs(), icon=FakeIcon())
    for station_row in (target, peer):
        report = loader.capture(
            run_at=run, forecast_hours=(lead, lead + 1),
            latitude=station_row.latitude, longitude=station_row.longitude,
            now=observed - timedelta(minutes=1),
        )
        assert not report["errors"]
        for minutes_before, speed in ((20, 8), (10, 9)):
            historical = normalize_observation(
                provider="dwd", station_id=station_row.provider_station_id,
                observed_at=observed - timedelta(minutes=minutes_before),
                received_at=received, imported_at=received,
                wind_speed_ms=speed, wind_direction_deg=270, provider_quality="good",
                latitude=station_row.latitude, longitude=station_row.longitude,
                measurement_height_m=10, license="fixture-only",
                provenance={"fixture": suffix},
            )
            assert persist_batch(db, station_row, [historical], dry_run=False)["persisted"] == 1
        normalized = normalize_observation(
            provider="dwd", station_id=station_row.provider_station_id,
            observed_at=observed, received_at=received, imported_at=received,
            wind_speed_ms=10, wind_direction_deg=270, provider_quality="good",
            latitude=station_row.latitude, longitude=station_row.longitude,
            measurement_height_m=10, license="fixture-only", provenance={"fixture": suffix},
        )
        assert persist_batch(db, station_row, [normalized], dry_run=False)["persisted"] == 1
        observation = db.scalar(select(WeatherObservation).where(
            WeatherObservation.station_id == station_row.id,
            WeatherObservation.observed_at == observed,
        ))
        residual = calculate_and_persist_station_model_error(
            db, station_row, observation, loader(station_row, observation), analyzed_at=received,
        )
        db.commit()
        assert residual.activation_eligible
    bundle = loader.bundle(valid_at=observed, latitude=target.latitude,
                           longitude=target.longitude, as_of=observed)
    job = WeatherLiveWindJob(
        spot_id=spot.id, region_id=region.id, region_key=region.slug,
        cycle_at=observed, rollout_stage="shadow", analysis_version=REGIONAL_LIVE_WIND_VERSION,
        status="succeeded", available_at=observed, analyzed_at=cutoff, valid_at=cutoff,
        diagnostics={"activation_eligible": True, "dataset_bundle_hash": bundle.dataset_bundle_hash,
                     "exact_run_bundle": bundle.manifest()},
    )
    db.add(job)
    db.commit()
    proof_end = observed - timedelta(days=3)
    proof = {
        "candidate_version": f"test-{suffix}",
        "training_window_end": proof_end.isoformat(),
        "frozen_at": (proof_end + timedelta(hours=1)).isoformat(),
        "training_weather_blocks": [],
        "training_sources": [{"source_id": "regional-live-wind-engine", "content_hash": _engine_hash(),
                              "last_observed_at": (proof_end - timedelta(days=1)).isoformat(),
                              "weather_blocks": []}],
        "lineage_complete": True, "reviewed": True,
    }
    proof["training_source_hash"] = _hash(proof["training_sources"])
    try:
        first = build_live_wind_holdout_cases(
            db, loader, candidate_version=proof["candidate_version"], training_proof=proof,
            since=observed - timedelta(minutes=1), until=cutoff, limit=1,
        )
        assert first["inserted"] == 1, first
        original_bundle = loader.bundle

        def interrupted_bundle(**_kwargs):
            raise RuntimeError("fixture_worker_interruption")

        loader.bundle = interrupted_bundle
        try:
            interrupted = build_live_wind_holdout_cases(
                db, loader, candidate_version=proof["candidate_version"], training_proof=proof,
                since=observed - timedelta(minutes=1), until=cutoff, limit=1,
            )
        finally:
            loader.bundle = original_bundle
        assert interrupted["errors"] == 1, interrupted
        assert db.scalar(select(WeatherLiveWindHoldoutCase).where(
            WeatherLiveWindHoldoutCase.candidate_version == proof["candidate_version"]
        )) is not None
        resumed = build_live_wind_holdout_cases(
            db, loader, candidate_version=proof["candidate_version"], training_proof=proof,
            since=observed - timedelta(minutes=1), until=cutoff, limit=2,
        )
        assert resumed["inserted"] == 1, resumed
        case_row = db.scalar(select(WeatherLiveWindHoldoutCase).where(
            WeatherLiveWindHoldoutCase.target_station_id == target.id))
        assert case_row is not None
        assert case_row.eligibility_status == "eligible", case_row.exclusion_reasons
        assert all(item["station_id"] != str(target.id) for item in case_row.payload["residuals"])
        assert case_row.payload["target_truth"]["u_ms"] is not None
        case_id = case_row.id
        for statement in (
            "UPDATE weather_live_wind_holdout_cases SET eligibility_status='not_activation_eligible' WHERE id=:id",
            "DELETE FROM weather_live_wind_holdout_cases WHERE id=:id",
        ):
            with pytest.raises(DBAPIError, match="LiveWind holdout cases are immutable"):
                db.execute(text(statement), {"id": case_id})
            db.rollback()
        assert db.get(WeatherLiveWindHoldoutCase, case_id) is not None
        replay = build_live_wind_holdout_cases(
            db, loader, candidate_version=proof["candidate_version"], training_proof=proof,
            since=observed - timedelta(minutes=1), until=cutoff, limit=2, recompute=True,
        )
        assert replay["existing"] == 2, replay
        policy = LiveWindVerificationPolicy(
            minimum_samples=2, minimum_days=2, minimum_stations=2,
            bootstrap_iterations=200,
        )
        verification = verify_persisted_holdouts(
            db, candidate_version=proof["candidate_version"], training_proof=proof,
            policy=policy,
        )
        assert verification["status"] == "collecting", verification
        assert verification["inserted"] is True
        repeat = verify_persisted_holdouts(
            db, candidate_version=proof["candidate_version"], training_proof=proof,
            policy=policy,
        )
        assert repeat["context_hash"] == verification["context_hash"]
        assert repeat["inserted"] is False
        readiness = _holdout_readiness(
            db, candidate_version=proof["candidate_version"], settings=Settings(),
        )
        assert readiness["status"] == "insufficient_evidence"
        assert readiness["case_counts"] == {"eligible": 2}
    finally:
        db.rollback()
