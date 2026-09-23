"""The core categorical evaluation used identically for live and climatology."""

from __future__ import annotations

from app.scoring.gates import apply_gates
from app.scoring.magnitude import grade_magnitude
from app.scoring.params import get_params

NO = "nein"


def evaluate_conditions(
    values: dict,
    editorial: dict | None,
    profile: dict | None,
    sport: str,
    params: dict | None = None,
) -> dict:
    """Rate one set of condition ``values`` as ``gut`` / ``mäßig`` / ``nein``.

    Same logic whether ``values`` come from a live instant or a climatology
    histogram cell. Returns ``{"rating", "reasons"}``; a failed gate yields
    ``nein`` with the failing gate reasons.
    """
    params = params or get_params(sport)
    passed, gate_reasons = apply_gates(values, editorial, sport, params, profile)
    if not passed:
        return {"rating": NO, "reasons": gate_reasons}
    rating, reasons = grade_magnitude(values, editorial, profile, params, sport)
    return {"rating": rating, "reasons": list(dict.fromkeys(gate_reasons + reasons))}
