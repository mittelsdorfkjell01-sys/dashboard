from app.forecast.backfill_control import evaluate
from app.forecast.backfill_plan import Candidate, build_plan, signature


def candidates(count=23):
    return [
        Candidate(str(i), f"Spot {i}", 40 + i * 0.01, -9 + i * 0.01, 1 if i < 2 else 0)
        for i in range(count)
    ]


def test_plan_is_deterministic_tile_centred_and_never_over_ten():
    first = build_plan(candidates())
    second = build_plan(list(reversed(candidates())))
    assert first == second
    assert [len(b["spots"]) for b in first["batches"]] == [3, 5, 10, 5]
    assert all(len(b["spots"]) <= 10 for b in first["batches"])
    assert first["execution_allowed"] is False


def test_nearby_spots_share_assets_and_dateline_is_bounded():
    a = signature(Candidate("a", "a", 40, -9))
    b = signature(Candidate("b", "b", 40.1, -9.1))
    assert set(a["assets"]) & set(b["assets"])
    edge = signature(Candidate("c", "c", 0, 179.9))
    assert all("E180" not in asset for asset in edge["assets"])


def test_cache_hits_reduce_requests_without_network():
    base = build_plan(candidates(2))
    cached = set(base["batches"][0]["assets"])
    warm = build_plan(candidates(2), cached=cached)
    assert warm["batches"][0]["expected_requests"] == 0
    assert not warm["execution_allowed"]


def test_circuit_breaker_rules():
    assert evaluate(auth_error=True).action == "blocked_provider"
    assert evaluate(planned_bytes=100, actual_bytes=126).action == "paused_budget"
    assert (
        evaluate(attempted_items=5, technical_failures=2).reason
        == "technical_failure_rate"
    )
    assert evaluate(attempted_items=5, d_profiles=2).reason == "quality_gate_d_profiles"
    assert evaluate(geometry_failures=1).action == "quarantined"
