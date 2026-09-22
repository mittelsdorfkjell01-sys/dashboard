from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

from app.config import Settings
from app.live.cache import InMemoryCache
from app.live.public_cache import (
    get_public_live_wind_analysis,
    get_public_live_wind_residuals,
    invalidate_public_measurement,
    public_live_wind_analysis_key,
    public_live_wind_input_generation,
    public_live_wind_lock_key,
    public_live_wind_residual_key,
    public_measurement_key,
    public_weather_generation,
    set_public_live_wind_analysis,
    set_public_live_wind_residuals,
)
from app.live.service import public_live_wind_analysis


def baseline(now: datetime) -> dict:
    return {
        "status": "baseline",
        "analyzed_at": now.isoformat(),
        "valid_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
        "wind_speed_ms": 5.0,
        "wind_direction_from_deg": 270.0,
        "wind_u_ms": 5.0,
        "wind_v_ms": 0.0,
        "model_version": "model-run-v1",
        "analysis_version": "regional-live-wind-uv-v2",
        "station_count": 0,
        "uncertainty_ms": 1.0,
        "confidence": 0.4,
        "sources": [{
            "source_type": "model_nowcast",
            "source": "raw-model",
            "valid_at": now.isoformat(),
            "captured_at": now.isoformat(),
        }],
        "applied_physics_version": "none",
        "fallback_reason": "station_residuals_unavailable",
        "model_baseline_u_ms": 5.0,
        "model_baseline_v_ms": 0.0,
        "model_spread_ms": 1.0,
    }


def test_cache_products_are_separate_by_spot_context_and_generation():
    cache = InMemoryCache()
    spot = uuid.uuid4()
    other = uuid.uuid4()
    context = "context-a"
    assert public_measurement_key(spot) not in public_live_wind_residual_key(spot, context)
    assert public_live_wind_residual_key(spot, context) not in public_live_wind_analysis_key(spot, context)
    assert public_live_wind_analysis_key(spot, context) != public_live_wind_analysis_key(other, context)

    set_public_live_wind_residuals(cache, spot, context, {"residuals": [{"id": "a"}]})
    set_public_live_wind_analysis(cache, spot, context, baseline(datetime.now(timezone.utc)))
    assert get_public_live_wind_residuals(cache, spot, context) is not None
    assert get_public_live_wind_analysis(cache, spot, context) is not None

    weather_generation = public_weather_generation(cache, spot)
    previous_input_generation = public_live_wind_input_generation(cache, spot)
    invalidate_public_measurement(cache, spot)
    assert public_weather_generation(cache, spot) == weather_generation
    assert public_live_wind_input_generation(cache, spot) != previous_input_generation
    assert get_public_live_wind_residuals(cache, spot, context) is None
    assert get_public_live_wind_analysis(cache, spot, context) is None


def test_in_memory_lock_has_token_ownership_and_explicit_stampede_protection():
    cache = InMemoryCache()
    key = "lock:live-wind:test"
    assert cache.acquire_lock(key, "owner-a", 30) is True
    assert cache.acquire_lock(key, "owner-b", 30) is False
    cache.release_lock(key, "owner-b")
    assert cache.acquire_lock(key, "owner-b", 30) is False
    cache.release_lock(key, "owner-a")
    assert cache.acquire_lock(key, "owner-b", 30) is True


def test_common_public_analysis_path_caches_once_without_mutating_baseline(monkeypatch):
    now = datetime.now(timezone.utc)
    source = baseline(now)
    original = {**source, "sources": [dict(source["sources"][0])]}
    cache = InMemoryCache()
    spot_id = uuid.uuid4()
    spot = SimpleNamespace(id=spot_id, weather_profile=None, region=SimpleNamespace(slug="test"))
    calls = []

    monkeypatch.setattr("app.live.service._load_spot", lambda _db, _spot_id: spot)
    monkeypatch.setattr(
        "app.live.service.get_settings",
        lambda: Settings(
            live_wind_rollout_stage="global",
            live_wind_require_verification_evidence=False,
        ),
    )

    def analyze(_db, _spot, candidate_baseline, **_kwargs):
        calls.append(candidate_baseline)
        result = dict(candidate_baseline)
        result["fallback_reason"] = "quality_gate:test"
        return result

    monkeypatch.setattr("app.weather.live_wind_rollout.public_live_wind", analyze)
    first = public_live_wind_analysis(object(), spot_id, source, cache=cache, model_ids=("icon_eu",))
    second = public_live_wind_analysis(object(), spot_id, source, cache=cache, model_ids=("icon_eu",))

    assert first == second
    assert len(calls) == 1
    assert source == original
    assert "_model_ids" not in first


def test_lock_contention_returns_controlled_baseline_without_running_analysis(monkeypatch):
    now = datetime.now(timezone.utc)
    source = baseline(now)
    cache = InMemoryCache()
    spot_id = uuid.uuid4()
    spot = SimpleNamespace(id=spot_id, weather_profile=None, region=SimpleNamespace(slug="test"))
    settings = Settings(
        live_wind_rollout_stage="global",
        live_wind_require_verification_evidence=False,
    )
    monkeypatch.setattr("app.live.service._load_spot", lambda _db, _spot_id: spot)
    monkeypatch.setattr("app.live.service.get_settings", lambda: settings)
    from app.live.live_wind import live_wind_context_id

    gate_configuration = {
        "rollout_stage": settings.live_wind_rollout_stage,
        "enabled_regions": sorted(settings.live_wind_enabled_region_slugs),
        "require_verification_evidence": settings.live_wind_require_verification_evidence,
        "require_operational_health": settings.live_wind_require_operational_health,
        "candidate_version": settings.live_wind_candidate_version,
        "verification_context_hash": settings.live_wind_verification_context_hash,
        "verification_min_samples": settings.live_wind_verification_min_samples,
        "verification_min_days": settings.live_wind_verification_min_days,
        "verification_min_stations": settings.live_wind_verification_min_stations,
        "verification_min_uv_mae_drop_ms": settings.live_wind_verification_min_uv_mae_drop_ms,
        "verification_max_subgroup_regression_ms": settings.live_wind_verification_max_subgroup_regression_ms,
        "verification_subgroup_policy_version": settings.live_wind_verification_subgroup_policy_version,
        "minimum_station_count": settings.live_wind_min_station_count,
        "minimum_confidence": settings.live_wind_min_confidence,
        "maximum_conflict": settings.live_wind_max_conflict_index,
        "maximum_uncertainty_ms": settings.live_wind_max_uncertainty_ms,
        "maximum_correction_ms": settings.live_wind_max_correction_ms,
    }
    working = {**source, "_model_ids": ["icon_eu"]}
    context = live_wind_context_id(spot, working, gate_configuration=gate_configuration)
    lock_key = public_live_wind_lock_key(
        spot_id,
        context,
        weather_generation="0",
        input_generation="0",
    )
    assert cache.acquire_lock(lock_key, "other-worker", 30)
    monkeypatch.setattr(
        "app.weather.live_wind_rollout.public_live_wind",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    result = public_live_wind_analysis(
        object(), spot_id, source, cache=cache, model_ids=("icon_eu",)
    )
    assert result["status"] == "baseline"
    assert result["fallback_reason"] == "analysis_in_progress"
