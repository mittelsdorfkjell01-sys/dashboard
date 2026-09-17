from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

from app.config import Settings
from app.weather.live_wind_jobs import (
    _exclusion_counts,
    retry_delay_seconds as live_wind_retry_delay,
    utc_cycle,
)
from app.weather.live_wind_operations import (
    _product_boundary_audit,
    summarize_live_wind_jobs,
)
from app.weather.live_wind_rollout import (
    public_live_wind,
    quality_gate_reasons,
    rollout_decision,
    verification_evidence_reasons,
)
from app.weather.observation_worker import retry_delay_seconds as import_retry_delay

NOW = datetime(2026, 9, 14, 12, 17, tzinfo=timezone.utc)


def test_residual_identity_rejections_are_counted_without_hash_labels():
    assert _exclusion_counts({}, {
        "residual_rejection_reasons": {
            "dataset_bundle_hash_mismatch": 2,
            "sample_hash_mismatch": 1,
        }
    }) == {"dataset_bundle_hash_mismatch": 2, "sample_hash_mismatch": 1}


def _spot(slug: str = "north-sea"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        region=SimpleNamespace(slug=slug),
    )


def _candidate(**patch) -> dict:
    payload = {
        "status": "station_adjusted",
        "station_count": 2,
        "confidence": 0.8,
        "conflict_index": 0.1,
        "uncertainty_ms": 1.5,
        "correction_u_ms": 1.0,
        "correction_v_ms": 0.5,
    }
    payload.update(patch)
    return payload


def test_rollout_is_shadow_first_and_region_gated():
    spot = _spot()
    shadow = Settings(live_wind_rollout_stage="shadow")
    assert rollout_decision(spot, settings=shadow).expose_station_adjustment is False

    pilot_missing = Settings(live_wind_rollout_stage="pilot")
    assert rollout_decision(spot, settings=pilot_missing).reason == "region_not_enabled"

    pilot = Settings(
        live_wind_rollout_stage="pilot",
        live_wind_enabled_region_slugs="NORTH-SEA, baltic",
    )
    assert rollout_decision(spot, settings=pilot).expose_station_adjustment is True

    killed = Settings(
        live_wind_rollout_stage="global",
        live_wind_force_baseline=True,
    )
    assert rollout_decision(spot, settings=killed).reason == "force_baseline"


def test_shadow_public_path_never_invokes_station_analysis(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("station analysis must stay out of shadow serving")

    monkeypatch.setattr("app.live.live_wind.analyze_live_wind_for_spot", forbidden)
    baseline = {"status": "baseline", "fallback_reason": "station_residuals_unavailable"}
    result = public_live_wind(
        object(),
        _spot(),
        baseline,
        settings=Settings(live_wind_rollout_stage="shadow"),
    )
    assert result is baseline


def test_public_activation_fails_closed_without_verification_context(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("unverified candidate must not run public analysis")

    monkeypatch.setattr("app.live.live_wind.analyze_live_wind_for_spot", forbidden)
    baseline = {"status": "baseline", "fallback_reason": "station_residuals_unavailable"}
    result = public_live_wind(
        object(),
        _spot(),
        baseline,
        settings=Settings(live_wind_rollout_stage="global"),
    )

    assert result["status"] == "baseline"
    assert result["fallback_reason"] == "verification_gate:verification_context_missing"


def test_persisted_evidence_still_requires_reviewed_subgroup_policy():
    evidence = SimpleNamespace(
        policy={"baseline_source": "exact-run-bundle-v2", "leakage_audit": "passed",
                "persisted_case_count": 600, "builder_version": "live-wind-holdout-builder-v1",
                "case_context_hashes": ["context"]},
        matched_samples=600, distinct_days=15, distinct_stations=12,
        metrics={"activation": {"uv_mae_drop_ms": 0.2, "ci_lower_ms": 0.05}},
        stratified_metrics={"country": {"DE": {
            "status": "sufficient", "raw_consensus": {"uv_mae_ms": 1.0},
            "multi_station_live_wind": {"uv_mae_ms": 1.2},
        }}},
    )

    class Db:
        def scalar(self, _statement):
            return evidence

    missing_policy = verification_evidence_reasons(
        Db(), settings=Settings(live_wind_verification_context_hash="a" * 64),
    )
    assert "subgroup_regression_policy_missing" in missing_policy
    regression = verification_evidence_reasons(
        Db(), settings=Settings(
            live_wind_verification_context_hash="a" * 64,
            live_wind_verification_max_subgroup_regression_ms=0.1,
        ),
    )
    assert "subgroup_regression_policy_missing" in regression
    evidence.policy.update({"subgroup_policy_version": "reviewed-v1",
                            "maximum_subgroup_regression_ms": 0.1})
    from app.weather.live_wind_verification import candidate_policy_hash
    evidence.policy["candidate_policy_hash"] = candidate_policy_hash(
        Settings().live_wind_candidate_version, "reviewed-v1", 0.1)
    regression = verification_evidence_reasons(
        Db(), settings=Settings(
            live_wind_verification_context_hash="a" * 64,
            live_wind_verification_subgroup_policy_version="reviewed-v1",
            live_wind_verification_max_subgroup_regression_ms=0.1,
        ),
    )
    assert "verification_subgroup_regression" in regression


def test_quality_loss_immediately_returns_the_model_baseline(monkeypatch):
    monkeypatch.setattr(
        "app.live.live_wind.analyze_live_wind_for_spot",
        lambda *_args, **_kwargs: _candidate(conflict_index=0.95),
    )
    baseline = {"status": "baseline", "fallback_reason": "station_residuals_unavailable"}
    result = public_live_wind(
        object(),
        _spot(),
        baseline,
        settings=Settings(
            live_wind_rollout_stage="global",
            live_wind_require_verification_evidence=False,
        ),
    )
    assert result["status"] == "baseline"
    assert result["fallback_reason"] == "quality_gate:conflict_high"


def test_regional_health_loss_opens_automatic_baseline_circuit(monkeypatch):
    class Rows:
        def all(self):
            return [
                SimpleNamespace(
                    status="succeeded",
                    product_status="baseline",
                    created_at=NOW - timedelta(minutes=index),
                    finished_at=NOW - timedelta(minutes=index),
                )
                for index in range(3)
            ]

    class Db:
        def scalars(self, _statement):
            return Rows()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("quality-degraded region must not run public analysis")

    monkeypatch.setattr("app.live.live_wind.analyze_live_wind_for_spot", forbidden)
    baseline = {"status": "baseline", "fallback_reason": "station_residuals_unavailable"}
    result = public_live_wind(
        Db(),
        _spot(),
        baseline,
        settings=Settings(
            live_wind_rollout_stage="global",
            live_wind_require_verification_evidence=False,
            live_wind_health_min_analyses=2,
        ),
    )
    assert result["status"] == "baseline"
    assert result["fallback_reason"].startswith("operational_gate:")
    assert "fallback_rate_high" in result["fallback_reason"]


def test_quality_gate_checks_vector_evidence_and_uncertainty():
    reasons = quality_gate_reasons(
        _candidate(
            station_count=1,
            confidence=0.05,
            uncertainty_ms=9,
            correction_u_ms=8,
        ),
        settings=Settings(),
    )
    assert reasons == (
        "station_count_low",
        "confidence_low",
        "uncertainty_high",
        "correction_high",
    )


def test_cycle_and_backoffs_are_bounded_and_deterministic():
    assert utc_cycle(NOW, minutes=15) == datetime(
        2026, 9, 14, 12, 15, tzinfo=timezone.utc
    )
    identity = uuid.UUID(int=321)
    assert live_wind_retry_delay(
        1, initial_seconds=30, maximum_seconds=300, identity=identity
    ) == live_wind_retry_delay(
        1, initial_seconds=30, maximum_seconds=300, identity=identity
    )
    assert live_wind_retry_delay(
        20, initial_seconds=30, maximum_seconds=300, identity=identity
    ) == 300
    assert import_retry_delay(
        1, initial_seconds=60, maximum_seconds=3600
    ) == 60
    assert import_retry_delay(
        20, initial_seconds=60, maximum_seconds=3600
    ) == 3600


def _job(
    identifier: int,
    *,
    status="succeeded",
    product_status="station_adjusted",
    region="north-sea",
    terrain="coastal",
    days_ago=0,
    payload=None,
):
    when = NOW - timedelta(days=days_ago)
    return SimpleNamespace(
        id=uuid.UUID(int=identifier),
        status=status,
        product_status=product_status,
        baseline_cache_hit=identifier % 2 == 0,
        analyzed_at=when,
        finished_at=when,
        cycle_at=when,
        created_at=when,
        station_count=2,
        correction_magnitude_ms=1.5,
        conflict_index=0.2,
        uncertainty_ms=1.8,
        duration_ms=120,
        exclusion_reasons={"residual_stale": 1},
        terrain_class=terrain,
        region_key=region,
        result_payload=payload
        or {
            "product_type": "live_wind",
            "wind_direction_from_deg": identifier * 45 % 360,
            "sources": [{"source_type": "station_residual"}],
        },
    )


def test_shadow_metrics_cover_requested_operational_dimensions():
    settings = Settings(
        live_wind_readiness_min_days=2,
        live_wind_readiness_min_analyses=10,
        live_wind_readiness_min_wind_sectors=2,
    )
    jobs = [_job(index, days_ago=index % 3) for index in range(1, 11)]
    jobs.append(_job(99, status="failed", product_status=None, region="baltic"))
    report = summarize_live_wind_jobs(jobs, now=NOW, settings=settings)
    assert report["jobs"]["succeeded"] == 10
    assert report["jobs"]["failed"] == 1
    assert report["stations_per_analysis"]["mean"] == 2
    assert report["correction_magnitude_ms"]["p95"] == 1.5
    assert report["cache_hit_rate"] == 0.5
    assert report["exclusion_reasons"] == {"residual_stale": 10}
    assert "coastal" in report["operational_results_by_terrain_class"]
    assert "north-sea" in report["operational_results_by_region"]
    assert report["rollout_readiness"]["ready_for_pilot_review"] is False


def test_product_boundary_audit_rejects_measurement_or_forecast_sources():
    clean = _job(1)
    leaking = _job(
        2,
        payload={
            "product_type": "live_wind",
            "sources": [
                {"source_type": "station_measurement"},
                {"source_type": "forecast"},
            ],
        },
    )
    report = _product_boundary_audit([clean, leaking])
    assert report["ok"] is False
    assert {item["reason"] for item in report["violations"]} == {
        "raw_measurement_source",
        "forecast_source",
    }


def test_database_lease_prevents_a_second_claim(db):
    from geoalchemy2 import WKTElement

    from app.models import Region, Spot, WeatherLiveWindJob
    from app.weather.live_wind_jobs import claim_live_wind_job

    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"lw-ops-{suffix}",
        name=f"LW Ops {suffix}",
        normalized_name=f"lw ops {suffix}",
        country="DE",
        status="published",
    )
    db.add(region)
    db.flush()
    spot = Spot(
        slug=f"lw-spot-{suffix}",
        name=f"LW Spot {suffix}",
        normalized_name=f"lw spot {suffix}",
        region_id=region.id,
        location=WKTElement("POINT(8.5 54.5)", srid=4326),
        sports=["wind"],
        water_type=["sea"],
        status="published",
    )
    db.add(spot)
    db.flush()
    job = WeatherLiveWindJob(
        spot_id=spot.id,
        region_id=region.id,
        region_key=region.slug,
        cycle_at=NOW,
        rollout_stage="shadow",
        analysis_version="regional-live-wind-uv-v1",
        status="queued",
        available_at=NOW,
    )
    db.add(job)
    db.commit()
    try:
        first = claim_live_wind_job(db, now=NOW)
        assert first is not None
        assert first.worker_token is not None
        assert first.attempt_count == 1
        assert claim_live_wind_job(db, now=NOW) is None
    finally:
        db.query(WeatherLiveWindJob).filter_by(spot_id=spot.id).delete()
        db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()


def test_shadow_workflow_schedules_import_worker_and_doctor():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "live-wind-shadow.yml"
    ).read_text(encoding="utf-8")
    assert 'cron: "3,13,23,33,43,53 * * * *"' in workflow
    assert "LIVE_WIND_ROLLOUT_STAGE: shadow" in workflow
    assert 'test "$LIVE_WIND_ROLLOUT_STAGE" = "shadow"' in workflow
    assert "$WEATHER_OBSERVATION_ENDPOINT" in workflow
    assert "$LIVE_WIND_ENDPOINT" in workflow
    assert "--retry 3" in workflow
    assert "python -m scripts.live_wind_worker" in workflow
    assert "python -m scripts.live_wind_doctor --no-rasters --fail-on-alert" in workflow
