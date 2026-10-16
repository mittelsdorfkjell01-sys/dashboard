from app.api.weather_fields import summarize_model_spread


def test_model_spread_reports_observed_range_without_inventing_confidence() -> None:
    result = summarize_model_spread(
        [
            {"speed_ms": 4.0, "gust_ms": 7.0},
            {"speed_ms": 6.5, "gust_ms": 11.0},
        ]
    )

    assert result == {
        "model_count": 2,
        "speed_min_ms": 4.0,
        "speed_max_ms": 6.5,
        "speed_spread_ms": 2.5,
        "gust_min_ms": 7.0,
        "gust_max_ms": 11.0,
        "gust_spread_ms": 4.0,
    }
