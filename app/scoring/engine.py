"""The ranking ``Scorer`` seam and its concrete scorers.

Search (Sprint 5) ranks against a continuous 0..1 score; the Sprint 4 engine
provides the real one via :class:`SeasonalRuleScorer` (the default), which reduces
a spot's climatology week to a usable/good share. :class:`InterimScorer` is kept
as a lightweight fallback.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

# Distance-decay scale (km) for ``score x exp(-d/d0)``. The parameter doc sets a
# global d0 = 40; kept per-sport here so a future override can differentiate.
DEFAULT_D0_KM: dict[str, float] = {
    "kitesurf": 40.0,
    "windsurf": 40.0,
    "wing": 40.0,
    "surf": 40.0,
}
_FALLBACK_D0_KM = 40.0

# Wind band (knots) mapped onto 0..1 for the interim fallback score.
_WIND_LOW_KT = 8.0
_WIND_HIGH_KT = 25.0


class Scorer(Protocol):
    def score(
        self, spot: Any, time_context: dict | None, profile: dict | None
    ) -> float: ...


def _week_of(time_context: dict | None) -> int:
    """1-based week bucket (1..52) from the time context, matching climatology."""
    if time_context and time_context.get("week"):
        return max(1, min(int(time_context["week"]), 52))
    now = (time_context or {}).get("now") or datetime.now(timezone.utc)
    doy = int(now.timetuple().tm_yday)
    return min((doy - 1) // 7, 51) + 1


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class InterimScorer:
    """Coarse 0..1 suitability from ERA5 climatology — a Sprint 4 placeholder.

    Uses the median wind (``p50_kt``) of the spot's climatology for the week in
    ``time_context``, normalised across an 8-25 kt band. Falls back to the spot's
    stored ``confidence`` (then 0.5) when no climatology is present. Deterministic
    and dependency-free so ranking/colouring are testable offline.
    """

    def score(
        self, spot: Any, time_context: dict | None = None, profile: dict | None = None
    ) -> float:
        clim = getattr(spot, "climatology", None)
        weeks = (clim or {}).get("weeks") if isinstance(clim, dict) else None
        if weeks:
            week = _week_of(time_context)
            entry = next((w for w in weeks if w.get("week") == week), None)
            p50 = (entry or {}).get("wind", {}).get("p50_kt") if entry else None
            if p50 is not None:
                return _clamp01(
                    (p50 - _WIND_LOW_KT) / (_WIND_HIGH_KT - _WIND_LOW_KT)
                )
        conf = getattr(spot, "confidence", None)
        return _clamp01(conf) if isinstance(conf, (int, float)) else 0.5


class SeasonalRuleScorer:
    """Real ranking score from the Sprint 4 rule engine.

    Reduces the spot's climatology week (for the ``time_context`` week and the
    rider/primary sport) to ``0.6·gut_anteil + 0.4·pct_usable``. Falls back to the
    interim score when the spot has no climatology / sport.
    """

    def __init__(self, db: Any | None = None) -> None:
        self._db = db
        self._fallback = InterimScorer()

    def score(
        self, spot: Any, time_context: dict | None = None, profile: dict | None = None
    ) -> float:
        from app.scoring.climatology import _week_entry, evaluate_week_cells
        from app.scoring.context import primary_sport, spot_editorial
        from app.scoring.params import SCORING_PARAMS_V1, get_params

        sport = primary_sport(spot, (profile or {}).get("sport"))
        clim = getattr(spot, "climatology", None)
        if sport in SCORING_PARAMS_V1 and isinstance(clim, dict):
            entry = _week_entry(clim, _week_of(time_context))
            if entry is not None:
                # Resolve via get_params so a deployed scoring_params override wins
                # on the ranking path too (falls back to in-code params if db=None).
                params = get_params(sport, self._db)
                res = evaluate_week_cells(
                    entry, spot_editorial(spot), profile, sport, params
                )
                return _clamp01(0.6 * res["gut_anteil"] + 0.4 * res["pct_usable"])
        return self._fallback.score(spot, time_context, profile)


_default_scorer: Scorer | None = None


def default_scorer(db: Any | None = None) -> Scorer:
    """The default ranking scorer.

    With a ``db`` it returns a fresh scorer bound to that session so DB-deployed
    ``scoring_params`` are honoured; without one it returns a cached, db-less
    scorer (in-code params) for pure/offline use.
    """
    if db is not None:
        return SeasonalRuleScorer(db=db)
    global _default_scorer
    if _default_scorer is None:
        _default_scorer = SeasonalRuleScorer()
    return _default_scorer


def distance_decay_d0(sport: str | None, db: Any | None = None) -> float:
    """Resolve the distance-decay scale ``d0`` (km) for a sport.

    Prefers an active ``scoring_params`` row (``params.d0_km``); otherwise uses
    :data:`DEFAULT_D0_KM`, then a global fallback.
    """
    if db is not None and sport:
        try:
            from sqlalchemy import select

            from app.models import ScoringParams

            row = db.scalar(
                select(ScoringParams)
                .where(ScoringParams.sport == sport)
                .where(ScoringParams.active.is_(True))
                .order_by(ScoringParams.version.desc())
            )
            if row and isinstance(row.params, dict) and row.params.get("d0_km"):
                return float(row.params["d0_km"])
        except Exception:
            pass
    return DEFAULT_D0_KM.get(sport or "", _FALLBACK_D0_KM)
