from datetime import datetime, timedelta, timezone

import pytest

from app.weather.live_wind_analysis import (
    StationResidualInput,
    TargetModelState,
    analyze_regional_live_wind,
)
from app.live.live_wind import build_live_wind_baseline, compose_live_wind
from app.schemas.live import LiveWindRead
from app.weather.consensus import WindConsensus
from app.weather.model_error import StationPhysicsSector
from app.weather.profiles import ResolvedWeatherProfile

NOW = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)


def target(**patch):
    values = dict(
        u_ms=10.0,
        v_ms=0.0,
        valid_at=NOW,
        model_version="raw-consensus-v1",
        model_ids=("icon_eu", "ncep_gfs_global"),
        model_spread_ms=1.0,
        air_mass_id="maritime-west",
    )
    values.update(patch)
    return TargetModelState(**values)


def residual(identifier: str, u_ms=2.0, v_ms=0.0, **patch):
    values = dict(
        residual_id=f"residual-{identifier}",
        analysis_id=f"analysis-{identifier}",
        station_id=identifier,
        observation_id=f"observation-{identifier}",
        provider="test",
        observed_at=NOW - timedelta(minutes=5),
        residual_u_ms=u_ms,
        residual_v_ms=v_ms,
        selection_weight=1.0,
        residual_uncertainty_ms=0.5,
        qc_status="accepted",
        correlation_group=f"group-{identifier}",
        terrain_similarity=1.0,
        coastal_similarity=1.0,
        elevation_similarity=1.0,
        air_mass_similarity=1.0,
        station_air_mass_id="maritime-west",
    )
    values.update(patch)
    return StationResidualInput(**values)


def test_agreeing_stations_produce_a_bounded_regional_vector_correction():
    result = analyze_regional_live_wind(
        target(),
        [residual("a", 2.0), residual("b", 2.1), residual("c", 1.9)],
        analyzed_at=NOW,
    )

    assert result.status == "station_adjusted"
    assert result.correction_u_ms == pytest.approx(1.93, abs=0.12)
    assert result.correction_v_ms == pytest.approx(0.0, abs=1e-9)
    assert result.regional_u_ms == pytest.approx(10 + result.correction_u_ms)
    assert sum(
        item.contribution_u_ms for item in result.station_contributions
    ) == pytest.approx(result.correction_u_ms)
    assert sum(
        item.normalized_weight for item in result.station_contributions if item.included
    ) == pytest.approx(1.0)


def test_contradictory_stations_raise_conflict_and_fall_back_to_model():
    result = analyze_regional_live_wind(
        target(),
        [residual("west", 4.0), residual("east", -4.0)],
        analyzed_at=NOW,
    )

    assert result.status == "baseline"
    assert result.fallback_reason == "station_residual_conflict"
    assert result.conflict_index >= 0.75
    assert result.uncertainty_ms > target().model_spread_ms
    assert result.correction_u_ms == 0
    assert result.regional_u_ms == target().u_ms


def test_one_faulty_station_is_removed_by_robust_weighting():
    result = analyze_regional_live_wind(
        target(),
        [residual("a", 2.0), residual("b", 2.0), residual("faulty", 22.0)],
        analyzed_at=NOW,
    )

    faulty = next(
        item for item in result.station_contributions if item.station_id == "faulty"
    )
    assert result.status == "station_adjusted"
    assert 1.6 < result.correction_u_ms < 2.1
    assert faulty.included is False
    assert "robust_outlier" in faulty.exclusion_reasons
    assert faulty.normalized_weight == 0


def test_mountain_barrier_prevents_air_mass_mixing():
    result = analyze_regional_live_wind(
        target(),
        [residual("lee", mountain_barrier=True)],
        analyzed_at=NOW,
    )

    assert result.status == "baseline"
    assert result.fallback_reason == "station_residuals_unavailable"
    assert result.station_contributions[0].exclusion_reasons == ("mountain_barrier",)


def test_coastal_transition_prevents_cross_regime_transfer():
    result = analyze_regional_live_wind(
        target(),
        [residual("inland", coastal_similarity=0.1)],
        analyzed_at=NOW,
    )

    assert result.status == "baseline"
    assert "coastal_regime_mismatch" in (
        result.station_contributions[0].exclusion_reasons
    )


def test_coastal_compatibility_tapers_to_zero_without_a_boundary_jump():
    just_outside = analyze_regional_live_wind(
        target(),
        [residual("coast", coastal_similarity=0.2499)],
        analyzed_at=NOW,
    )
    just_inside = analyze_regional_live_wind(
        target(),
        [residual("coast", coastal_similarity=0.2501)],
        analyzed_at=NOW,
    )

    assert just_outside.correction_u_ms == 0
    assert just_inside.correction_u_ms == 0
    assert just_inside.status == "baseline"


def test_different_air_mass_is_not_mixed_into_the_target_analysis():
    result = analyze_regional_live_wind(
        target(),
        [residual("continental", station_air_mass_id="continental-east")],
        analyzed_at=NOW,
    )

    assert result.status == "baseline"
    assert "air_mass_mismatch" in result.station_contributions[0].exclusion_reasons


def test_rejected_residual_cannot_influence_live_wind():
    result = analyze_regional_live_wind(
        target(),
        [residual("failed-qc", qc_status="rejected")],
        analyzed_at=NOW,
    )

    assert result.status == "baseline"
    assert result.correction_u_ms == 0
    assert "residual_qc_rejected" in result.station_contributions[0].exclusion_reasons


def test_newer_residual_receives_more_weight_without_becoming_a_hard_override():
    result = analyze_regional_live_wind(
        target(),
        [
            residual("fresh", 2.0, observed_at=NOW - timedelta(minutes=2)),
            residual("older", 2.0, observed_at=NOW - timedelta(minutes=35)),
        ],
        analyzed_at=NOW,
    )

    by_station = {item.station_id: item for item in result.station_contributions}
    assert by_station["fresh"].normalized_weight > by_station["older"].normalized_weight
    assert by_station["older"].normalized_weight > 0


def test_complete_station_outage_returns_the_unchanged_model_baseline():
    result = analyze_regional_live_wind(target(), [], analyzed_at=NOW)

    assert result.status == "baseline"
    assert result.fallback_reason == "station_residuals_unavailable"
    assert result.regional_u_ms == 10.0
    assert result.regional_v_ms == 0.0
    assert result.correction_u_ms == 0.0
    assert result.correction_v_ms == 0.0


def test_extreme_agreeing_residuals_are_limited_smoothly():
    result = analyze_regional_live_wind(
        target(),
        [residual("a", 20.0), residual("b", 20.0), residual("c", 20.0)],
        analyzed_at=NOW,
    )

    assert result.status == "station_adjusted"
    assert 0 < result.correction_u_ms < 6.0


def test_calm_model_consensus_remains_an_available_baseline():
    class Spot:
        weather_profile = None

    payload = build_live_wind_baseline(
        Spot(),
        WindConsensus(
            speed_ms=0.0,
            direction_deg=None,
            gust_ms=None,
            low_ms=0.0,
            high_ms=0.0,
            member_count=2,
            weights={"icon_eu": 0.5, "ncep_gfs_global": 0.5},
        ),
        model_ids=("icon_eu", "ncep_gfs_global"),
        valid_at=NOW,
        captured_at=NOW,
    )

    validated = LiveWindRead.model_validate(payload)
    assert validated.status == "baseline"
    assert validated.wind_speed_ms == 0.0
    assert validated.wind_direction_from_deg is None


def test_result_is_deterministic_across_database_order_and_caps_station_clusters():
    inputs = [
        residual("a", correlation_group="nearby", selection_weight=1.0),
        residual("b", correlation_group="nearby", selection_weight=1.0),
        residual("c", correlation_group="independent", selection_weight=0.2),
    ]
    forward = analyze_regional_live_wind(target(), inputs, analyzed_at=NOW)
    reverse = analyze_regional_live_wind(target(), list(reversed(inputs)), analyzed_at=NOW)

    assert forward == reverse
    clustered = sum(
        item.normalized_weight
        for item in forward.station_contributions
        if item.correlation_group == "nearby"
    )
    assert clustered <= 0.550001


def test_small_spatial_weight_change_cannot_create_a_region_boundary_jump():
    left = analyze_regional_live_wind(
        target(),
        [
            residual("a", 2.0, selection_weight=0.49),
            residual("b", 4.0, selection_weight=0.51),
        ],
        analyzed_at=NOW,
    )
    right = analyze_regional_live_wind(
        target(),
        [
            residual("a", 2.0, selection_weight=0.51),
            residual("b", 4.0, selection_weight=0.49),
        ],
        analyzed_at=NOW,
    )

    assert abs(left.correction_u_ms - right.correction_u_ms) < 0.2


def test_duplicate_residual_input_is_never_weighted_twice():
    duplicate = residual("same")
    result = analyze_regional_live_wind(
        target(), [duplicate, duplicate], analyzed_at=NOW
    )

    assert sum(item.normalized_weight > 0 for item in result.station_contributions) == 1
    rejected = next(
        item for item in result.station_contributions if "duplicate_residual_input" in item.exclusion_reasons
    )
    assert rejected.applied_weight == 0


def test_malformed_duplicate_identifier_still_has_a_deterministic_winner():
    first = residual("same", u_ms=2.0)
    conflicting = residual("same", u_ms=4.0)

    forward = analyze_regional_live_wind(
        target(), [first, conflicting], analyzed_at=NOW
    )
    reverse = analyze_regional_live_wind(
        target(), [conflicting, first], analyzed_at=NOW
    )

    assert forward == reverse


def test_zero_relationship_weight_falls_back_without_dividing_by_zero():
    result = analyze_regional_live_wind(
        target(),
        [
            residual("a", terrain_similarity=0.0),
            residual("b", terrain_similarity=0.0),
            residual("c", terrain_similarity=0.0),
        ],
        analyzed_at=NOW,
    )

    assert result.status == "baseline"
    assert result.fallback_reason == "station_residuals_unavailable"
    assert all(
        "station_relationship_weight_zero" in item.exclusion_reasons
        for item in result.station_contributions
    )


def test_regional_analysis_is_applied_before_local_spot_physics():
    model = target()
    regional = analyze_regional_live_wind(
        model,
        [residual("a"), residual("b"), residual("c")],
        analyzed_at=NOW,
    )
    profile = ResolvedWeatherProfile(
        active=True,
        quality_tier="advanced",
        sectors=(
            StationPhysicsSector(
                start_deg=0,
                end_deg=360,
                speed_factor=1.2,
            ),
        ),
    )

    payload = compose_live_wind(
        model,
        regional,
        profile=profile,
        physics_version="spot-physics-v3",
        captured_at=NOW,
    )

    regional_speed = (
        payload["regional_wind_u_ms"] ** 2
        + payload["regional_wind_v_ms"] ** 2
    ) ** 0.5
    assert payload["wind_speed_ms"] == pytest.approx(regional_speed * 1.2)
    assert payload["model_baseline_u_ms"] == 10.0
    assert payload["correction_u_ms"] > 0
    assert payload["local_physics_component"]["component"] == "gwa_sector"
    assert "station_measurement" not in {
        source["source_type"] for source in payload["sources"]
    }
    validated = LiveWindRead.model_validate(payload)
    assert validated.station_count == 3


def test_uncertainty_accounts_for_age_geometry_profile_and_correction_strength():
    fresh_independent = analyze_regional_live_wind(
        target(profile_available=True, terrain_complexity=0.0),
        [
            residual("a", 1.0, distance_km=10.0),
            residual("b", 1.0, distance_km=15.0),
        ],
        analyzed_at=NOW,
    )
    old_clustered_missing_profile = analyze_regional_live_wind(
        target(profile_available=False, terrain_complexity=1.0),
        [
            residual(
                "a", 5.0, observed_at=NOW - timedelta(minutes=45),
                correlation_group="cluster", distance_km=80.0,
            ),
            residual(
                "b", 5.0, observed_at=NOW - timedelta(minutes=45),
                correlation_group="cluster", distance_km=85.0,
            ),
        ],
        analyzed_at=NOW,
    )

    assert old_clustered_missing_profile.uncertainty_ms > fresh_independent.uncertainty_ms
    components = old_clustered_missing_profile.uncertainty_components
    assert components["station_age"] > 0
    assert components["station_geometry"] > 0
    assert components["terrain"] > 0
    assert components["missing_information"] > 0
    assert components["correction_strength"] > fresh_independent.uncertainty_components["correction_strength"]


def test_public_uncertainty_band_contains_speed_and_weak_wind_has_no_bearing_precision():
    model = target(u_ms=0.5, v_ms=0.0, profile_available=False)
    regional = analyze_regional_live_wind(model, (), analyzed_at=NOW)
    payload = compose_live_wind(model, regional, profile=None, captured_at=NOW)
    validated = LiveWindRead.model_validate(payload)

    assert validated.speed_uncertainty_band_ms is not None
    assert validated.speed_uncertainty_band_ms.low_ms <= validated.wind_speed_ms
    assert validated.speed_uncertainty_band_ms.high_ms >= validated.wind_speed_ms
    assert validated.direction_uncertainty_deg is None
    assert validated.uncertainty_components["missing_information"] > 0
    assert validated.fallback_level == "raw_model"
