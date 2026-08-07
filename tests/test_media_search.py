"""Media proxy: caching, hourly budget, per-provider degradation, auth.

DB-gated — cache and budget live in Postgres, and the duplicate annotation reads
``media_usage``. Upstream calls are replaced by counting fakes; no network.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.config import get_settings
from app.media import budget as budget_store
from app.media import search as media_search
from app.media.providers import pexels, unsplash, wikimedia
from app.media.providers.base import ProviderError
from app.models import MediaProviderBudget, MediaSearchCache, MediaUsage
from tests.conftest import require_db

FIXTURES = Path(__file__).parent / "fixtures" / "media"


def fixture(name: str) -> list[dict]:
    return [json.loads((FIXTURES / name).read_text(encoding="utf-8"))]


class CountingSearch:
    """Stand-in for an adapter's ``search``: records calls, returns a fixture."""

    def __init__(self, payload, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.payload


@pytest.fixture(scope="module", autouse=True)
def _catalogue(_migrated_db):
    """The duplicate annotation and the picker context need a real spot with a
    region, so this module seeds the core catalogue like ``test_seed`` does
    rather than skipping when the database happens to be empty."""
    from app.db.session import SessionLocal
    from app.seed.seed import seed

    require_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


@pytest.fixture
def seeded_spot(db):
    from sqlalchemy import select

    from app.models import Spot

    spot = db.scalars(
        select(Spot).where(Spot.slug == "tarifa-los-lances")
    ).first()
    assert spot is not None, "core seed did not create the reference spot"
    return spot


@pytest.fixture(autouse=True)
def _clean_media_state(db):
    """Cache and budget are global state — reset around every test so counts
    are the test's own."""
    require_db()
    for model in (MediaSearchCache, MediaProviderBudget, MediaUsage):
        db.execute(delete(model))
    db.commit()
    yield
    for model in (MediaSearchCache, MediaProviderBudget, MediaUsage):
        db.execute(delete(model))
    db.commit()


@pytest.fixture
def with_keys(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "unsplash_access_key", "test-key")
    monkeypatch.setattr(settings, "pexels_api_key", "test-key")
    return settings


# --- caching ---------------------------------------------------------------

def test_repeating_a_search_costs_one_upstream_request(db, monkeypatch, with_keys):
    """The whole reason the cache exists: Unsplash's demo tier is 50/hour."""
    fake = CountingSearch(fixture("unsplash_search.json"))
    monkeypatch.setattr(unsplash.ADAPTER, "search", fake)

    first = media_search.search(db, provider="unsplash", query="Tarifa kitesurf")
    second = media_search.search(db, provider="unsplash", query="Tarifa kitesurf")

    assert fake.calls == 1
    assert first.cached is False and second.cached is True
    assert first.items and first.items == second.items


def test_query_spelling_variants_share_one_cache_entry(db, monkeypatch, with_keys):
    fake = CountingSearch(fixture("unsplash_search.json"))
    monkeypatch.setattr(unsplash.ADAPTER, "search", fake)

    media_search.search(db, provider="unsplash", query="Tarifa  Kitesurf")
    media_search.search(db, provider="unsplash", query="tarifa kitesurf")
    media_search.search(db, provider="unsplash", query="  TARIFA kitesurf ")

    assert fake.calls == 1


def test_switching_role_does_not_refetch(db, monkeypatch, with_keys):
    """Both eligibility flags ride on every result, and no adapter varies its
    upstream query by role — so a Hero/Galerie toggle must be free."""
    fake = CountingSearch(fixture("unsplash_search.json"))
    monkeypatch.setattr(unsplash.ADAPTER, "search", fake)

    hero = media_search.search(db, provider="unsplash", query="tarifa", role="hero")
    gallery = media_search.search(db, provider="unsplash", query="tarifa", role="gallery")

    assert fake.calls == 1
    assert hero.items == gallery.items


def test_a_cache_hit_costs_no_budget(db, monkeypatch, with_keys):
    fake = CountingSearch(fixture("unsplash_search.json"))
    monkeypatch.setattr(unsplash.ADAPTER, "search", fake)

    media_search.search(db, provider="unsplash", query="tarifa")
    after_first = budget_store.budget_used(db, "unsplash")
    media_search.search(db, provider="unsplash", query="tarifa")

    assert after_first == 1
    assert budget_store.budget_used(db, "unsplash") == 1


# --- budget ----------------------------------------------------------------

def test_budget_counts_upstream_requests(db, monkeypatch, with_keys):
    fake = CountingSearch(fixture("unsplash_search.json"))
    monkeypatch.setattr(unsplash.ADAPTER, "search", fake)

    for page in range(1, 4):
        media_search.search(db, provider="unsplash", query="tarifa", page=page)

    assert budget_store.budget_used(db, "unsplash") == 3


def test_budget_warning_appears_before_exhaustion(db, monkeypatch, with_keys):
    monkeypatch.setattr(
        get_settings(), "media_budget_per_hour", {"unsplash": 10}, raising=False
    )
    for _ in range(8):
        budget_store.budget_consume(db, "unsplash")

    state = budget_store.budget_state(db, "unsplash")
    assert state["warning"] is True and state["exhausted"] is False


def test_exhausted_budget_stops_the_request_before_it_is_made(
    db, monkeypatch, with_keys
):
    monkeypatch.setattr(
        get_settings(), "media_budget_per_hour", {"unsplash": 2}, raising=False
    )
    fake = CountingSearch(fixture("unsplash_search.json"))
    monkeypatch.setattr(unsplash.ADAPTER, "search", fake)

    media_search.search(db, provider="unsplash", query="one")
    media_search.search(db, provider="unsplash", query="two")
    blocked = media_search.search(db, provider="unsplash", query="three")

    assert fake.calls == 2  # the third never reached Unsplash
    assert blocked.status == media_search.STATUS_EXHAUSTED
    assert blocked.items == []


def test_exhausting_one_provider_leaves_the_others_working(db, monkeypatch, with_keys):
    """Budget exhaustion must isolate one tab, never the overlay."""
    monkeypatch.setattr(
        get_settings(),
        "media_budget_per_hour",
        {"unsplash": 1, "pexels": 50},
        raising=False,
    )
    monkeypatch.setattr(
        unsplash.ADAPTER, "search", CountingSearch(fixture("unsplash_search.json"))
    )
    monkeypatch.setattr(
        pexels.ADAPTER, "search", CountingSearch(fixture("pexels_search.json"))
    )

    media_search.search(db, provider="unsplash", query="a")
    exhausted = media_search.search(db, provider="unsplash", query="b")
    other = media_search.search(db, provider="pexels", query="b")

    assert exhausted.status == media_search.STATUS_EXHAUSTED
    assert other.status == media_search.STATUS_OK and other.items


# --- degradation -----------------------------------------------------------

def test_a_provider_outage_isolates_that_tab(db, monkeypatch, with_keys):
    monkeypatch.setattr(
        unsplash.ADAPTER,
        "search",
        CountingSearch(None, error=ProviderError("connection reset")),
    )
    monkeypatch.setattr(
        pexels.ADAPTER, "search", CountingSearch(fixture("pexels_search.json"))
    )

    down = media_search.search(db, provider="unsplash", query="tarifa")
    healthy = media_search.search(db, provider="pexels", query="tarifa")

    assert down.status == media_search.STATUS_ERROR
    assert "connection reset" in down.message
    assert healthy.status == media_search.STATUS_OK and healthy.items


def test_a_failed_request_is_not_cached(db, monkeypatch, with_keys):
    fake = CountingSearch(None, error=ProviderError("boom"))
    monkeypatch.setattr(unsplash.ADAPTER, "search", fake)

    media_search.search(db, provider="unsplash", query="tarifa")
    media_search.search(db, provider="unsplash", query="tarifa")

    assert fake.calls == 2  # retried, not served a cached failure


def test_a_missing_key_disables_only_that_provider(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "unsplash_access_key", None)
    monkeypatch.setattr(
        wikimedia.ADAPTER, "search", CountingSearch(fixture("wikimedia_search.json"))
    )

    disabled = media_search.search(db, provider="unsplash", query="tarifa")
    keyless = media_search.search(db, provider="wikimedia", query="tarifa")

    assert disabled.status == media_search.STATUS_DISABLED
    assert "UNSPLASH_ACCESS_KEY" in disabled.message
    assert keyless.status == media_search.STATUS_OK and keyless.items


# --- licensing + duplicates ------------------------------------------------

def test_unusable_licenses_never_reach_the_grid(db, monkeypatch):
    """Unlike a too-small photo, an NC-licensed one can never become usable —
    so it is dropped rather than greyed out."""
    monkeypatch.setattr(
        wikimedia.ADAPTER, "search", CountingSearch(fixture("wikimedia_search.json"))
    )
    outcome = media_search.search(db, provider="wikimedia", query="tarifa")
    ids = {item["external_id"] for item in outcome.items}
    assert "45219877" not in ids  # CC BY-NC
    assert "45219876" in ids      # CC BY-SA


def test_results_report_where_the_photo_is_already_used(
    db, monkeypatch, with_keys, seeded_spot
):
    spot = seeded_spot
    db.add(
        MediaUsage(
            provider="unsplash",
            external_id="Qw3w0hVjJ2M",
            entity_type="spot",
            entity_id=spot.id,
            role="hero",
        )
    )
    db.commit()

    monkeypatch.setattr(
        unsplash.ADAPTER, "search", CountingSearch(fixture("unsplash_search.json"))
    )
    outcome = media_search.search(db, provider="unsplash", query="tarifa")
    used = next(i for i in outcome.items if i["external_id"] == "Qw3w0hVjJ2M")
    fresh = next(i for i in outcome.items if i["external_id"] == "Kd8Lm2QpXyz")

    assert used["used_by"] == [
        {
            "entity_type": "spot",
            "entity_id": str(spot.id),
            "name": spot.name,
            "role": "hero",
        }
    ]
    assert fresh["used_by"] == []


# --- housekeeping ----------------------------------------------------------

def test_sweep_removes_expired_cache_entries(db, monkeypatch, with_keys):
    monkeypatch.setattr(
        unsplash.ADAPTER, "search", CountingSearch(fixture("unsplash_search.json"))
    )
    media_search.search(db, provider="unsplash", query="tarifa")
    db.execute(
        __import__("sqlalchemy").update(MediaSearchCache).values(
            expires_at=__import__("datetime").datetime(
                2020, 1, 1, tzinfo=__import__("datetime").timezone.utc
            )
        )
    )
    db.commit()

    removed = budget_store.sweep_expired(db)
    assert removed["cache_entries_removed"] >= 1


# --- HTTP surface ----------------------------------------------------------

def test_search_requires_authentication(anon_client):
    resp = anon_client.get("/admin/media/search", params={"q": "tarifa", "provider": "unsplash"})
    assert resp.status_code in (401, 403)
    # No provider detail leaks to an unauthenticated caller.
    assert "UNSPLASH" not in resp.text.upper()


def test_curators_may_search(client, monkeypatch, with_keys):
    monkeypatch.setattr(
        unsplash.ADAPTER, "search", CountingSearch(fixture("unsplash_search.json"))
    )
    resp = client.get(
        "/admin/media/search", params={"q": "tarifa", "provider": "unsplash"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["items"][0]["provider"] == "unsplash"
    assert "hero_eligible" in body["items"][0]


def test_unknown_provider_is_a_client_error(client):
    resp = client.get("/admin/media/search", params={"q": "x", "provider": "getty"})
    assert resp.status_code == 422


def test_nearby_without_coordinates_is_refused(client):
    resp = client.get("/admin/media/search", params={"provider": "nearby"})
    assert resp.status_code == 422


def test_provider_status_lists_budgets(client):
    resp = client.get("/admin/media/providers")
    assert resp.status_code == 200
    providers = {p["provider"]: p for p in resp.json()["providers"]}
    assert {"unsplash", "pexels", "wikimedia", "openverse"} <= set(providers)
    assert "used" in providers["unsplash"]["budget"]


def test_picker_context_supplies_chips_and_coordinates(client, seeded_spot):
    resp = client.get(f"/admin/media/context/spot/{seeded_spot.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == seeded_spot.name
    # The first chip is active on open, so it must be the most specific one —
    # the operator should not have to type anything.
    assert body["suggestions"][0] == seeded_spot.name
    assert body["lat"] is not None and body["lon"] is not None
    # Sport terms are English: stock libraries are indexed in English.
    assert any("kitesurfing" in chip for chip in body["suggestions"])


def test_region_context_suggests_landscape_not_sport_terms(client, db):
    from sqlalchemy import select

    from app.models import Region

    region = db.scalars(select(Region).where(Region.slug == "tarifa")).first()
    resp = client.get(f"/admin/media/context/region/{region.id}")
    assert resp.status_code == 200, resp.text
    chips = resp.json()["suggestions"]
    assert chips[0] == region.name
    assert any("coast" in chip for chip in chips)
    assert not any("kitesurfing" in chip for chip in chips)


def test_picker_context_404s_for_an_unknown_entity(client):
    resp = client.get(f"/admin/media/context/spot/{uuid.uuid4()}")
    assert resp.status_code == 404
