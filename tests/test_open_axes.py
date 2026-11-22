"""Pure tests for Sprint 6: time windows, coverage/intensity ranking, open time,
and the region aggregate (counting working spots, not averaging). No DB/network."""

from __future__ import annotations

import app.search.timewindow as timewindow
from app.scoring.region import region_season_weeks, region_score_series, smooth_circular
from app.search.timewindow import (
    best_weeks_for_area,
    coverage_intensity,
    months_to_weeks,
    rank_by_timewindow,
    resolve_time_window,
    spot_week_scores,
)
from tests.search_helpers import make_spot


# --- build spots with a known per-week pct_usable pattern ------------------

def _week(week: int, kind: str, *, wind_p50=16.0, sst=18.0, air=15.0) -> dict:
    """kind -> pct_usable: full=1.0, half=0.5, low=0.3, off=0.0 (kite, 16 kt cell)."""
    joint = [[0] * 6 for _ in range(16)]
    if kind == "full":
        joint[4][3] = 10
    elif kind == "half":
        joint[4][3] = 5
        joint[4][0] = 5
    elif kind == "low":
        joint[4][3] = 3
        joint[4][0] = 7
    else:  # off
        joint[4][0] = 10
    return {
        "week": week, "daylight_hours": 10,
        "wind": {"joint": joint, "p50_kt": wind_p50, "dir_dominant_deg": 90},
        "swell": {}, "air_p50_c": air, "sst_p50_c": sst,
    }


def _spot(name, kinds: dict[int, str], *, sports=("kitesurf",), **env):
    weeks = [_week(w, kinds.get(w, "off"), **env) for w in range(1, 53)]
    return make_spot(name, 54.4, 10.2, list(sports),
                     slug=name.lower(), climatology={"weeks": weeks})


# --- resolve_time_window ---------------------------------------------------

def test_resolve_time_window_open_is_full_season():
    win = resolve_time_window("season", None)
    assert win["open"] is True and len(win["weeks"]) == 52


def test_resolve_time_window_month_and_weeks():
    assert resolve_time_window("season", {"month": 6})["weeks"] == months_to_weeks([6])
    assert resolve_time_window("season", {"weeks": [10, 12]})["weeks"] == [10, 11, 12]


def test_resolve_time_window_current_caps_at_7_days():
    assert resolve_time_window("current", {"days": 20})["days"] == 7
    assert resolve_time_window("current", None)["open"] is True


def test_spot_week_scores_without_climatology_is_zero():
    bare = make_spot("Bare", 54.4, 10.2, ["kitesurf"])
    assert spot_week_scores(bare, "kitesurf", None) == [0.0] * 52


# --- coverage / intensity --------------------------------------------------

def test_coverage_intensity_basic():
    scores = [0.0] * 52
    scores[0], scores[1], scores[2], scores[3] = 1.0, 1.0, 0.3, 0.0
    cov, inten = coverage_intensity(scores, [1, 2, 3, 4], 0.40)
    assert cov == 0.5                      # 2 of 4 weeks >= 0.40
    assert round(inten, 4) == 0.575        # mean of 1,1,0.3,0


def test_ranking_is_coverage_first():
    # A: reliably mediocre (always covered); B: spikier, higher mean but thinner coverage
    a = _spot("A", {1: "half", 2: "half", 3: "half", 4: "half"})
    b = _spot("B", {1: "full", 2: "full", 3: "low", 4: "low"})
    ranked = rank_by_timewindow([b, a], {"weeks": [1, 2, 3, 4]}, "kitesurf", None)

    assert [r["spot"].slug for r in ranked] == ["a", "b"]   # coverage wins
    assert ranked[0]["coverage"] > ranked[1]["coverage"]
    assert ranked[1]["intensity"] > ranked[0]["intensity"]  # B is more intense


def test_ranking_intensity_breaks_ties():
    c = _spot("C", {1: "full", 2: "full", 3: "off", 4: "off"})  # cov .5, inten .5
    d = _spot("D", {1: "half", 2: "half", 3: "off", 4: "off"})  # cov .5, inten .25
    ranked = rank_by_timewindow([d, c], {"weeks": [1, 2, 3, 4]}, "kitesurf", None)
    assert [r["spot"].slug for r in ranked] == ["c", "d"]
    assert ranked[0]["coverage"] == ranked[1]["coverage"]


# --- open time: best weeks for an area -------------------------------------

def test_best_weeks_single_spot_is_its_curve():
    s = _spot("Solo", {10: "full", 20: "half"})
    weeks = best_weeks_for_area([s], "kitesurf", None)
    assert weeks[0]["week"] == 10 and weeks[0]["score"] == 1.0
    assert weeks[1]["week"] == 20 and weeks[1]["score"] == 0.5


def test_best_weeks_area_takes_best_spot_per_week():
    s1 = _spot("S1", {10: "full"})
    s2 = _spot("S2", {20: "full"})
    weeks = {w["week"]: w for w in best_weeks_for_area([s1, s2], "kitesurf", None)}
    assert weeks[10]["score"] == 1.0 and weeks[10]["spots_working"] == 1
    assert weeks[20]["score"] == 1.0 and weeks[20]["spots_working"] == 1
    assert weeks[1]["score"] == 0.0


def test_timewindow_params_are_loaded_once_per_sport(monkeypatch):
    spots = [_spot("A", {1: "full"}), _spot("B", {2: "full"})]
    calls = 0
    original = timewindow.get_params

    def counted(sport, db=None):
        nonlocal calls
        calls += 1
        return original(sport)

    monkeypatch.setattr(timewindow, "get_params", counted)
    rank_by_timewindow(spots, {"weeks": [1, 2]}, "kitesurf", None, db=object())
    assert calls == 1


def test_region_params_are_loaded_once_per_sport(monkeypatch):
    import app.scoring.region as region

    spots = [_spot("A", {1: "full"}), _spot("B", {2: "full"})]
    calls = 0
    original = region.get_params

    def counted(sport, db=None):
        nonlocal calls
        calls += 1
        return original(sport)

    monkeypatch.setattr(region, "get_params", counted)
    region_season_weeks(spots, "kitesurf", db=object())
    assert calls == 1


# --- region aggregate: count working spots, don't average ------------------

def test_region_aggregate_counts_working_spots():
    # week 1: only A works; medians still computed over both spots
    a = _spot("A", {1: "full"}, wind_p50=20.0, sst=19.0, air=16.0)
    b = _spot("B", {1: "off"}, wind_p50=10.0, sst=17.0, air=14.0)
    weeks = {w["week"]: w for w in region_season_weeks([a, b])}

    assert weeks[1]["spots_working"] == 1            # counted, not averaged to 0.5
    assert weeks[1]["wind_p50"] == 15.0              # median(20, 10)
    assert weeks[1]["sst_p50"] == 18.0               # median(19, 17)
    assert weeks[2]["spots_working"] == 0


def test_region_score_series_is_best_spot():
    a = _spot("A", {1: "full"})
    b = _spot("B", {1: "half"})
    series = region_score_series([a, b])
    assert series[0] == 1.0                          # best spot in week 1


def test_smooth_circular_preserves_length_and_smooths():
    series = [0.0] * 52
    series[0] = 1.0
    smoothed = smooth_circular(series, window=5)
    assert len(smoothed) == 52
    assert smoothed[0] < 1.0                         # spike spread to neighbours
    assert smoothed[1] > 0.0 and smoothed[-1] > 0.0  # circular: wraps both ways
