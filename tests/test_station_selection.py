from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.weather.station_selection import (
    SpotSelectionContext,
    StationCandidate,
    evaluate_station_candidates,
)
from app.weather.vectors import wind_to_uv

NOW = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)


def station(identifier: str, *, lat=54.0, lon=10.0, **patch):
    values = dict(
        id=identifier,
        provider="dwd",
        provider_station_id=identifier,
        wigos_id=None,
        icao_id=None,
        latitude=lat,
        longitude=lon,
        elevation_m=5.0,
        measurement_height_m=10.0,
        active=True,
        approved=True,
        blocked=False,
        representativeness_status="passed",
        setting_class="coastal",
        exposure_status="passed",
        provenance={
            "terrain_class": "flat",
            "roughness_length_m": 0.03,
            "mountain_side": "west",
            "provider_reliability": 0.9,
            "station_reliability": 0.9,
            "wind_sector_scores": {"9": 0.9},
        },
    )
    values.update(patch)
    return SimpleNamespace(**values)


def observation(*, age_minutes=5, speed=8.0, direction=270.0, **patch):
    u_ms, v_ms = wind_to_uv(speed, direction)
    values = dict(
        observed_at=NOW - timedelta(minutes=age_minutes),
        wind_speed_ms=speed,
        wind_direction_deg=direction,
        wind_u_ms=u_ms,
        wind_v_ms=v_ms,
        provider_quality="good",
        import_status="accepted",
    )
    values.update(patch)
    return SimpleNamespace(**values)


def target(**patch):
    values = dict(
        latitude=54.0,
        longitude=10.0,
        elevation_m=4.0,
        measurement_height_m=10.0,
        terrain_class="flat",
        roughness_length_m=0.03,
        surface_context="coastal",
        mountain_side="west",
        wind_direction_deg=270.0,
    )
    values.update(patch)
    return SpotSelectionContext(**values)


def evaluate(*pairs, target_context=None):
    return evaluate_station_candidates(
        [StationCandidate(left, right) for left, right in pairs],
        target_context or target(),
        now=NOW,
    )


def test_all_candidates_are_returned_with_components_and_versioned_configuration():
    result = evaluate(
        (station("best"), observation()),
        (station("blocked", lon=10.2, blocked=True), observation()),
    )
    assert len(result.candidates) == 2
    assert result.policy_version == "station-selection-v1"
    assert len(result.configuration_hash) == 64
    best = result.selected
    assert best.station_identity == "dwd:BEST"
    assert set(best.component_weights) == set(result.configuration["component_weights"])
    assert all(
        {"score", "policy_weight", "weighted_value"} == set(component)
        for component in best.component_weights.values()
    )
    blocked = next(item for item in result.candidates if item.provider_station_id == "blocked")
    assert blocked.eligible is False
    assert "station_blocked" in blocked.exclusion_reasons


def test_coastal_transition_and_mountain_barrier_reduce_score():
    matching = station("matching", lon=10.2)
    inland = station("inland", lon=9.8, setting_class="inland")
    other_side = station(
        "other-side",
        lat=54.12,
        provenance={**matching.provenance, "mountain_side": "east"},
    )
    result = evaluate(
        (matching, observation()),
        (inland, observation()),
        (other_side, observation()),
    )
    by_id = {item.provider_station_id: item for item in result.candidates}
    assert (
        by_id["matching"].component_weights["surface_context"]["score"]
        > by_id["inland"].component_weights["surface_context"]["score"]
    )
    assert (
        by_id["matching"].component_weights["mountain_side"]["score"]
        > by_id["other-side"].component_weights["mountain_side"]["score"]
    )
    assert by_id["matching"].base_score > by_id["inland"].base_score
    assert by_id["matching"].base_score > by_id["other-side"].base_score


def test_large_elevation_difference_and_stale_values_are_hard_excluded():
    high = station("high", elevation_m=1000)
    stale = station("stale", lon=10.2)
    result = evaluate(
        (high, observation()),
        (stale, observation(age_minutes=31)),
    )
    by_id = {item.provider_station_id: item for item in result.candidates}
    assert "elevation_difference_exceeded" in by_id["high"].exclusion_reasons
    assert "observation_stale" in by_id["stale"].exclusion_reasons
    assert result.selected is None


def test_physical_duplicate_is_never_weighted_twice():
    primary = station("airport-a", icao_id="EDDH")
    alias = station(
        "airport-b",
        provider="awc_metar",
        icao_id="EDDH",
        lat=54.2,
        lon=10.2,
    )
    result = evaluate(
        (primary, observation(age_minutes=4)),
        (alias, observation(age_minutes=5)),
    )
    assert sum(item.eligible for item in result.candidates) == 1
    duplicate = next(item for item in result.candidates if not item.eligible)
    assert any(reason.startswith("duplicate_of:") for reason in duplicate.exclusion_reasons)
    assert duplicate.total_weight == 0


def test_fallback_uses_second_best_after_nearest_station_fails_gate():
    nearest_stale = station("nearest", lon=10.01)
    second = station("second", lon=10.20)
    result = evaluate(
        (nearest_stale, observation(age_minutes=45)),
        (second, observation(age_minutes=10)),
    )
    assert result.selected.provider_station_id == "second"
    nearest = next(item for item in result.candidates if item.provider_station_id == "nearest")
    assert "observation_stale" in nearest.exclusion_reasons


def test_freshness_alone_cannot_dominate_and_cluster_weight_is_capped():
    fresh_but_poor = station(
        "fresh-poor",
        lon=10.1,
        setting_class="inland",
        exposure_status="limited",
        measurement_height_m=40,
        provenance={
            "terrain_class": "urban",
            "roughness_length_m": 2.0,
            "mountain_side": "east",
            "provider_reliability": 0.2,
            "station_reliability": 0.2,
            "wind_sector_scores": {"9": 0.1},
        },
    )
    older_good = station("older-good", lon=10.3)
    cluster_peer = station("cluster-peer", lat=54.001, lon=10.301)
    result = evaluate(
        (fresh_but_poor, observation(age_minutes=0)),
        (older_good, observation(age_minutes=12)),
        (cluster_peer, observation(age_minutes=12)),
    )
    by_id = {item.provider_station_id: item for item in result.candidates}
    assert by_id["older-good"].base_score > by_id["fresh-poor"].base_score
    clustered = [item for item in result.candidates if item.correlation_group == by_id["older-good"].correlation_group]
    assert sum(item.total_weight for item in clustered) <= 0.900001


def test_missing_or_inconsistent_vector_and_bad_quality_are_excluded():
    missing = observation(wind_u_ms=None)
    inconsistent = observation(wind_u_ms=99.0)
    bad = observation(provider_quality="suspect")
    result = evaluate(
        (station("missing"), missing),
        (station("inconsistent", lon=10.2), inconsistent),
        (station("bad", lon=10.4), bad),
    )
    by_id = {item.provider_station_id: item for item in result.candidates}
    assert "wind_vector_invalid" in by_id["missing"].exclusion_reasons
    assert "wind_vector_inconsistent" in by_id["inconsistent"].exclusion_reasons
    assert "provider_quality_rejected" in by_id["bad"].exclusion_reasons
