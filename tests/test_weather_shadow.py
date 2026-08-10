from types import SimpleNamespace

from app.weather.shadow import physics_shadow


def test_ocean_spot_prefers_sea_grid_but_never_activates_correction():
    spot = SimpleNamespace(water_type=["ocean"], weather_profile=None)
    result = physics_shadow(spot, None)
    assert result["grid_preference"] == "sea"
    assert result["active_correction"] is False
    assert result["metadata_quality"] == "coordinates"


def test_partial_profile_reports_exact_missing_inputs():
    raw = SimpleNamespace(coastal_normal_deg=270, elevation_m=3, roughness_length_m=None,
                          land_reference={"latitude": 1}, water_reference=None)
    spot = SimpleNamespace(water_type=["sea"], weather_profile=raw)
    result = physics_shadow(spot, SimpleNamespace())
    assert result["metadata_quality"] == "partial"
    assert result["missing"] == ["roughness_length_m", "water_reference"]
