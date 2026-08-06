"""Unit tests for the read-overlay helper. No database required."""

from types import SimpleNamespace

from app.services.overrides import apply_overrides


def _spot(**kwargs):
    base = dict(
        name="Los Lances",
        water_type="sea",
        bottom_type=["sand"],
        level="beginner",
        facing=225,
        sports=["kitesurf"],
        model_pref="icon",
        confidence=None,
        editorial=None,
        climatology=None,
        image=None,
        overrides=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_no_overrides_returns_auto_values():
    eff = apply_overrides(_spot())
    assert eff["level"] == "beginner"
    assert eff["_overridden"] == []


def test_override_replaces_value_and_is_recorded():
    eff = apply_overrides(_spot(overrides={"level": "advanced", "facing": 90}))
    assert eff["level"] == "advanced"
    assert eff["facing"] == 90
    assert eff["_overridden"] == ["facing", "level"]


def test_unknown_override_keys_are_ignored():
    eff = apply_overrides(_spot(overrides={"status": "archived", "level": "expert"}))
    assert "status" not in eff  # status is not overridable
    assert eff["level"] == "expert"
    assert eff["_overridden"] == ["level"]
