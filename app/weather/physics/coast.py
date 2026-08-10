"""Coastal exposure classification without unvalidated speed constants."""

from __future__ import annotations


def signed_angle_delta(direction_deg: float, reference_deg: float) -> float:
    return ((direction_deg - reference_deg + 180.0) % 360.0) - 180.0


def coastal_class(direction_from_deg: float, waterward_normal_deg: float) -> str:
    """Classify wind relative to a reviewed land-to-water normal.

    A wind *from* the waterward normal is onshore. Broad classes are exposed as
    information only; V1 applies no invented coast multiplier.
    """
    delta = abs(signed_angle_delta(direction_from_deg, waterward_normal_deg))
    if delta <= 45.0:
        return "onshore"
    if delta >= 135.0:
        return "offshore"
    return "crossshore"
