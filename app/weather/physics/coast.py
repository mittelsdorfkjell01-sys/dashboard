"""Coastal exposure classification without unvalidated speed constants."""

from __future__ import annotations


def signed_angle_delta(direction_deg: float, reference_deg: float) -> float:
    return ((direction_deg - reference_deg + 180.0) % 360.0) - 180.0


def coastal_class(direction_from_deg: float | None, waterward_normal_deg: float | None) -> str:
    """Classify wind relative to a reviewed land-to-water normal.

    A wind *from* the waterward normal is onshore. Broad classes are exposed as
    information only; V1 applies no invented coast multiplier.
    """
    if direction_from_deg is None or waterward_normal_deg is None:
        return "unavailable"
    delta = abs(signed_angle_delta(direction_from_deg, waterward_normal_deg))
    if delta <= 22.5:
        return "onshore"
    if delta <= 67.5:
        return "cross_onshore"
    if delta < 112.5:
        return "sideshore"
    if delta < 157.5:
        return "cross_offshore"
    if delta <= 180.0:
        return "offshore"
    return "unavailable"
