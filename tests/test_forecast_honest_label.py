"""WP4: honest quality_level derivation and correction-confidence propagation."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.weather.contracts import ModelFamily
from app.weather.physics import correction_summary


def _sector(speed_factor=1.0, *, enabled=True, offset=0.0, note=None):
    return SimpleNamespace(enabled=enabled, start_deg=0, end_deg=30,
                           speed_factor=speed_factor, direction_offset_deg=offset, note=note)


def _profile(sectors, *, active=True):
    return SimpleNamespace(active=active, sectors=sectors)


def test_no_profile_or_inactive_is_baseline():
    assert correction_summary(None) == {"applied": False, "confidence": "ok"}
    assert correction_summary(_profile([_sector(1.3)], active=False))["applied"] is False


def test_neutral_or_disabled_sectors_are_baseline():
    assert correction_summary(_profile([]))["applied"] is False
    assert correction_summary(_profile([_sector(1.0)]))["applied"] is False           # neutral factor
    assert correction_summary(_profile([_sector(1.3, enabled=False)]))["applied"] is False


def test_nonneutral_enabled_sector_is_corrected():
    assert correction_summary(_profile([_sector(1.0), _sector(1.25)]))["applied"] is True
    assert correction_summary(_profile([_sector(1.0, offset=5.0)]))["applied"] is True  # offset-only


def test_low_confidence_sector_propagates_confidence():
    low = _sector(1.3, note=json.dumps({"confidence": "low"}))
    summary = correction_summary(_profile([low]))
    assert summary == {"applied": True, "confidence": "low"}
    ok = _sector(1.3, note=json.dumps({"confidence": "ok"}))
    assert correction_summary(_profile([ok]))["confidence"] == "ok"


def test_zero_blend_for_every_family_neutralises_the_label():
    overrides = {family.value: 0.0 for family in ModelFamily}
    assert correction_summary(_profile([_sector(1.4)]), overrides)["applied"] is False
    # a single non-zero family restores "corrected"
    overrides[ModelFamily.REGIONAL.value] = 1.0
    assert correction_summary(_profile([_sector(1.4)]), overrides)["applied"] is True
