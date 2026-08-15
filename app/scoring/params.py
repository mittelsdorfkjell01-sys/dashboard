"""Version 1 scoring parameters (one set per sport) + parameter resolution.

These are the *global* layer of the score model. The exact numbers reference the
external "Score-Parameter-Doc" (not in the repo); the values below are a
documented, reasonable interpretation and are versioned via
``scoring_params.version`` so they can evolve without breaking pre-computed
scores. The other two layers are the spot's ``editorial`` (e.g. usable
directions, tide dependence, overrides) and the rider ``profile`` (level offsets).
"""

from __future__ import annotations

from typing import Any

from app.era5.bins import SWELL_HEIGHT_BINS_M, WIND_SPEED_BINS_KT

SCORING_PARAMS_VERSION = 1

# Fraction of a week's daylight hours that must be usable for the week to count
# as "good" (used by season curves / good-week flags).
WEEK_GOOD_THRESHOLD = 0.40

# Distance-decay scale (km) for search ranking — global per the parameter doc.
DISTANCE_D0_KM = 40.0


def _wind_params() -> dict:
    """Shared parameter block for the wind sports (kite/wind/wing)."""
    return {
        "sport_type": "wind",
        "daylight_required": True,
        # absolute usable band (gate) and the ideal band (good vs moderate)
        "wind": {"min_kt": 12.0, "max_kt": 35.0, "good_min_kt": 16.0, "good_max_kt": 28.0},
        # gustiness downgrade (good -> moderate)
        "gust_ratio_downgrade": 1.4,
        "gust_delta_downgrade_kt": 8.0,
        # rider-level offsets applied to the *ideal* band only
        "level_offsets": {
            "beginner": {"good_min_kt": -2.0, "good_max_kt": -8.0},
            "advanced": {"good_min_kt": 2.0, "good_max_kt": 3.0},
            "expert": {"good_min_kt": 4.0, "good_max_kt": 5.0},
        },
        "week_good_threshold": WEEK_GOOD_THRESHOLD,
        "d0_km": DISTANCE_D0_KM,
    }


SCORING_PARAMS_V1: dict[str, dict] = {
    "kitesurf": _wind_params(),
    "windsurf": _wind_params(),
    "wing": _wind_params(),
    "surf": {
        "sport_type": "wave",
        "daylight_required": True,
        "swell": {
            "min_m": 0.6,
            "max_m": 4.0,
            "good_min_m": 1.0,
            "good_max_m": 2.5,
            "period_min_s": 8.0,
        },
        # a clean wave dies under strong onshore wind
        "onshore_wind_max_kt": 18.0,
        # default: not tide-dependent (editorial may override per spot)
        "tide": {"dependence": False},
        "level_offsets": {
            "beginner": {"good_min_m": -0.4, "good_max_m": -1.0},
            "advanced": {"good_min_m": 0.3, "good_max_m": 0.5},
            "expert": {"good_min_m": 0.5, "good_max_m": 1.0},
        },
        "week_good_threshold": WEEK_GOOD_THRESHOLD,
        "d0_km": DISTANCE_D0_KM,
    },
}


def get_params(sport: str, db: Any | None = None, version: int | None = None) -> dict:
    """Resolve the global parameter set for ``sport``.

    Prefers the active ``scoring_params`` row from the DB (so a deployed override
    wins); otherwise returns the in-code :data:`SCORING_PARAMS_V1`. Raises
    ``KeyError`` for an unknown sport with no DB row.
    """
    if db is not None:
        try:
            from sqlalchemy import select

            from app.models import ScoringParams

            stmt = select(ScoringParams).where(ScoringParams.sport == sport)
            if version is not None:
                stmt = stmt.where(ScoringParams.version == version)
            else:
                stmt = stmt.where(ScoringParams.active.is_(True))
            row = db.scalar(stmt.order_by(ScoringParams.version.desc()))
            if row and isinstance(row.params, dict):
                return row.params
        except Exception:
            pass
    return SCORING_PARAMS_V1[sport]


def bin_representatives(edges: tuple[float, ...]) -> list[float]:
    """Representative value for each histogram bin given its lower edges.

    Interior bins use the midpoint; the open-ended last bin extends by half the
    previous bin width.
    """
    reps: list[float] = []
    for i in range(len(edges)):
        if i < len(edges) - 1:
            reps.append((edges[i] + edges[i + 1]) / 2.0)
        else:
            prev_width = edges[i] - edges[i - 1] if i > 0 else edges[i]
            reps.append(edges[i] + prev_width / 2.0)
    return reps


WIND_BIN_REP_KT: list[float] = bin_representatives(WIND_SPEED_BINS_KT)
SWELL_BIN_REP_M: list[float] = bin_representatives(SWELL_HEIGHT_BINS_M)


def seed_scoring_params(db: Any) -> int:
    """Upsert the version-1 active parameter row for each sport. Idempotent.

    Returns the number of rows inserted.
    """
    from sqlalchemy import select

    from app.models import ScoringParams

    inserted = 0
    for sport, params in SCORING_PARAMS_V1.items():
        existing = db.scalar(
            select(ScoringParams)
            .where(ScoringParams.sport == sport)
            .where(ScoringParams.version == SCORING_PARAMS_VERSION)
        )
        if existing is not None:
            existing.params = params
            existing.active = True
            continue
        db.add(
            ScoringParams(
                sport=sport,
                version=SCORING_PARAMS_VERSION,
                active=True,
                params=params,
            )
        )
        inserted += 1
    db.commit()
    return inserted
