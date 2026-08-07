"""Canonical image object: construction, legacy upgrade, placeholder detection.

Pure functions — no database, so these run even without a test Postgres.
"""

from __future__ import annotations

import pytest

from app.admin.readiness import image_ready
from app.media.image_object import (
    CANONICAL_KEYS,
    CENTER_FOCAL,
    ImageObjectError,
    build_image,
    is_placeholder,
    normalize_focal,
    placeholder_image,
    upgrade_legacy,
    with_fields,
)

FULL_RIGHTS = {
    "url": "https://images.unsplash.com/photo-1",
    "source": "Unsplash",
    "license": "Unsplash License",
    "credit": "Jane Doe",
}


# --- build_image -----------------------------------------------------------

def test_build_image_fills_every_canonical_key():
    image = build_image(**FULL_RIGHTS)
    assert set(image) == set(CANONICAL_KEYS)


def test_build_image_defaults_are_conservative():
    image = build_image(**FULL_RIGHTS)
    assert image["provider"] == "unknown"
    assert image["delivery"] == "hosted"
    assert image["role"] == "hero"
    assert image["focal"] == CENTER_FOCAL
    assert image["geo_verified"] is False
    # Nothing is invented for the fields we have no value for.
    assert image["license_url"] is None
    assert image["external_id"] is None
    assert image["width"] is None


@pytest.mark.parametrize("missing", sorted(FULL_RIGHTS))
def test_build_image_requires_every_rights_field(missing):
    payload = {**FULL_RIGHTS, missing: "   "}
    with pytest.raises(ImageObjectError) as exc:
        build_image(**payload)
    assert missing in str(exc.value)


def test_build_image_rejects_unknown_enums():
    with pytest.raises(ImageObjectError):
        build_image(**FULL_RIGHTS, provider="getty")
    with pytest.raises(ImageObjectError):
        build_image(**FULL_RIGHTS, delivery="streamed")
    with pytest.raises(ImageObjectError):
        build_image(**FULL_RIGHTS, role="thumbnail")


def test_build_image_treats_none_enums_as_unspecified():
    """Callers pass ``{k: payload.get(k) for k in CANONICAL_KEYS}``, so an
    absent enum arrives as None rather than not at all."""
    image = build_image(**FULL_RIGHTS, provider=None, delivery=None, role=None)
    assert (image["provider"], image["delivery"], image["role"]) == (
        "unknown", "hosted", "hero",
    )


def test_source_health_defaults_to_unchecked():
    """None means "never checked" and must stay distinguishable from "alive" —
    the Sprint 6 "Quelle tot" filter depends on that difference."""
    image = build_image(**FULL_RIGHTS)
    assert image["source_status"] is None
    assert image["source_checked_at"] is None


def test_build_image_rejects_an_unknown_source_status():
    with pytest.raises(ImageObjectError):
        build_image(**FULL_RIGHTS, source_status="probably-fine")


def test_build_image_drops_nonsense_dimensions():
    image = build_image(**FULL_RIGHTS, width=0, height="tall")
    assert image["width"] is None and image["height"] is None


# --- focal points ----------------------------------------------------------

def test_normalize_focal_clamps_to_percent_range():
    assert normalize_focal(-10, 140) == {"x": 0.0, "y": 100.0}


def test_focal_accepts_the_repo_percent_dict():
    image = build_image(**FULL_RIGHTS, focal={"x": 30, "y": 70})
    assert image["focal"] == {"x": 30.0, "y": 70.0}


def test_focal_pair_in_zero_to_one_is_scaled_not_stored_raw():
    """A 0..1 pair would otherwise land as "0.5% 0.42%" — the top-left corner —
    and silently ruin the crop."""
    image = build_image(**FULL_RIGHTS, focal=[0.5, 0.42])
    assert image["focal"] == {"x": 50.0, "y": 42.0}


def test_missing_focal_is_dead_centre():
    assert build_image(**FULL_RIGHTS, focal=None)["focal"] == CENTER_FOCAL


# --- legacy upgrade --------------------------------------------------------

def test_upgrade_legacy_pads_a_four_field_object():
    upgraded = upgrade_legacy(
        {"url": "https://img/x.jpg", "source": "upload", "license": "own", "credit": "Jo"}
    )
    assert set(upgraded) == set(CANONICAL_KEYS)
    assert upgraded["provider"] == "unknown"
    assert upgraded["delivery"] == "hosted"
    assert upgraded["focal"] == CENTER_FOCAL


def test_upgrade_legacy_keeps_an_existing_focal_point():
    upgraded = upgrade_legacy({"url": "https://img/x.jpg", "focal": {"x": 12, "y": 88}})
    assert upgraded["focal"] == {"x": 12.0, "y": 88.0}


def test_upgrade_legacy_passes_through_none_and_junk():
    assert upgrade_legacy(None) is None
    assert upgrade_legacy("not-a-dict") is None


def test_upgrade_legacy_discards_an_unknown_provider_rather_than_trusting_it():
    upgraded = upgrade_legacy({"url": "https://img/x.jpg", "provider": "getty"})
    assert upgraded["provider"] == "unknown"


# --- with_fields (attribution / focal editors) ------------------------------

def test_with_fields_preserves_provenance_while_editing_attribution():
    original = build_image(
        **FULL_RIGHTS,
        provider="unsplash",
        external_id="abc123",
        delivery="hotlinked",
        focal={"x": 40, "y": 60},
    )
    edited = with_fields(original, credit="Bob", license="CC0", source="own")
    assert edited["credit"] == "Bob"
    assert edited["provider"] == "unsplash"
    assert edited["external_id"] == "abc123"
    assert edited["delivery"] == "hotlinked"
    assert edited["focal"] == {"x": 40.0, "y": 60.0}


def test_with_fields_refuses_to_empty_a_credit():
    original = build_image(**FULL_RIGHTS)
    with pytest.raises(ImageObjectError):
        with_fields(original, credit="   ")


def test_with_fields_needs_an_existing_image():
    with pytest.raises(ImageObjectError):
        with_fields(None, credit="Bob")


# --- placeholders ----------------------------------------------------------

def test_placeholder_image_is_recognised_as_one():
    image = placeholder_image("tarifa-los-lances", kind="spot")
    assert is_placeholder(image)
    assert image["provider"] == "seed"


def test_a_real_photo_is_not_a_placeholder():
    assert not is_placeholder(build_image(**FULL_RIGHTS, provider="unsplash"))


def test_any_dot_local_host_counts_as_a_placeholder():
    assert is_placeholder({"url": "https://placeholder.local/x.jpg"})
    assert not is_placeholder({"url": "https://placeholder.localhost.example/x.jpg"})


def test_readiness_rejects_a_placeholder_despite_complete_rights_fields():
    """The seed writes complete-looking rights fields, so the four-field check
    alone would report unstarted work as done."""
    placeholder = placeholder_image("laboe", kind="spot")
    assert all(placeholder[k] for k in ("url", "source", "license", "credit"))
    assert not image_ready(placeholder)
    assert image_ready(build_image(**FULL_RIGHTS, provider="unsplash"))
