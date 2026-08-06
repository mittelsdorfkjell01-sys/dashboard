"""Pure score-engine tests over synthetic values/histograms. No DB, no network.

Covers kite + surf gates, gustiness, level offsets, the climatology week/curve
scoring (live↔climatology consistency), describe_week and confidence.
"""

from __future__ import annotations

from app.scoring import (
    SCORING_PARAMS_V1,
    SeasonalRuleScorer,
    apply_gates,
    confidence_for,
    describe_week_entry,
    evaluate_conditions,
    evaluate_week_cells,
    climatology_curve,
    grade_magnitude,
    profile_thresholds,
)
from app.scoring.params import SWELL_BIN_REP_M, WIND_BIN_REP_KT
from tests.search_helpers import make_spot

GOOD, MOD, NO = "gut", "mäßig", "nein"


# --- kite gates ------------------------------------------------------------

def _kite(wind_kt, wind_dir=90, daylight=True, gust=None, editorial=None, profile=None):
    values = {"wind_kt": wind_kt, "wind_dir": wind_dir, "daylight": daylight}
    if gust is not None:
        values["gust_kt"] = gust
    return evaluate_conditions(values, editorial or {}, profile, "kitesurf")


def test_kite_ideal_direction_and_band_is_good():
    assert _kite(20)["rating"] == GOOD


def test_kite_below_min_is_no():
    res = _kite(8)
    assert res["rating"] == NO
    assert "wind_too_light" in res["reasons"]


def test_kite_above_max_is_no():
    res = _kite(40)
    assert res["rating"] == NO
    assert "wind_too_strong" in res["reasons"]


def test_kite_direction_outside_usable_is_no():
    editorial = {"usable_wind_directions": {"min": 0, "max": 45}}
    res = _kite(20, wind_dir=180, editorial=editorial)
    assert res["rating"] == NO
    assert "direction_unusable" in res["reasons"]


def test_kite_night_is_no():
    res = _kite(20, daylight=False)
    assert res["rating"] == NO
    assert "night" in res["reasons"]


# --- gustiness downgrade ---------------------------------------------------

def test_gust_ratio_downgrades_good_to_moderate():
    # 20 kt mean would be good; gust 30 -> ratio 1.5 >= 1.4 -> moderate
    res = _kite(20, gust=30)
    assert res["rating"] == MOD
    assert "gusty" in res["reasons"]


def test_gust_delta_downgrades_good_to_moderate():
    # ratio 1.35 (< 1.4) but delta 27-20 = 7? use 20 -> 28 = delta 8 >= 8
    res = _kite(20, gust=28)
    assert res["rating"] == MOD


def test_smooth_wind_stays_good():
    assert _kite(20, gust=23)["rating"] == GOOD  # ratio 1.15, delta 3


# --- level offsets ---------------------------------------------------------

def test_level_shifts_rating_beginner_vs_pro():
    # 18 kt: beginner ideal 14-20 -> good; pro ideal 20-33 -> moderate (too light)
    assert _kite(18, profile={"level": "beginner"})["rating"] == GOOD
    assert _kite(18, profile={"level": "expert"})["rating"] == MOD
    # 26 kt: beginner -> moderate (above 20); pro -> good
    assert _kite(26, profile={"level": "beginner"})["rating"] == MOD
    assert _kite(26, profile={"level": "expert"})["rating"] == GOOD


def test_profile_thresholds_offsets():
    offs = profile_thresholds("beginner", "kitesurf")
    assert offs["good_max_kt"] == -8.0
    assert profile_thresholds(None, "kitesurf") == {}


# --- surf gates ------------------------------------------------------------

def _surf(swell_m, period_s=11, swell_dir=200, daylight=True, editorial=None,
          wind_kt=10, wind_dir=200, profile=None):
    values = {
        "swell_m": swell_m, "period_s": period_s, "swell_dir": swell_dir,
        "daylight": daylight, "wind_kt": wind_kt, "wind_dir": wind_dir,
    }
    return evaluate_conditions(values, editorial or {}, profile, "surf")


def test_surf_ideal_is_good():
    assert _surf(1.5)["rating"] == GOOD


def test_surf_too_small_is_no():
    res = _surf(0.3)
    assert res["rating"] == NO and "swell_too_small" in res["reasons"]


def test_surf_short_period_is_no():
    res = _surf(1.5, period_s=6)
    assert res["rating"] == NO and "period_too_short" in res["reasons"]


def test_surf_strong_onshore_is_no():
    # facing 200 (beach faces SSW); wind from 200 at 25 kt > 18 -> strong onshore
    res = _surf(1.5, wind_kt=25, wind_dir=200, editorial={"facing": 200})
    assert res["rating"] == NO and "strong_onshore" in res["reasons"]


def test_surf_swell_direction_window():
    editorial = {"usable_swell_directions": {"min": 180, "max": 260}}
    assert _surf(1.5, swell_dir=200, editorial=editorial)["rating"] == GOOD
    assert _surf(1.5, swell_dir=20, editorial=editorial)["rating"] == NO


def test_surf_free_text_tide_does_not_crash():
    # editorial.tide may be a free-text note ("mid", "n/a") rather than a
    # structured {dependence, window} dict — the gate must tolerate it.
    assert _surf(1.5, editorial={"tide": "mid"})["rating"] == GOOD
    assert _surf(1.5, editorial={"tide": "n/a"})["rating"] == GOOD


# --- apply_gates directly --------------------------------------------------

def test_apply_gates_returns_reasons_list():
    passed, reasons = apply_gates(
        {"wind_kt": 5, "wind_dir": 90, "daylight": True}, {}, "kitesurf"
    )
    assert passed is False and "wind_too_light" in reasons


# --- climatology week scoring (live <-> climatology consistency) -----------

def _wind_week(cells: dict, week=1) -> dict:
    joint = [[0] * 6 for _ in range(16)]
    for (sector, mag), hours in cells.items():
        joint[sector][mag] = hours
    total = sum(h for h in cells.values())
    return {"week": week, "daylight_hours": total,
            "wind": {"joint": joint, "p50_kt": 16, "dir_dominant_deg": 90},
            "swell": {}, "air_p50_c": 15, "sst_p50_c": 16}


def test_climatology_week_is_share_of_passing_hours():
    # sector 4 (=90deg, usable); bins: 0->3kt(no), 3->16kt(good), 4->21.5(good), 5->28.5(mod)
    week = _wind_week({(4, 0): 5, (4, 3): 10, (4, 4): 3, (4, 5): 2})
    res = evaluate_week_cells(week, {}, None, "kitesurf")
    assert res["total_hours"] == 20
    assert res["usable_hours"] == 15   # all but the 5 too-light hours
    assert res["good_hours"] == 13     # 10 + 3
    assert res["pct_usable"] == 0.75
    assert res["gut_anteil"] == 0.65


def test_climatology_consistent_with_evaluate_conditions():
    # Manually evaluating each cell must reproduce the aggregate.
    cells = {(4, 0): 5, (4, 3): 10, (4, 5): 2}
    week = _wind_week(cells)
    usable = 0
    for (sector, mag), hours in cells.items():
        v = {"wind_kt": WIND_BIN_REP_KT[mag], "wind_dir": sector * 22.5, "daylight": True}
        if evaluate_conditions(v, {}, None, "kitesurf")["rating"] != NO:
            usable += hours
    assert evaluate_week_cells(week, {}, None, "kitesurf")["usable_hours"] == usable


def test_climatology_direction_gate_lowers_score():
    week = _wind_week({(4, 3): 10, (8, 3): 10})  # 90deg and 180deg, both 16 kt
    editorial = {"usable_wind_directions": {"min": 45, "max": 135}}  # only sector 4
    res = evaluate_week_cells(week, editorial, None, "kitesurf")
    assert res["usable_hours"] == 10        # the 180deg cell is gated out
    assert res["pct_usable"] == 0.5


def test_climatology_curve_length_and_threshold():
    weeks = [_wind_week({(4, 3): 10}, week=w) for w in range(1, 53)]
    clim = {"weeks": weeks}
    curve = climatology_curve(clim, {}, None, "kitesurf")
    assert len(curve) == 52
    assert all(w["pct_usable"] == 1.0 for w in curve)


# --- describe_week (stage 1, no gates, sparse editorial) -------------------

def test_describe_week_works_without_editorial():
    week = _wind_week({(4, 3): 10})
    desc = describe_week_entry(week)
    assert desc["week"] == 1
    assert desc["wind"]["p50_kt"] == 16
    assert desc["air_c"] == 15 and desc["sst_c"] == 16
    # no gates / editorial involved
    assert "rating" not in desc


# --- confidence ------------------------------------------------------------

def test_confidence_override_wins():
    clim = {"weeks": [_wind_week({(4, 3): 10})]}
    assert confidence_for(clim, {"confidence_override": "niedrig"}, "kitesurf") == "niedrig"


def test_confidence_wave_is_lower_than_wind():
    clim = {"weeks": [_wind_week({(4, 3): 10})]}
    assert confidence_for(clim, {}, "kitesurf") == "hoch"
    assert confidence_for(clim, {}, "surf") == "mittel"


def test_confidence_no_climatology_is_low():
    assert confidence_for(None, {}, "kitesurf") == "niedrig"


def test_confidence_thermal_downgrades():
    clim = {"weeks": [_wind_week({(4, 3): 10})]}
    assert confidence_for(clim, {"wind_type": "thermal"}, "kitesurf") == "mittel"


# --- ranking-seam: the scorer must score the *selected* sport ---------------

def _both_week(w: int) -> dict:
    wind = [[0] * 6 for _ in range(16)]
    wind[4][3] = 18   # 16 kt -> good kite
    wind[4][0] = 2    # 3 kt -> too light
    swell = [[0] * 6 for _ in range(16)]
    swell[8][0] = 20  # 0.25 m -> below surf minimum -> all nein
    return {
        "week": w, "daylight_hours": 20,
        "wind": {"joint": wind, "p50_kt": 16, "dir_dominant_deg": 90},
        "swell": {"joint": swell, "period_p50_s": 11, "dir_dominant_deg": 180},
    }


def test_seasonal_scorer_is_sport_aware():
    # spot whose climatology is great for kite but useless for surf; surf is the
    # *first* listed sport, so falling back to it (the old bug) scores ~0.
    spot = make_spot("Both", 54.4, 10.2, ["surf", "kitesurf"])
    spot.climatology = {"weeks": [_both_week(w) for w in range(1, 53)]}
    scorer = SeasonalRuleScorer()

    kite = scorer.score(spot, {"week": 1}, {"sport": "kitesurf"})
    surf = scorer.score(spot, {"week": 1}, {"sport": "surf"})
    default = scorer.score(spot, {"week": 1}, None)  # -> first sport = surf

    assert kite > 0.8          # selected sport is scored correctly
    assert surf == 0.0
    assert default == surf     # no sport -> first listed sport


def test_search_service_threads_sport_into_profile():
    from app.search.service import _with_sport

    assert _with_sport({"level": "expert"}, "surf") == {"level": "expert", "sport": "surf"}
    assert _with_sport(None, "kitesurf") == {"sport": "kitesurf"}
    assert _with_sport({"level": "expert"}, None) == {"level": "expert"}  # unchanged
