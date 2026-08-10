from __future__ import annotations

import pytest

from app.weather.consensus import WindMember, calculate_wind_consensus
from app.weather.contracts import ModelFamily
from app.weather.weights import normalized_model_weights


def test_aifs_never_exceeds_ten_percent_after_missing_models():
    weights = normalized_model_weights(
        [("aifs", ModelFamily.AIFS), ("gfs", ModelFamily.GFS)], lead_hours=12
    )
    assert weights["aifs"] == pytest.approx(0.10)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_regional_family_weight_is_shared_not_duplicated():
    weights = normalized_model_weights(
        [
            ("icon_d2", ModelFamily.REGIONAL),
            ("knmi", ModelFamily.REGIONAL),
            ("ifs", ModelFamily.IFS),
            ("gfs", ModelFamily.GFS),
            ("aifs", ModelFamily.AIFS),
        ],
        lead_hours=24,
    )
    assert weights["icon_d2"] == pytest.approx(0.25)
    assert weights["knmi"] == pytest.approx(0.25)


def test_wind_consensus_uses_vector_direction_and_enforces_gust_floor():
    result = calculate_wind_consensus(
        [
            WindMember("icon_d2", 10.0, 350.0, 8.0),
            WindMember("ecmwf_ifs", 10.0, 10.0, 9.0),
        ],
        lead_hours=12,
    )
    assert result is not None
    assert result.direction_deg == pytest.approx(356.66, abs=0.1)
    assert result.gust_ms >= result.speed_ms
