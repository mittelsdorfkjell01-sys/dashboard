import inspect
import pytest
from app.weather.shadow_metrics import (
    aggregate_observations,
    circular_error,
    lead_band,
    verification_metrics,
)


def test_lead_bands_and_circular_direction_error():
    assert [lead_band(x) for x in (0, 25, 49, 73, 121, 241)] == [
        "0-24h",
        "25-48h",
        "49-72h",
        "73-120h",
        "121-240h",
        None,
    ]
    assert circular_error(355, 5) == 10


def test_observation_aggregation_is_vectorial_and_gust_is_maximum():
    result = aggregate_observations(
        [
            {
                "quality_status": "valid",
                "wind_speed_ms": 10,
                "wind_direction_deg": 350,
                "wind_gust_ms": 13,
            },
            {
                "quality_status": "valid",
                "wind_speed_ms": 10,
                "wind_direction_deg": 10,
                "wind_gust_ms": 15,
            },
            {
                "quality_status": "suspect",
                "wind_speed_ms": 99,
                "wind_direction_deg": 180,
                "wind_gust_ms": 99,
            },
        ]
    )
    assert result["wind_direction_deg"] == pytest.approx(0, abs=1e-6)
    assert result["wind_gust_ms"] == 15 and result["sample_count"] == 2


def test_metrics_include_counts_vectors_gusts_and_event_matrix():
    pairs = [
        (
            {
                "wind_speed_ms": 8,
                "wind_gust_ms": 10,
                "wind_direction_deg": 0,
                "u_ms": 0,
                "v_ms": -8,
            },
            {
                "wind_speed_ms": 7.5,
                "wind_gust_ms": 9,
                "wind_direction_deg": 350,
                "u_ms": 1.2,
                "v_ms": -7.4,
            },
        )
    ]
    result = verification_metrics(pairs)
    assert result["sample_count"] == 1 and result["speed"]["bias"] == 0.5
    assert result["direction_mae_deg"] == 10 and result["gust"]["mae"] == 1
    assert result["event_14kn"]["hits"] == 1


def test_public_forecast_modules_do_not_import_shadow_study():
    from app.forecast import publisher
    from app.live import service

    assert "weather.shadow_study" not in inspect.getsource(publisher)
    assert "weather.shadow_study" not in inspect.getsource(service)


def test_phase4_admin_requires_auth(anon_client):
    assert anon_client.get("/admin/weather/shadow-study/status").status_code in (
        401,
        403,
    )
