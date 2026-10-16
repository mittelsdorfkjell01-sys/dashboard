"""Conservative, datum-independent transfer of harmonic tide corrections."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ConstituentCorrection:
    amplitude_ratio: float
    phase_delta_deg: float
    weight: float
    basin: str
    water_path_km: float
    validated: bool = False


def correction_is_eligible(
    correction: ConstituentCorrection,
    *,
    target_basin: str,
    max_water_path_km: float,
) -> bool:
    return (
        correction.validated
        and correction.basin == target_basin
        and 0 <= correction.water_path_km <= max_water_path_km
        and correction.weight > 0
        and correction.amplitude_ratio > 0
        and math.isfinite(correction.phase_delta_deg)
    )


def interpolate_constituent_correction(
    corrections: list[ConstituentCorrection],
    *,
    target_basin: str,
    max_water_path_km: float,
) -> tuple[float, float] | None:
    """Return weighted amplitude ratio and circular phase delta.

    Only validated corrections in the same connected basin participate.
    Amplitude ratios are averaged in log space and phase is averaged on the
    unit circle, preventing the 359°/1° discontinuity.
    """
    eligible = [
        item for item in corrections
        if correction_is_eligible(
            item, target_basin=target_basin, max_water_path_km=max_water_path_km
        )
    ]
    if not eligible:
        return None
    weights = [
        item.weight / max(1.0, item.water_path_km)
        for item in eligible
    ]
    total = sum(weights)
    log_ratio = sum(w * math.log(item.amplitude_ratio) for w, item in zip(weights, eligible, strict=True)) / total
    x = sum(w * math.cos(math.radians(item.phase_delta_deg)) for w, item in zip(weights, eligible, strict=True))
    y = sum(w * math.sin(math.radians(item.phase_delta_deg)) for w, item in zip(weights, eligible, strict=True))
    phase = math.degrees(math.atan2(y, x))
    return math.exp(log_ratio), phase
