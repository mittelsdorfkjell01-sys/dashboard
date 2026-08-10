from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def clamp_combined_factor(factor: float, advanced: bool) -> float:
    return clamp(factor, 0.60 if advanced else 0.70, 1.35 if advanced else 1.25)


def clamp_direction_change(offset_deg: float, advanced: bool) -> float:
    return clamp(offset_deg, -15.0 if advanced else -10.0, 15.0 if advanced else 10.0)
