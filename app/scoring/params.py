"""Versioned scoring parameters (one set per sport) + parameter resolution.

These are the *global* layer of the score model. The exact numbers reference the
external "Score-Parameter-Doc" (not in the repo); the values below are a
documented, reasonable interpretation and are versioned via
``scoring_params.version`` so they can evolve without breaking pre-computed
scores. The other two layers are the spot's ``editorial`` (e.g. usable
directions, tide dependence, overrides) and the rider ``profile`` (level offsets).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.era5.bins import SWELL_HEIGHT_BINS_M, WIND_SPEED_BINS_KT

SCORING_PARAMS_VERSION = 4

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


def _with_competition(base: dict) -> dict:
    """Copy a V1 payload and add V2's competition offsets."""
    params = deepcopy(base)
    expert = params["level_offsets"]["expert"]
    if params["sport_type"] == "wind":
        params["level_offsets"]["competition"] = {
            "good_min_kt": float(expert["good_min_kt"]) + 1.0,
            "good_max_kt": float(expert["good_max_kt"]) + 1.0,
        }
    else:
        # The Phase-A "+1 kt" rule only applies to wind sports. Surf still gets
        # the canonical key, initially equal to expert.
        params["level_offsets"]["competition"] = deepcopy(expert)
    return params


def _version_2_params() -> dict[str, dict]:
    """Add the canonical competition level without mutating historical V1."""
    return {
        sport: _with_competition(params)
        for sport, params in SCORING_PARAMS_V1.items()
    }


SCORING_PARAMS_V2: dict[str, dict] = _version_2_params()

# Phase-B rider-model calibration. These values are the documented code fallback
# and are byte-for-byte equivalent to the 0067 migration seed. Production reads
# the active scoring_params row first, so later calibration never needs a deploy.
RIDER_MODEL_KITESURF: dict = {
    "k_board": {
        "twintip": 2.2,
        "surfboard": 2.0,
        "foil": 1.4,
        "bigair_twintip": 2.35,
    },
    "f_lo": 0.8,
    "f_hi": 1.35,
    "levels": {
        "beginner": {"max_kt": 24.0, "gust_tolerance_kt": 5.0},
        "advanced": {"max_kt": 34.0, "gust_tolerance_kt": 8.0},
        "expert": {"max_kt": 42.0, "gust_tolerance_kt": 12.0},
        "competition": {"max_kt": 50.0, "gust_tolerance_kt": 15.0},
    },
}

DEFAULT_RIDER_KITESURF: dict = {
    "weight_kg": 78.0,
    "level": "advanced",
    "quiver": [
        {"kind": "kite", "size": 9.0},
        {"kind": "kite", "size": 12.0},
        {"kind": "board", "board_type": "twintip"},
    ],
    "style_weights": {
        "freeride": 2,
        "freestyle": 1,
        "big_air": 1,
        "wave_riding": 0,
        "wavekite": 0,
    },
    "travel_mode": "day_trip",
}


def _with_rider_model(base: dict, sport: str) -> dict:
    """Copy V2 and add Phase-B blocks without mutating historical payloads."""
    params = deepcopy(base)
    if sport == "kitesurf":
        params["rider_model"] = {"kitesurf": deepcopy(RIDER_MODEL_KITESURF)}
        params["default_rider"] = {"kitesurf": deepcopy(DEFAULT_RIDER_KITESURF)}
    return params


SCORING_PARAMS_V3: dict[str, dict] = {
    sport: _with_rider_model(params, sport)
    for sport, params in SCORING_PARAMS_V2.items()
}


def _with_evaluation(base: dict, sport: str) -> dict:
    """Add Phase-E social calibration controls without auto-activating them."""
    params = deepcopy(base)
    if sport == "kitesurf":
        params["social"] = {
            "weight": 0.02,
            "min_group_size": 20,
            "validated": False,
            "similar_band": False,
        }
        params["parameter_log"] = [
            {
                "version": 4,
                "kind": "social_signal",
                "weight": 0.02,
                "effective": False,
                "reason": "Initial small weight; activation requires measured improvement",
            }
        ]
    return params


SCORING_PARAMS_V4: dict[str, dict] = {
    sport: _with_evaluation(params, sport)
    for sport, params in SCORING_PARAMS_V3.items()
}
SCORING_PARAMS_BY_VERSION: dict[int, dict[str, dict]] = {
    1: SCORING_PARAMS_V1,
    2: SCORING_PARAMS_V2,
    3: SCORING_PARAMS_V3,
    4: SCORING_PARAMS_V4,
}


def get_params(sport: str, db: Any | None = None, version: int | None = None) -> dict:
    """Resolve the global parameter set for ``sport``.

    Prefers the active ``scoring_params`` row from the DB (so a deployed override
    wins); otherwise returns the requested in-code version or the current V4. Raises
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
    fallback_version = version or SCORING_PARAMS_VERSION
    return SCORING_PARAMS_BY_VERSION[fallback_version][sport]


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
    """Ensure immutable parameter versions exist; activate only the current one.

    Returns the number of rows inserted.
    """
    from sqlalchemy import select

    from app.models import ScoringParams

    inserted = 0
    initial_rows = list(db.scalars(select(ScoringParams)).all())
    active_versions = {
        sport: max(row.version for row in initial_rows if row.sport == sport and row.active)
        for sport in SCORING_PARAMS_V1
        if any(row.sport == sport and row.active for row in initial_rows)
    }
    for version, version_params in SCORING_PARAMS_BY_VERSION.items():
        for sport, params in version_params.items():
            existing = db.scalar(
                select(ScoringParams)
                .where(ScoringParams.sport == sport)
                .where(ScoringParams.version == version)
            )
            if existing is None:
                payload = params
                if version in (2, 3, 4):
                    source_version = version - 1
                    stored_source = db.scalar(
                        select(ScoringParams)
                        .where(ScoringParams.sport == sport)
                        .where(ScoringParams.version == source_version)
                    )
                    if stored_source is not None and isinstance(stored_source.params, dict):
                        payload = (
                            _with_competition(stored_source.params)
                            if version == 2
                            else (
                                _with_rider_model(stored_source.params, sport)
                                if version == 3
                                else _with_evaluation(stored_source.params, sport)
                            )
                        )
                db.add(
                    ScoringParams(
                        sport=sport,
                        version=version,
                        active=False,
                        params=deepcopy(payload),
                    )
                )
                inserted += 1
    db.flush()
    # Deploying a newer code baseline advances older seed versions once. A
    # human-approved version above the code baseline remains active across
    # process restarts and deploys.
    for sport in SCORING_PARAMS_V1:
        if active_versions.get(sport, 0) <= SCORING_PARAMS_VERSION:
            for row in db.scalars(
                select(ScoringParams).where(ScoringParams.sport == sport)
            ).all():
                row.active = row.version == SCORING_PARAMS_VERSION
    db.commit()
    return inserted
