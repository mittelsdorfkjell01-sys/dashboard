"""Pure Personal-Band and fingerprint contracts."""

from copy import deepcopy

from app.scoring.params import SCORING_PARAMS_V3
from app.scoring.rider.band import personal_band, profile_fingerprint


PARAMS = SCORING_PARAMS_V3["kitesurf"]


def _profile(weight: float, *, board_type: str = "twintip", level: str = "advanced") -> dict:
    return {
        "weight_kg": weight,
        "level": level,
        "quiver": [
            {"kind": "kite", "size": 12, "active": True},
            {"kind": "board", "board_type": board_type, "active": True},
        ],
        "style_weights": {"freeride": 2},
        "travel_mode": "day_trip",
    }


def test_more_weight_moves_single_kite_band_up():
    light = personal_band(_profile(65), "kitesurf", PARAMS)
    heavy = personal_band(_profile(90), "kitesurf", PARAMS)
    assert heavy.min_kt > light.min_kt
    assert heavy.ideal_lo_kt > light.ideal_lo_kt
    assert heavy.ideal_hi_kt > light.ideal_hi_kt
    assert heavy.max_kt > light.max_kt


def test_foil_board_lowers_minimum_wind():
    twintip = personal_band(_profile(78), "kitesurf", PARAMS)
    foil = personal_band(_profile(78, board_type="foil"), "kitesurf", PARAMS)
    assert foil.min_kt < twintip.min_kt


def test_level_cap_limits_the_upper_band():
    profile = _profile(120, level="beginner")
    profile["quiver"] = [
        {"kind": "kite", "size": 6},
        {"kind": "kite", "size": 8},
        {"kind": "board", "board_type": "bigair_twintip"},
    ]
    beginner = personal_band(profile, "kitesurf", PARAMS)
    profile["level"] = "competition"
    competition = personal_band(profile, "kitesurf", PARAMS)
    assert beginner.max_kt == PARAMS["rider_model"]["kitesurf"]["levels"]["beginner"]["max_kt"]
    assert competition.max_kt > beginner.max_kt


def test_empty_quiver_uses_default_sizes_at_the_users_weight():
    profile = _profile(90)
    profile["quiver"] = []
    band = personal_band(profile, "kitesurf", PARAMS)
    average = deepcopy(PARAMS["default_rider"]["kitesurf"])
    average["weight_kg"] = 90
    expected = personal_band(average, "kitesurf", PARAMS)
    assert (
        band.min_kt, band.ideal_lo_kt, band.ideal_hi_kt,
        band.max_kt, band.gust_tolerance_kt,
    ) == (
        expected.min_kt, expected.ideal_lo_kt, expected.ideal_hi_kt,
        expected.max_kt, expected.gust_tolerance_kt,
    )
    assert band.fingerprint != expected.fingerprint  # the user's own style remains part of the key


def test_single_kite_stays_narrow_and_fingerprint_is_stable():
    profile = _profile(78)
    first = personal_band(profile, "kitesurf", PARAMS)
    second = personal_band(deepcopy(profile), "kitesurf", deepcopy(PARAMS))
    assert first.ideal_lo_kt == first.ideal_hi_kt
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint == profile_fingerprint(
        first, profile["style_weights"], profile["travel_mode"]
    )
    assert hash(first)
