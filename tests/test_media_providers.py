"""Provider normalisation against frozen upstream responses.

The fixtures in ``tests/fixtures/media`` are shaped like the real API answers,
including the awkward parts: a photo below the hero gate, a portrait, an
NC-licensed Commons file, a file with no machine-readable license and an
HTML-wrapped author field. Pure parsing — no network, no database.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.media.normalize import (
    GALLERY_MIN_LONG_EDGE,
    HERO_MIN_HEIGHT,
    HERO_MIN_WIDTH,
    adoptable,
    gallery_eligible,
    hero_eligible,
)
from app.media.providers import openverse, pexels, unsplash, wikimedia

FIXTURES = Path(__file__).parent / "fixtures" / "media"


def load(name: str) -> list[dict]:
    return [json.loads((FIXTURES / name).read_text(encoding="utf-8"))]


def by_id(results, external_id):
    return next(r for r in results if r.external_id == external_id)


# --- size gates ------------------------------------------------------------

@pytest.mark.parametrize(
    "width,height,expected",
    [
        (HERO_MIN_WIDTH, HERO_MIN_HEIGHT, True),
        (HERO_MIN_WIDTH - 1, HERO_MIN_HEIGHT, False),
        (HERO_MIN_WIDTH, HERO_MIN_HEIGHT - 1, False),
        (6000, 4000, True),
        (None, 4000, False),
        (0, 0, False),
    ],
)
def test_hero_gate_boundaries(width, height, expected):
    assert hero_eligible(width, height) is expected


def test_a_small_portrait_fails_on_width():
    """Typical portraits are rejected — but by the width rule, not by
    orientation: 2000 px is simply too narrow for a 3840 px-wide crop."""
    assert hero_eligible(2000, 4000) is False


def test_a_large_portrait_passes_and_that_is_correct():
    """A 4000×6000 portrait yields a 3840×1920 crop without upscaling, so the
    gate lets it through.

    Worth stating explicitly because the spec claims "portrait drops out
    automatically" — that holds for ordinary portraits (previous test) but not
    for very large ones. The rule as written is right; only that aside is
    imprecise. Adding an orientation rule on top would reject usable photos.
    """
    assert hero_eligible(4000, 6000) is True


@pytest.mark.parametrize(
    "width,height,expected",
    [
        (GALLERY_MIN_LONG_EDGE, 900, True),
        (GALLERY_MIN_LONG_EDGE - 1, 1200, False),
        (900, GALLERY_MIN_LONG_EDGE, True),
    ],
)
def test_gallery_gate_uses_the_long_edge(width, height, expected):
    assert gallery_eligible(width, height) is expected


# --- Unsplash --------------------------------------------------------------

def test_unsplash_normalises_a_result():
    results = unsplash.ADAPTER.parse(load("unsplash_search.json"))
    hero = by_id(results, "Qw3w0hVjJ2M")
    assert hero.provider == "unsplash"
    assert hero.width == 6000 and hero.height == 4000
    assert hero.credit.name == "Sam Rivera"
    assert hero.license.commercial and hero.license.modification
    assert hero.delivery == "hotlinked"


def test_unsplash_attribution_links_carry_utm():
    """An API condition, not decoration."""
    hero = by_id(unsplash.ADAPTER.parse(load("unsplash_search.json")), "Qw3w0hVjJ2M")
    assert "utm_source=surfwinddata" in hero.credit.url
    assert "utm_medium=referral" in hero.credit.url
    assert "utm_source=surfwinddata" in hero.source_page


def test_unsplash_keeps_the_download_location_for_adopt():
    """Pinging it on adopt is an API condition; losing it here would cost
    production access later."""
    hero = by_id(unsplash.ADAPTER.parse(load("unsplash_search.json")), "Qw3w0hVjJ2M")
    assert hero.unsplash_download_location.startswith("https://api.unsplash.com/")


def test_unsplash_preview_is_a_sized_cdn_url():
    hero = by_id(unsplash.ADAPTER.parse(load("unsplash_search.json")), "Qw3w0hVjJ2M")
    assert "w=1600" in hero.preview_url


def test_unsplash_small_photo_is_marked_not_dropped():
    """The Wikimedia tab would look empty if we filtered — small photos are
    still usable in the gallery."""
    small = by_id(unsplash.ADAPTER.parse(load("unsplash_search.json")), "Kd8Lm2QpXyz")
    payload = small.as_payload()
    assert payload["hero_eligible"] is False
    assert payload["gallery_eligible"] is True


def test_unsplash_falls_back_to_the_username_when_the_name_is_null():
    small = by_id(unsplash.ADAPTER.parse(load("unsplash_search.json")), "Kd8Lm2QpXyz")
    assert small.credit.name == "anon_shooter"


# --- Pexels ----------------------------------------------------------------

def test_pexels_normalises_a_result():
    results = pexels.ADAPTER.parse(load("pexels_search.json"))
    hero = by_id(results, "3560168")
    assert hero.width == 5472 and hero.height == 3648
    assert hero.credit.name == "Marta Kowalska"
    assert hero.credit.url.endswith("marta-kowalska")
    assert hero.full_url.endswith("pexels-photo-3560168.jpeg")
    assert hero.delivery == "hosted"
    assert hero.as_payload()["hero_eligible"] is True


def test_pexels_below_hero_gate_is_gallery_only():
    small = by_id(pexels.ADAPTER.parse(load("pexels_search.json")), "1174732")
    payload = small.as_payload()
    assert (payload["hero_eligible"], payload["gallery_eligible"]) == (False, True)


# --- Wikimedia Commons -----------------------------------------------------

def test_wikimedia_normalises_a_cc_by_sa_file():
    results = wikimedia.ADAPTER.parse(load("wikimedia_search.json"))
    photo = by_id(results, "45219876")
    assert photo.license.name == "CC BY-SA 4.0"
    assert photo.license.commercial and photo.license.modification
    assert photo.source_page.startswith("https://commons.wikimedia.org/")


def test_wikimedia_strips_html_from_the_author_field_server_side():
    """Commons author fields are free-form HTML; no markup may reach the UI."""
    photo = by_id(wikimedia.ADAPTER.parse(load("wikimedia_search.json")), "45219876")
    assert photo.credit.name == "Ana Ruiz"  # tags gone, whitespace collapsed
    assert "<" not in photo.credit.name


def test_wikimedia_marks_noncommercial_licenses_as_not_adoptable():
    photo = by_id(wikimedia.ADAPTER.parse(load("wikimedia_search.json")), "45219877")
    assert photo.license.name == "CC BY-NC 3.0"
    assert not adoptable(photo)


def test_wikimedia_drops_files_without_a_machine_readable_license():
    """Nothing to attribute means nothing usable, whatever the size."""
    ids = {r.external_id for r in wikimedia.ADAPTER.parse(load("wikimedia_search.json"))}
    assert "45219878" not in ids


def test_wikimedia_cc0_just_misses_the_hero_gate():
    """4000×1900: wide enough, 20 px too short. Adoptable by license, gallery
    only by size — exactly the case that must stay visible-but-greyed rather
    than silently disappear."""
    photo = by_id(wikimedia.ADAPTER.parse(load("wikimedia_search.json")), "45219879")
    assert adoptable(photo)
    payload = photo.as_payload()
    assert (payload["hero_eligible"], payload["gallery_eligible"]) == (False, True)


def test_wikimedia_geo_flag_is_only_set_for_coordinate_search():
    raw = load("wikimedia_search.json")
    assert all(not r.geo_verified for r in wikimedia.ADAPTER.parse(raw))
    assert all(r.geo_verified for r in wikimedia.ADAPTER.parse(raw, geo_verified=True))


# --- Openverse -------------------------------------------------------------

def test_openverse_normalises_a_result():
    results = openverse.ADAPTER.parse(load("openverse_search.json"))
    photo = by_id(results, "5f7c1b6a-0f2e-4c8a-9d1b-2a3c4d5e6f70")
    assert photo.license.name == "CC BY 2.0"
    assert photo.credit.name == "Kai Weber"
    assert photo.width == 4288 and photo.height == 2848
    assert photo.source_page.startswith("https://www.flickr.com/")


def test_openverse_falls_back_to_the_source_when_the_creator_is_null():
    photo = by_id(
        openverse.ADAPTER.parse(load("openverse_search.json")),
        "9a8b7c6d-5e4f-3a2b-1c0d-9e8f7a6b5c40",
    )
    assert photo.credit.name == "flickr"


def test_openverse_license_filter_is_not_a_parameter():
    """Hard-coded on purpose: nothing that forbids commercial use or
    modification may enter the picker from here."""
    from app.media.providers.base import ProviderRequest

    params = openverse.ADAPTER._params(ProviderRequest(query="tarifa"))
    assert params["license_type"] == "commercial,modification"


# --- availability ----------------------------------------------------------

def test_keyless_providers_stay_enabled(monkeypatch):
    """Wikimedia needs no key; Openverse works anonymously, so disabling it for
    a missing optional credential would cost function for nothing."""
    assert wikimedia.ADAPTER.available() is True
    assert openverse.ADAPTER.available() is True


def test_keyed_providers_report_unavailable_without_credentials(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "unsplash_access_key", None)
    monkeypatch.setattr(settings, "pexels_api_key", None)
    assert unsplash.ADAPTER.available() is False
    assert pexels.ADAPTER.available() is False
