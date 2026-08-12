"""Pure phase-3 circuit-breaker decisions; persistence belongs to the job runner."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitState:
    action: str
    reason: str | None = None


def evaluate(
    *,
    auth_error=False,
    licence_error=False,
    planned_bytes=0,
    actual_bytes=0,
    free_bytes=10**18,
    required_free_bytes=0,
    attempted_items=0,
    technical_failures=0,
    geometry_failures=0,
    d_profiles=0,
    repeated_rate_errors=0,
) -> CircuitState:
    if auth_error or licence_error:
        return CircuitState("blocked_provider", "authentication_or_licence")
    if free_bytes < required_free_bytes:
        return CircuitState("paused_budget", "insufficient_free_storage")
    if planned_bytes and actual_bytes > planned_bytes * 1.25:
        return CircuitState("paused_budget", "actual_bytes_over_125_percent")
    if repeated_rate_errors >= 2:
        return CircuitState("paused", "provider_cooldown")
    if geometry_failures:
        return CircuitState("quarantined", "hard_geometry_invariant")
    if attempted_items >= 5 and technical_failures / attempted_items > 0.2:
        return CircuitState("paused", "technical_failure_rate")
    if attempted_items >= 5 and d_profiles / attempted_items > 0.2:
        return CircuitState("paused", "quality_gate_d_profiles")
    return CircuitState("continue")
