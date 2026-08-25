from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.weather.physics.coast import coastal_class
from app.weather.physics.engine import apply_local_physics
from app.weather.physics.limits import clamp_combined_factor, clamp_direction_change


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


def test_unreviewed_advanced_sector_is_not_applied():
    sector = SimpleNamespace(enabled=True, start_deg=250, end_deg=290, speed_factor=1.3, direction_offset_deg=12, version=1)
    profile = SimpleNamespace(active=True, quality_tier="advanced", reviewed_at=None, coastal_normal_deg=270, sectors=[sector])
    result = apply_local_physics(10.0, 270.0, profile)
    assert result.speed_ms == 10.0
    assert result.direction_deg == 270.0


def test_reviewed_advanced_sector_stays_disabled():
    sector = SimpleNamespace(enabled=True, start_deg=250, end_deg=290, speed_factor=1.35, direction_offset_deg=15, version=1)
    profile = SimpleNamespace(active=True, quality_tier="advanced", reviewed_at=datetime.now(timezone.utc), coastal_normal_deg=270, sectors=[sector])
    result = apply_local_physics(10.0, 270.0, profile)
    assert result.speed_ms == pytest.approx(10.0)
    assert result.direction_deg == 270.0


def test_normal_and_advanced_limits_are_explicit():
    assert clamp_combined_factor(1.5, advanced=False) == 1.25
    assert clamp_combined_factor(0.5, advanced=True) == 0.60
    assert clamp_direction_change(14, advanced=False) == 10
    assert clamp_direction_change(14, advanced=True) == 14
