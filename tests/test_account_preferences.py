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
