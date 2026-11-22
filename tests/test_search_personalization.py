from __future__ import annotations

from app.recommendations.service import RiderUtilityScorer
from app.scoring.params import get_params
from app.scoring.rider.band import personal_band
from app.scoring.rider.resolve import RiderContext
from tests.search_helpers import make_spot


def test_rider_window_score_logs_aggregate_components():
    params = get_params("kitesurf")
    profile = dict(params["default_rider"]["kitesurf"])
    rider = RiderContext(
        sport="kitesurf",
        source="default",
        profile=profile,
        band=personal_band(profile, "kitesurf", params),
        profile_version=None,
    )
    spot = make_spot("Window", 54.41, 10.22, ["kitesurf"])

    class WeeklyScorer:
        def score(self, spot, time_context=None, profile=None):
            return {1: 0.8, 2: 0.2}[time_context["week"]]

    scorer = RiderUtilityScorer(WeeklyScorer(), rider)
    values = scorer.score_window(spot, [1, 2], None)
    components = scorer.scored[spot.id][1]

    assert values == [0.48, 0.12]
    assert components["condition_fit"] == 0.5
    assert components["utility"] == 0.3
    assert components["source"] == "search_window"
