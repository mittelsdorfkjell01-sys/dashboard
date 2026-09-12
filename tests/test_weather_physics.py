from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.weather.physics.coast import coastal_class
from app.weather.physics.engine import apply_local_physics
from app.weather.physics.limits import clamp_combined_factor, clamp_direction_change
from app.weather.physics.manual import select_sector


def test_coastal_classification_uses_waterward_normal_and_wraps_north():
    assert coastal_class(350, 10) == "onshore"
    assert coastal_class(190, 10) == "offshore"
    assert coastal_class(100, 10) == "sideshore"


@pytest.mark.parametrize(("direction", "expected"), [
    (0, "onshore"), (22.5, "onshore"), (22.6, "cross_onshore"),
    (67.5, "cross_onshore"), (67.6, "sideshore"), (112.4, "sideshore"),
    (112.5, "cross_offshore"), (157.4, "cross_offshore"),
    (157.5, "offshore"), (180, "offshore"), (359.9, "onshore"),
])
def test_coastal_classification_boundaries(direction, expected):
    assert coastal_class(direction, 0) == expected


def test_coastal_classification_requires_both_bearings():
    assert coastal_class(None, 0) == "unavailable"
    assert coastal_class(0, None) == "unavailable"


def test_missing_profile_does_not_invent_local_correction():
    result = apply_local_physics(10.0, 270.0, None)
    assert result.speed_ms == 10.0
    assert result.quality_tier == "coordinates"


def test_enabled_sector_applies_without_a_review_gate():
    # Application is gated only by the sector being enabled (no reviewed_at gate).
    sector = SimpleNamespace(enabled=True, start_deg=250, end_deg=290, speed_factor=1.3,
                             direction_offset_deg=0, version=1, note="gwa")
    profile = SimpleNamespace(active=True, quality_tier="advanced", reviewed_at=None,
                              coastal_normal_deg=270, sectors=[sector])
    result = apply_local_physics(10.0, 270.0, profile)
    assert result.speed_ms == pytest.approx(13.0)
    assert result.corrected is True


def test_inactive_profile_applies_nothing():
    sector = SimpleNamespace(enabled=True, start_deg=250, end_deg=290, speed_factor=1.3,
                             direction_offset_deg=0, version=1, note="gwa")
    profile = SimpleNamespace(active=False, quality_tier="advanced", reviewed_at=None,
                              coastal_normal_deg=270, sectors=[sector])
    result = apply_local_physics(10.0, 270.0, profile)
    assert result.speed_ms == 10.0
    assert result.corrected is False


def test_reviewed_sector_scales_magnitude_in_uv_space():
    # Phase 1: magnitude only (offset 0). A reviewed, enabled sector applies.
    sector = SimpleNamespace(enabled=True, start_deg=250, end_deg=290, speed_factor=1.3,
                             direction_offset_deg=0, version=1, note="gwa")
    profile = SimpleNamespace(active=True, quality_tier="advanced", reviewed_at=datetime.now(timezone.utc),
                              coastal_normal_deg=270, sectors=[sector])
    result = apply_local_physics(10.0, 270.0, profile)
    assert result.speed_ms == pytest.approx(13.0)
    assert result.direction_deg == pytest.approx(270.0)
    assert result.corrected is True
    assert result.applied_component["component"] == "gwa_sector"
    # The caller derives the gust factor from the same ratio.
    assert result.speed_ms / 10.0 == pytest.approx(1.3)


def test_disabled_sector_is_not_applied():
    sector = SimpleNamespace(enabled=False, start_deg=250, end_deg=290, speed_factor=1.3,
                             direction_offset_deg=0, version=1, note=None)
    profile = SimpleNamespace(active=True, quality_tier="advanced", reviewed_at=datetime.now(timezone.utc),
                              coastal_normal_deg=270, sectors=[sector])
    result = apply_local_physics(10.0, 270.0, profile)
    assert result.speed_ms == pytest.approx(10.0)
    assert result.corrected is False
    assert result.applied_component is None


def test_adjacent_sector_boundary_belongs_only_to_the_sector_that_starts_there():
    left = SimpleNamespace(enabled=True, start_deg=0, end_deg=30, version=9)
    right = SimpleNamespace(enabled=True, start_deg=30, end_deg=60, version=1)

    assert select_sector(30, [left, right]) is right


def test_saturated_factor_is_clamped_and_flagged():
    sector = SimpleNamespace(enabled=True, start_deg=250, end_deg=290, speed_factor=1.75,
                             direction_offset_deg=0, version=1, note="gwa")
    profile = SimpleNamespace(active=True, quality_tier="advanced", reviewed_at=datetime.now(timezone.utc),
                              coastal_normal_deg=270, sectors=[sector])
    result = apply_local_physics(10.0, 270.0, profile)
    assert result.speed_ms == pytest.approx(16.0)  # clamped to the 1.60 advanced hull
    assert result.correction_limited is True
    assert result.applied_component["saturated"] is True


def test_normal_and_advanced_limits_are_explicit():
    assert clamp_combined_factor(1.5, advanced=False) == 1.25
    assert clamp_combined_factor(0.5, advanced=True) == 0.50
    assert clamp_combined_factor(1.7, advanced=True) == 1.60
    assert clamp_direction_change(14, advanced=False) == 10
    assert clamp_direction_change(14, advanced=True) == 14
