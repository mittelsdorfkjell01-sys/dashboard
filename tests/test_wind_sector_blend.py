"""WP3 Task 4: per-model-family blend coefficient for GWA sector factors."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.weather.contracts import ModelFamily
from app.weather.physics.blend import blended_factor, family_blend
from app.weather.physics.engine import apply_local_physics


def test_family_blend_defaults_to_full_factor():
    assert family_blend(ModelFamily.REGIONAL) == 1.0
    assert family_blend(ModelFamily.IFS, {}) == 1.0


def test_family_blend_reads_and_clamps_overrides():
    overrides = {"regional": 0.4, "ifs": 5.0, "gfs": -1.0, "aifs": "bad"}
    assert family_blend(ModelFamily.REGIONAL, overrides) == 0.4
    assert family_blend(ModelFamily.IFS, overrides) == 1.0   # clamped to [0,1]
    assert family_blend(ModelFamily.GFS, overrides) == 0.0
    assert family_blend(ModelFamily.AIFS, overrides) == 1.0  # non-numeric -> default


def test_blended_factor_endpoints_and_midpoint():
    assert blended_factor(1.4, 1.0) == pytest.approx(1.4)   # full
    assert blended_factor(1.4, 0.0) == pytest.approx(1.0)   # neutralised
    assert blended_factor(1.4, 0.5) == pytest.approx(1.2)   # halfway


def _reviewed_profile(speed_factor=1.4):
    sector = SimpleNamespace(enabled=True, start_deg=250, end_deg=290, speed_factor=speed_factor,
                             direction_offset_deg=0, version=1, note="gwa")
    return SimpleNamespace(active=True, quality_tier="advanced", reviewed_at=datetime.now(timezone.utc),
                           coastal_normal_deg=270, sectors=[sector])


def test_engine_blend_full_reproduces_factor():
    result = apply_local_physics(10.0, 270.0, _reviewed_profile(1.4), blend=1.0)
    assert result.speed_ms == pytest.approx(14.0)
    assert result.applied_component["blend"] == 1.0
    assert result.applied_component["raw_factor"] == pytest.approx(1.4)


def test_engine_blend_zero_neutralises_factor():
    result = apply_local_physics(10.0, 270.0, _reviewed_profile(1.4), blend=0.0)
    assert result.speed_ms == pytest.approx(10.0)
    assert result.corrected is False  # nothing applied


def test_engine_blend_half_applies_half_the_excess():
    result = apply_local_physics(10.0, 270.0, _reviewed_profile(1.4), blend=0.5)
    assert result.speed_ms == pytest.approx(12.0)
    assert result.corrected is True


def test_engine_default_blend_is_full_factor():
    # Default arg (no blend passed) must not change existing behaviour.
    result = apply_local_physics(10.0, 270.0, _reviewed_profile(1.3))
    assert result.speed_ms == pytest.approx(13.0)
