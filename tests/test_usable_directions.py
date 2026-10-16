from types import SimpleNamespace

from app.recommendations.service import _direction_windows
from app.weather.usable_directions import (
    AUTOMATIC_RULE_VERSION,
    classify_legacy_v3_sectors,
    derive_usable_directions,
    sectors_for_waterward_normals,
    usable_direction_state,
)


def _geometry(*, normal=90.0, conflicts=None):
    return {
        "geometry_version": "shore-v1",
        "start_areas": [
            {
                "name": "Hauptstart",
                "start_area": {
                    "type": "Polygon",
                    "coordinates": [[[-0.001, 0], [0, 0], [0, 0.001], [-0.001, 0.001], [-0.001, 0]]],
                },
                "usable_water": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0.002, 0], [0.002, 0.001], [0, 0.001], [0, 0]]],
                },
                "shoreline": {
                    "type": "LineString",
                    "coordinates": [[0, 0], [0, 0.001]],
                },
                "waterward_normal_deg": normal,
                "source": {"label": "Vermessung", "url": "https://example.test/shore-v1"},
            }
        ],
        "exclusions": [],
        "conflicts": conflicts or [],
    }


def test_onshore_sideshore_rule_includes_boundaries_and_north_wrap():
    assert sectors_for_waterward_normals([0]) == [0, 1, 2, 3, 4, 12, 13, 14, 15]
    assert 4 in sectors_for_waterward_normals([0])
    assert 12 in sectors_for_waterward_normals([0])


def test_multiple_launches_are_unioned_and_local_exclusions_apply():
    assert sectors_for_waterward_normals([0, 180], excluded={4}) == [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]


def test_complete_geometry_activates_without_profile_review():
    result = derive_usable_directions(_geometry())
    assert result.status == "active"
    assert result.missing == []
    assert result.sectors == list(range(9))
    assert result.evidence["origin"] == "automatic_geometry"


def test_conflict_or_insufficient_geometry_fails_closed():
    conflicted = derive_usable_directions(_geometry(conflicts=["Sperrzone unklar"]))
    assert conflicted.status == "blocked"
    assert conflicted.sectors == []
    assert "unresolved_local_conflicts" in conflicted.missing
    missing = derive_usable_directions({"geometry_version": "v1"})
    assert missing.status == "blocked"
    assert "start_areas" in missing.missing


def test_rule_change_makes_automatic_result_ineffective():
    profile = SimpleNamespace(
        active=True,
        usable_direction_status="active",
        usable_direction_rule_version="old-rule",
        usable_direction_sectors=[0],
        usable_direction_windows=[{"start_deg": 0, "end_deg": 22.5}],
        usable_direction_evidence={"origin": "automatic_geometry", "missing": []},
        usable_direction_geometry=None,
        usable_direction_geometry_version="v1",
        usable_direction_calculated_at=None,
    )
    state = usable_direction_state(profile)
    assert state["status"] == "stale_rule"
    assert state["effective"] is False
    assert state["windows"] == []
    assert "direction_rule_changed" in state["missing"]


def test_legacy_migration_only_accepts_neutral_canonical_rows():
    canonical = {"id": "1", "enabled": True, "start_deg": 337.5, "end_deg": 0,
                 "speed_factor": 1, "direction_offset_deg": 0, "version": 1}
    correction = {**canonical, "id": "2", "speed_factor": 1.1}
    assert classify_legacy_v3_sectors([canonical])["status"] == "active"
    ambiguous = classify_legacy_v3_sectors([canonical, correction])
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["sectors"] == []
    assert classify_legacy_v3_sectors([{**canonical, "enabled": False}])["status"] == "missing"


def test_recommendations_ignore_forecast_correction_sectors():
    profile = SimpleNamespace(
        active=True,
        reviewed_at=None,
        sectors=[SimpleNamespace(enabled=True, start_deg=180, end_deg=270, speed_factor=1.2)],
        usable_direction_status="active",
        usable_direction_rule_version=AUTOMATIC_RULE_VERSION,
        usable_direction_sectors=[0],
        usable_direction_windows=[{"start_deg": 0, "end_deg": 22.5}],
        usable_direction_evidence={"origin": "automatic_geometry", "missing": []},
        usable_direction_geometry=None,
        usable_direction_geometry_version="v1",
        usable_direction_calculated_at=None,
    )
    assert _direction_windows(SimpleNamespace(weather_profile=profile)) == [
        {"min": 0.0, "max": 22.5}
    ]
    profile.usable_direction_windows = []
    assert _direction_windows(SimpleNamespace(weather_profile=profile)) == []
