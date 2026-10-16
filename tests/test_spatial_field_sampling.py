from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.spatial_fields.sampling import bilinear_uv, temporal_uv, wind_sample
from app.weather.vectors import wind_to_uv


def test_bilinear_interpolates_components_not_direction() -> None:
    sample = bilinear_uv(
        np.array([0.0, 1.0]),
        np.array([0.0, 1.0]),
        np.array([[1.0, 3.0], [3.0, 5.0]]),
        np.array([[2.0, 4.0], [4.0, 6.0]]),
        longitude=0.5,
        latitude=0.5,
    )

    assert sample is not None
    assert sample.u_ms == pytest.approx(3.0)
    assert sample.v_ms == pytest.approx(4.0)
    assert sample.speed_ms == pytest.approx(5.0)


def test_bilinear_accepts_descending_axes_and_grid_edges() -> None:
    sample = bilinear_uv(
        np.array([1.0, 0.0]),
        np.array([1.0, 0.0]),
        np.array([[4.0, 3.0], [2.0, 1.0]]),
        np.zeros((2, 2)),
        longitude=0.0,
        latitude=0.0,
    )

    assert sample is not None
    assert sample.u_ms == pytest.approx(1.0)


@pytest.mark.parametrize("missing", [np.nan, -32768.0])
def test_bilinear_refuses_a_missing_vector_neighbour(missing: float) -> None:
    sample = bilinear_uv(
        np.array([0.0, 1.0]),
        np.array([0.0, 1.0]),
        np.array([[1.0, missing], [1.0, 1.0]]),
        np.ones((2, 2)),
        longitude=0.5,
        latitude=0.5,
        nodata=-32768,
    )

    assert sample is None


def test_bilinear_returns_none_outside_coverage() -> None:
    values = np.ones((2, 2))
    assert bilinear_uv(
        np.array([0.0, 1.0]),
        np.array([0.0, 1.0]),
        values,
        values,
        longitude=-0.1,
        latitude=0.5,
    ) is None


def test_temporal_interpolation_crosses_north_without_angle_wrap() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sample = temporal_uv(
        wind_sample(-1.0, -10.0),
        wind_sample(1.0, -10.0),
        lower_time=start,
        upper_time=start + timedelta(hours=1),
        target_time=start + timedelta(minutes=30),
    )

    assert sample.u_ms == pytest.approx(0.0)
    assert sample.v_ms == pytest.approx(-10.0)
    assert sample.direction_from_deg == pytest.approx(0.0)


def test_temporal_interpolation_handles_359_to_1_degree_transition() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    lower_u, lower_v = wind_to_uv(10.0, 359.0)
    upper_u, upper_v = wind_to_uv(10.0, 1.0)
    sample = temporal_uv(
        wind_sample(lower_u, lower_v),
        wind_sample(upper_u, upper_v),
        lower_time=start,
        upper_time=start + timedelta(hours=1),
        target_time=start + timedelta(minutes=30),
    )

    assert sample.direction_from_deg == pytest.approx(0.0, abs=1e-9)
    assert sample.speed_ms == pytest.approx(9.9985, abs=0.001)


def test_calm_sample_has_no_direction() -> None:
    sample = wind_sample(0.0, 0.0)
    assert sample.speed_ms == 0.0
    assert sample.direction_from_deg is None
