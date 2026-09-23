"""Score engine (Sprint 4) + the ranking ``Scorer`` seam (used by Sprint 5).

A rule-based, categorical evaluation (``gut`` / ``mäßig`` / ``nein``) parametrised
over three layers: ``scoring_params`` (global, versioned), spot ``editorial``, and
the rider ``profile`` (level). The *same* :func:`evaluate_conditions` runs both
live and over the climatology histogram, so seasonal and now-badges stay
consistent.

  evaluate_conditions      values -> {rating, reasons}        (core)
  apply_gates              hard pass/fail gates
  grade_magnitude          gut vs mäßig (with gust downgrade + level offsets)
  profile_thresholds       per-level threshold offsets
  score_live               now-badge via the live cache
  score_climatology_week   usable-hours share for a week
  score_climatology_curve  pct_usable[52] + good weeks
  describe_week            Stage-1 description (no gates)
  spot_confidence          hoch | mittel | niedrig

The ranking seam (`Scorer`, `default_scorer`, `distance_decay_d0`) lives in
`engine` and is consumed by `app.search`.
"""

from app.scoring.confidence import confidence_for, spot_confidence
from app.scoring.climatology import (
    climatology_curve,
    describe_week,
    describe_week_entry,
    evaluate_week_cells,
    score_climatology_curve,
    score_climatology_week,
)
from app.scoring.engine import (
    DEFAULT_D0_KM,
    InterimScorer,
    Scorer,
    SeasonalRuleScorer,
    default_scorer,
    distance_decay_d0,
)
from app.scoring.eligibility import is_recommendable, recommendability_gaps
from app.scoring.evaluate import evaluate_conditions
from app.scoring.gates import apply_gates
from app.scoring.live import score_live
from app.scoring.magnitude import grade_magnitude
from app.scoring.params import (
    SCORING_PARAMS_V1,
    SCORING_PARAMS_V2,
    SCORING_PARAMS_V3,
    SCORING_PARAMS_VERSION,
    get_params,
    seed_scoring_params,
)
from app.scoring.profile import profile_thresholds

__all__ = [
    # seam
    "Scorer",
    "SeasonalRuleScorer",
    "InterimScorer",
    "default_scorer",
    "distance_decay_d0",
    "DEFAULT_D0_KM",
    "is_recommendable",
    "recommendability_gaps",
    # params
    "SCORING_PARAMS_V1",
    "SCORING_PARAMS_V2",
    "SCORING_PARAMS_V3",
    "SCORING_PARAMS_VERSION",
    "get_params",
    "seed_scoring_params",
    "profile_thresholds",
    # core evaluation
    "evaluate_conditions",
    "apply_gates",
    "grade_magnitude",
    # live + climatology
    "score_live",
    "score_climatology_week",
    "score_climatology_curve",
    "climatology_curve",
    "evaluate_week_cells",
    "describe_week",
    "describe_week_entry",
    # confidence
    "spot_confidence",
    "confidence_for",
]
