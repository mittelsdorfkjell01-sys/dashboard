"""Composition of the independent climatological and microscale wind priors."""

from types import SimpleNamespace

import pytest

from app.forecast.combined_correction import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    combine_sector_results,
)


def _result(factors, *, status="ok", confidence="ok"):
    return SimpleNamespace(
        status=status,
        provenance={
            "method": "component",
            "gwa_version": "GWA-3.0",
            "reference_model": "era5",
            "window": [2008, 2017],
            "grid_cell": [54.5, 8.5],
        },
        sectors=[
            SimpleNamespace(
                index=index,
                start_deg=float(index * 30),
                end_deg=float((index + 1) * 30 % 360),
                speed_factor=factor,
                direction_offset_deg=0.0,
                confidence=confidence,
                saturated=False,
            )
            for index, factor in enumerate(factors)
        ],
    )


def test_combined_prior_multiplies_matching_sector_factors_and_clamps():
    result = combine_sector_results(_result([1.2] * 12), _result([1.1] * 11 + [1.5]))

    assert result.status == STATUS_OK
    assert len(result.sectors) == 12
    assert result.sectors[0].speed_factor == pytest.approx(1.32)
    assert result.sectors[-1].speed_factor == pytest.approx(1.6)
    assert result.sectors[-1].saturated is True
    components = result.provenance["sector_components"]["0"]
    assert components["gwa"] == 1.2
    assert components["microscale"] == 1.1
    assert components["gwa_saturated"] is False
    assert components["microscale_saturated"] is False


def test_combined_prior_fails_closed_if_either_component_is_unavailable():
    result = combine_sector_results(
        _result([1.0] * 12),
        _result([], status="microscale_unavailable"),
    )

    assert result.status == STATUS_UNAVAILABLE
    assert result.sectors == []


def test_combined_prior_fails_closed_on_incomplete_sector_axis():
    result = combine_sector_results(_result([1.0] * 12), _result([1.0] * 11))

    assert result.status == STATUS_UNAVAILABLE
    assert result.sectors == []
