"""Local-only marine model comparison. It has no public activation path."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from app.weather.verification import circular_error_deg

MARINE_SHADOW_VERSION = "marine-shadow-v1"


@dataclass(frozen=True)
class MarineShadowResult:
    version: str
    sample_count: int
    height_mae_m: float | None
    period_mae_s: float | None
    direction_mae_deg: float | None
    availability_ratio: float
    public_effect: bool = False
    uncertainty: str = "not_determined"


def compare_marine_shadow(rows: list[dict]) -> MarineShadowResult:
    """Compare candidate values with a reference fixture without filling gaps."""
    available = [row for row in rows if row.get("candidate_height_m") is not None]
    height = [abs(float(row["candidate_height_m"]) - float(row["reference_height_m"]))
              for row in available if row.get("reference_height_m") is not None]
    period = [abs(float(row["candidate_period_s"]) - float(row["reference_period_s"]))
              for row in available if row.get("candidate_period_s") is not None and row.get("reference_period_s") is not None]
    direction = [circular_error_deg(row["candidate_direction_deg"], row["reference_direction_deg"])
                 for row in available if row.get("candidate_direction_deg") is not None
                 and row.get("reference_direction_deg") is not None]
    return MarineShadowResult(
        MARINE_SHADOW_VERSION, len(available),
        round(mean(height), 3) if height else None,
        round(mean(period), 3) if period else None,
        round(mean(direction), 3) if direction else None,
        round(len(available) / len(rows), 4) if rows else 0.0,
    )
