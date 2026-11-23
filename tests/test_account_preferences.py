"""Pure validation checks for per-sport account conditions."""

import pytest
from pydantic import ValidationError

from app.api.account import PreferencesPatch


def test_conditions_accept_optional_ranges_per_sport():
    patch = PreferencesPatch.model_validate({
        "sports": ["surf", "wing"],
        "conditions": {
            "surf": {"waveMinM": 0.8, "waveMaxM": 2.5},
            "wing": {"windMinKn": 12, "windMaxKn": 28, "waterTempMinC": 10},
        },
    })
    assert patch.model_dump(exclude_none=True)["conditions"]["surf"] == {
        "waveMinM": 0.8, "waveMaxM": 2.5,
    }


@pytest.mark.parametrize("conditions", [
    {"wing": {"windMinKn": 30, "windMaxKn": 12}},
    {"surf": {"waveMinM": 3, "waveMaxM": 1}},
    {"wing": {"windMinKn": -1}},
    {"surf": {"waveMaxM": 13}},
    {"paragliding": {"windMinKn": 10}},
    {"wing": {"waterTempMinC": 45}},
    {"wing": {"windMinKn": 10, "unknown": 1}},
])
def test_conditions_reject_invalid_values(conditions):
    with pytest.raises(ValidationError):
        PreferencesPatch.model_validate({"conditions": conditions})


def test_preferences_reject_unknown_top_level_setting():
    with pytest.raises(ValidationError):
        PreferencesPatch.model_validate({"windspeed": 20})


def test_map_location_is_rounded_and_null_clears_it():
    patch = PreferencesPatch.model_validate({
        "mapLocation": {"lat": 54.412345678, "lon": 10.198765432, "source": "gps"},
    })
    assert patch.to_patch() == {"mapLocation": {"lat": 54.4123, "lon": 10.1988, "source": "gps"}}

    assert PreferencesPatch.model_validate({"mapLocation": None}).to_patch() == {"mapLocation": None}
    assert PreferencesPatch.model_validate({"sports": ["surf"]}).to_patch() == {"sports": ["surf"]}


@pytest.mark.parametrize("location", [
    {"lat": 91, "lon": 10, "source": "gps"},
    {"lat": 54, "lon": 181, "source": "manual"},
    {"lat": 54, "lon": 10, "source": "ip"},
    {"lat": 54, "lon": 10, "source": "gps", "accuracy": 5},
])
def test_map_location_rejects_invalid_values(location):
    with pytest.raises(ValidationError):
        PreferencesPatch.model_validate({"mapLocation": location})
