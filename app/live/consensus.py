"""Pure statistics for multi-model consensus + spread (Sprint 18, Phase 1).

No I/O and no dependencies, so this is unit-testable in isolation. Given the
per-model values of one variable at one timestep, the "spread" is the honest
uncertainty band: the **consensus** (median) is the headline estimate, and
min/max is the band. With <= 4 models min/max *is* the p0/p100 band, which is
the most interpretable form of the spread; ``n`` records how many models had
data so callers can degrade gracefully when coverage is thin.
"""

from __future__ import annotations

from statistics import median as _median
import math

# Confidence tiers, shared with the live path (German strings).
CONFIDENCE_HIGH = "hoch"
CONFIDENCE_MEDIUM = "mittel"
CONFIDENCE_LOW = "niedrig"

# Wind model-disagreement (kt) thresholds mapping spread -> day confidence.
# Model spread naturally widens with the forecast horizon, so later days drift
# to lower confidence on their own -- the honest replacement for the old
# calendar rule (days 1-3 hoch / 4-5 mittel / 6-7 niedrig).
SPREAD_TIGHT_KT = 6.0   # <= -> hoch
SPREAD_WIDE_KT = 12.0   # <= -> mittel, else niedrig


def _finite(values) -> list[float]:
    """Keep only real numbers (drops None / non-numeric coverage gaps)."""
    return [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)]


def spread(values) -> dict | None:
    """Consensus band over per-model values at one timestep.

    Returns ``{"median", "low", "high", "n"}`` over the finite values, or
    ``None`` when no model reported data (the caller decides the fallback).
    """
    xs = _finite(values)
    if not xs:
        return None
    return {
        "median": round(_median(xs), 1),
        "low": round(min(xs), 1),
        "high": round(max(xs), 1),
        "n": len(xs),
    }


def confidence_from_spread(spread_kt: float | None) -> str | None:
    """Wind model-disagreement (kt) -> confidence tier, or ``None`` if unknown."""
    if spread_kt is None:
        return None
    if spread_kt <= SPREAD_TIGHT_KT:
        return CONFIDENCE_HIGH
    if spread_kt <= SPREAD_WIDE_KT:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW
