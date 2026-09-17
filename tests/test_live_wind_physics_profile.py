from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.weather.live_wind_physics_profile import (
    ablate_physics_profile,
    build_offline_live_wind_physics_profile,
    live_wind_physics_profile_doctor,
    validate_correction_ledger,
)
from app.weather.physics.engine import apply_local_physics
from app.weather.profiles import ResolvedWeatherProfile

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)


def inputs(*, missing_worldcover=False):
    sources = {
        "glo30_dem": {"status": "available", "dataset_version": "2024_1", "resolution_m": 30},
        "glo30_wbm": {"status": "available", "dataset_version": "2024_1", "resolution_m": 30},
        "worldcover": {"status": "available", "dataset_version": "2021-v200", "resolution_m": 10},
        "gwa_10m": {"status": "available", "dataset_version": "3.0", "resolution_m": 250},
    }
    if missing_worldcover:
        sources.pop("worldcover")
    sector = {
        "components": {
            "gwa_era5_factor": {
                "status": "available", "factor": 1.10, "direction_offset_deg": 0,
            },
            "roughness": {
                "status": "available", "factor": 0.95, "direction_offset_deg": 2,
            },
            "orography": {
                "status": "available", "factor": 1.05, "direction_offset_deg": -1,
            },
        }
    }
    return {
        "sources": sources,
        "terrain": {
            "spot_elevation_m": 12,
            "surrounding_elevation_m": {"mean": 28, "p95": 110},
            "slope_deg": 7,
            "aspect_deg": 260,
            "upwind_profiles": {"W": [10, 15, 30]},
            "ridge_lee": {"W": "lee"},
            "valley_axis": 275,
            "pass_nozzle": {"axis_deg": 280, "opening_ratio": 0.6},
        },
        "surface": {
            "coast_orientation_deg": 180,
            "land_water_transition": {"W": "water_to_land"},
            "fetch_by_sector_m": {"W": 50000},
            "estuary_opening": {"axis_deg": 270, "width_m": 900},
            "roughness_by_sector_m": {"W": 0.03},
            "forest_fraction": 0.12,
            "built_fraction": 0.08,
        },
        "sector_responses": [sector for _ in range(16)],
    }


def test_offline_profile_is_versioned_directional_and_never_auto_activated():
    profile = build_offline_live_wind_physics_profile(inputs(), generated_at=NOW)

    assert profile["status"] == "candidate"
    assert profile["serving_eligible"] is False
    assert profile["activation"]["status"] == "not_reviewed"
    assert len(profile["sectors"]) == 16
    assert profile["sectors"][0]["candidate_factor"] == pytest.approx(1.10 * 0.95 * 1.05)
    assert profile["terrain"]["valley_axis"]["status"] == "available"
    assert profile["surface"]["forest_fraction"]["status"] == "available"
    assert live_wind_physics_profile_doctor(profile)["ok"] is True


def test_missing_raster_is_explicit_and_does_not_become_neutral_landscape():
    profile = build_offline_live_wind_physics_profile(
        inputs(missing_worldcover=True), generated_at=NOW
    )

    assert profile["sources"]["worldcover"]["status"] == "unavailable"
    assert profile["status"] == "unavailable"
    assert profile["serving_eligible"] is False


def test_ablation_recomputes_each_sector_without_mutating_the_candidate():
    profile = build_offline_live_wind_physics_profile(inputs(), generated_at=NOW)
    ablated = ablate_physics_profile(profile, {"orography"})

    assert profile["sectors"][0]["candidate_factor"] != ablated["sectors"][0]["candidate_factor"]
    assert "orography" in profile["sectors"][0]["components"]
    assert "orography" not in ablated["sectors"][0]["components"]
    assert ablated["serving_eligible"] is False


def test_double_correction_ledger_rejects_overlapping_long_term_layers():
    result = validate_correction_ledger(
        ["model_calibration", "gwa_era5_factor", "roughness"]
    )
    assert result.ok is False
    assert "overlapping_long_term_speed_correction" in result.reasons

    sector = SimpleNamespace(
        start_deg=0,
        end_deg=360,
        speed_factor=1.2,
        direction_offset_deg=0,
        enabled=True,
        version=1,
        note='{"correction_ledger":{"ordered_components":["model_calibration","gwa_era5_factor"]}}',
    )
    applied = apply_local_physics(
        10.0,
        270.0,
        ResolvedWeatherProfile(quality_tier="advanced", sectors=(sector,)),
    )
    assert applied.corrected is False
    assert applied.applied_component["status"] == "unavailable"
    assert applied.applied_component["reason"].startswith("double_correction_guard")
