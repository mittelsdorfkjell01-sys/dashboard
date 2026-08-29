"""Sprint C community tests: ratings + aggregate, tips, submissions, image
upload gates, reports, rate-limit + honeypot. DB-gated.

Community endpoints are public; the target spot is created via the admin client.
The rate limiter is overridden to a no-op for most tests (Redis state would leak
across the 1h window otherwise) and to an in-memory one for the limiter test.
"""

from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.admin.deps import get_cds_client
from app.community.aggregate import bayesian_score
from app.community.ratelimit import (
    InMemoryRateLimiter,
    NoLimitRateLimiter,
    get_rate_limiter,
)
from app.config import get_settings
from app.main import app
from app.models import LocalTip, Spot, SpotSubmission
from app.seed.seed import seed
from tests.era5_helpers import FakeCdsClient, make_synthetic_series


def _img_bytes(w: int, h: int, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 80, 140)).save(buf, fmt)
    return buf.getvalue()


@pytest.fixture(scope="module", autouse=True)
def _seeded(_migrated_db):
    from app.db.session import SessionLocal
    from tests.conftest import require_db

    require_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    """Fake ERA5 client, tmp media dir, and a no-op rate limiter by default."""
    app.dependency_overrides[get_cds_client] = lambda: FakeCdsClient(
        make_synthetic_series()
    )
    app.dependency_overrides[get_rate_limiter] = lambda: NoLimitRateLimiter()
    monkeypatch.setattr(get_settings(), "media_dir", str(tmp_path))
    yield
    app.dependency_overrides.pop(get_cds_client, None)
    app.dependency_overrides.pop(get_rate_limiter, None)


@pytest.fixture(autouse=True)
def _cleanup(db):
    """Spots first, before their region — see the identical teardown in
    test_admin_moderation for the reasoning."""
    from sqlalchemy import delete

    yield
    from app.models import Region, Spot

    regions = db.scalars(
        select(Region).where(Region.slug.like("comm-region-%"))
    ).all()
    if not regions:
        return
    ids = [region.id for region in regions]
    db.execute(delete(Spot).where(Spot.region_id.in_(ids)))
    db.execute(delete(Region).where(Region.id.in_(ids)))
    db.commit()


@pytest.fixture
def spot_id(client):
    suffix = uuid.uuid4().hex[:8]
    r = client.post("/admin/regions", json={
        "name": f"Comm Region {suffix}", "slug": f"comm-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    })
    rid = r.json()["id"]
    s = client.post("/admin/spots", json={
        "name": f"Comm Spot {suffix}", "slug": f"comm-spot-{suffix}",
        "region_id": rid, "lat": 54.41, "lon": 10.22, "sports": ["kitesurf"],
        "water_type": ["sea"], "bottom_type": ["sand"], "level": ["beginner"],
        "water_character": ["chop"],
        "editorial": {"description": "Test spot for automated coverage."},
    })
    sid = s.json()["id"]
    client.post(f"/admin/spots/{sid}/image", json={
        "url": "https://images.example.com/hero.jpg", "source": "unsplash",
        "license": "Unsplash License", "credit": "Test",
    })
    # Community routes reject non-public spots — publish so the tests can
    # exercise them. Go-live enforces editorial completeness (Aug 2026), so
    # the fields above satisfy every required readiness gap.
    live = client.post(f"/admin/spots/{sid}/live")
    assert live.status_code == 200, live.text
    return sid


# --- ratings + aggregate ---------------------------------------------------

def test_rating_create_and_aggregate(anon_client, spot_id):
    for stars in (5, 3):
        resp = anon_client.post(f"/spots/{spot_id}/ratings", json={
            "stars": stars, "skill_level": "advanced", "sport": "kitesurf",
            "conditions": "20 Knoten, sonnig", "author_name": "Kai",
        })
        assert resp.status_code == 201, resp.text

    got = anon_client.get(f"/spots/{spot_id}/ratings")
    assert got.status_code == 200
    body = got.json()
    assert len(body["items"]) == 2
    assert body["aggregate"]["count"] == 2
    assert body["aggregate"]["avg"] == 4.0
    assert 3.0 < body["aggregate"]["score"] < 5.0
    # email is never exposed
    assert all("author_email" not in it for it in body["items"])


def test_anonymous_author_identity_is_server_controlled(anon_client, spot_id, db):
    response = anon_client.post(f"/spots/{spot_id}/tips", json={
        "body": "Sicherer anonymer Hinweis", "author_name": "Gefälschter Name",
        "author_email": "spoof@example.com",
    })
    assert response.status_code == 201, response.text
    row = db.get(LocalTip, uuid.UUID(response.json()["id"]))
    assert row.author_name == "Anonym"
    assert row.author_email is None
    assert row.app_user_id is None


def test_authenticated_upvote_is_idempotent_and_reversible(anon_client, spot_id, db):
    tip = anon_client.post(f"/spots/{spot_id}/tips", json={"body": "Hilfreicher Hinweis"})
    assert tip.status_code == 201, tip.text
    tip_id = tip.json()["id"]
    assert anon_client.put(f"/community/comments/tip/{tip_id}/upvote").status_code == 401

    email = f"voter-{uuid.uuid4().hex[:8]}@example.com"
    password = "pw-123456789"
    registered = anon_client.post("/account/register", json={
        "email": email, "password": password, "displayName": "Wind Voter",
    })
    assert registered.status_code == 202, registered.text
    login = anon_client.post("/account/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    anon_client.headers["X-CSRF-Token"] = anon_client.cookies.get(get_settings().csrf_cookie_name)

    first = anon_client.put(f"/community/comments/tip/{tip_id}/upvote")
    second = anon_client.put(f"/community/comments/tip/{tip_id}/upvote")
    assert first.json() == {"count": 1, "viewer_upvoted": True}
    assert second.json() == {"count": 1, "viewer_upvoted": True}
    removed = anon_client.delete(f"/community/comments/tip/{tip_id}/upvote")
    assert removed.json() == {"count": 0, "viewer_upvoted": False}


def test_bayesian_score_math():
    assert bayesian_score(0, 0, 3.5) == 3.5  # prior with no votes
    assert bayesian_score(1, 5, 3.5, c=5) == pytest.approx((5 * 3.5 + 5) / 6)


@pytest.mark.parametrize(
    "patch",
    [
        {"stars": 6},
        {"stars": 0},
        {"conditions": "  "},
        {"sport": "snowboard"},
        {"skill_level": "legend"},
    ],
)
def test_rating_validation(anon_client, spot_id, patch):
    body = {
        "stars": 4, "skill_level": "advanced", "sport": "kitesurf",
        "conditions": "böig", "author_name": "Kai",
    }
    body.update(patch)
    resp = anon_client.post(f"/spots/{spot_id}/ratings", json=body)
    assert resp.status_code == 422, resp.text


def test_rating_unknown_spot_404(anon_client):
    resp = anon_client.post(f"/spots/{uuid.uuid4()}/ratings", json={
        "stars": 4, "skill_level": "advanced", "sport": "kitesurf",
        "conditions": "solid wind", "author_name": "Kai",
    })
    assert resp.status_code == 404


# --- tips ------------------------------------------------------------------

def test_term_filter_flags_link_content(anon_client, spot_id, db):
    from app.models import LocalTip

    tid = anon_client.post(f"/spots/{spot_id}/tips", json={
        "body": "Mehr Infos auf http://spam.example", "author_name": "Max",
    }).json()["id"]
    # still published (post-moderation), but flagged for the review panel
    row = db.get(LocalTip, uuid.UUID(tid))
    assert row.status == "published" and row.flagged is True


def test_tip_create_and_only_published_visible(anon_client, spot_id, db):
    resp = anon_client.post(f"/spots/{spot_id}/tips", json={
        "body": "Bei Ostwind früh da sein.", "title": "Ostwind", "author_name": "Local",
    })
    assert resp.status_code == 201
    assert resp.json()["title"] == "Ostwind"

    # a hidden tip must not appear in the public list
    hidden = LocalTip(
        spot_id=uuid.UUID(spot_id), body="versteckt", author_name="x", status="hidden"
    )
    db.add(hidden)
    db.commit()

    listed = anon_client.get(f"/spots/{spot_id}/tips").json()["items"]
    bodies = {t["body"] for t in listed}
    assert next(t for t in listed if t["body"] == "Bei Ostwind früh da sein.")["title"] == "Ostwind"
    assert "Bei Ostwind früh da sein." in bodies
    assert "versteckt" not in bodies


# --- submissions -----------------------------------------------------------

def test_submission_stored_without_creating_spot(anon_client, spot_id, db):
    region_id = db.get(Spot, uuid.UUID(spot_id)).region_id
    before = db.scalar(select(func.count()).select_from(Spot))
    payload = {
        "name": "Vorgeschlagener Spot",
        "region_id": str(region_id),
        "lat": 54.5,
        "lon": 10.3,
        "sports": ["windsurf"],
    }
    resp = anon_client.post("/submissions", json={
        "payload": payload, "submitter_name": "Vorschlager",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending"
    # no new spot was created
    assert db.scalar(select(func.count()).select_from(Spot)) == before
    assert db.scalar(select(func.count()).select_from(SpotSubmission)) >= 1


def test_submission_invalid_payload_422(anon_client):
    resp = anon_client.post("/submissions", json={
        "payload": {"name": "kaputt"},  # missing region_id/lat/lon
        "submitter_name": "x",
    })
    assert resp.status_code == 422


# --- images ----------------------------------------------------------------

def _upload(client, sid, data, *, kind, license_accept=True, credit="Kai", review=False):
    form = {"kind": kind, "license_accept": str(license_accept).lower()}
    if credit is not None:
        form["credit"] = credit
    if review:
        form["review"] = "true"
    return client.post(
        f"/spots/{sid}/images",
        files={"file": ("photo.jpg", data, "image/jpeg")},
        data=form,
    )


def test_gallery_image_visible_hero_candidate_pending(anon_client, spot_id, db):
    from app.media import IMAGE_LICENSE_VERSION
    from app.models import SpotImage

    gallery = _upload(anon_client, spot_id, _img_bytes(1600, 1000), kind="gallery")
    assert gallery.status_code == 201, gallery.text

    hero = _upload(anon_client, spot_id, _img_bytes(3840, 2100), kind="hero_candidate")
    assert hero.status_code == 201, hero.text

    # gallery visible immediately; hero candidate awaits approval (not listed)
    visible = anon_client.get(f"/spots/{spot_id}/images").json()["items"]
    kinds = {i["kind"] for i in visible}
    assert "gallery" in kinds
    assert "hero_candidate" not in kinds

    # license provenance stored
    row = db.get(SpotImage, uuid.UUID(gallery.json()["id"]))
    assert row.license_version == IMAGE_LICENSE_VERSION
    assert row.license_accepted_at is not None
    assert row.status == "approved"
    hero_row = db.get(SpotImage, uuid.UUID(hero.json()["id"]))
    assert hero_row.status == "pending"


def test_gallery_upload_with_review_flag_is_pending_not_public(anon_client, spot_id, db):
    """The standalone "add a photo" form (decoupled from the composer) sets
    review=true so its upload lands in the admin queue instead of going
    straight to the public gallery."""
    from app.models import SpotImage

    up = _upload(anon_client, spot_id, _img_bytes(1600, 1000), kind="gallery", review=True)
    assert up.status_code == 201, up.text

    visible = anon_client.get(f"/spots/{spot_id}/images").json()["items"]
    assert up.json()["id"] not in {i["id"] for i in visible}
    assert db.get(SpotImage, uuid.UUID(up.json()["id"])).status == "pending"


def test_hero_candidate_too_small_422(anon_client, spot_id):
    resp = _upload(anon_client, spot_id, _img_bytes(1600, 1000), kind="hero_candidate")
    assert resp.status_code == 422


def test_image_requires_license_accept(anon_client, spot_id):
    resp = _upload(
        anon_client, spot_id, _img_bytes(1600, 1000), kind="gallery",
        license_accept=False,
    )
    assert resp.status_code == 422


def test_upload_reencodes_to_avif_or_webp(anon_client, spot_id):
    up = _upload(anon_client, spot_id, _img_bytes(2000, 1400), kind="gallery")
    assert up.status_code == 201, up.text
    assert up.json()["url"].rsplit(".", 1)[-1] in ("avif", "webp")


def test_public_gallery_uses_the_curated_position_order(anon_client, spot_id, db):
    from app.models import SpotImage

    first = _upload(anon_client, spot_id, _img_bytes(1600, 1000), kind="gallery")
    second = _upload(anon_client, spot_id, _img_bytes(1600, 1000), kind="gallery")
    first_row = db.get(SpotImage, uuid.UUID(first.json()["id"]))
    second_row = db.get(SpotImage, uuid.UUID(second.json()["id"]))
    first_row.position = 2
    second_row.position = 1
    db.commit()

    visible = anon_client.get(f"/spots/{spot_id}/images").json()["items"]
    assert [item["id"] for item in visible[:2]] == [second.json()["id"], first.json()["id"]]


def test_gallery_limit_enforced(anon_client, spot_id, db):
    from datetime import datetime, timezone

    from app.models import SpotImage

    for _ in range(15):
        db.add(SpotImage(
            spot_id=uuid.UUID(spot_id), url="x", kind="gallery", status="approved",
            license_version="v1", license_accepted_at=datetime.now(timezone.utc),
        ))
    db.commit()
    resp = _upload(anon_client, spot_id, _img_bytes(1600, 1000), kind="gallery")
    assert resp.status_code == 422
    assert "15" in resp.json()["detail"]


def test_image_report_increments_count(anon_client, spot_id):
    up = _upload(anon_client, spot_id, _img_bytes(1600, 1000), kind="gallery")
    image_id = up.json()["id"]
    resp = anon_client.post(f"/images/{image_id}/report", json={
        "reason": "copyright", "note": "Das ist mein Foto.",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["report_count"] == 1
    # second report bumps again
    resp2 = anon_client.post(f"/images/{image_id}/report", json={"reason": "other"})
    assert resp2.json()["report_count"] == 2


# --- rate limit + honeypot -------------------------------------------------

def test_rate_limit_kicks_in(anon_client, spot_id, monkeypatch):
    from app.api import community

    monkeypatch.setitem(community.LIMITS, "rating", (2, 60))
    limiter = InMemoryRateLimiter()  # one shared instance so hits accumulate
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        body = {
            "stars": 4, "skill_level": "advanced", "sport": "kitesurf",
            "conditions": "solid wind", "author_name": "Kai",
        }
        codes = [
            anon_client.post(f"/spots/{spot_id}/ratings", json=body).status_code
            for _ in range(3)
        ]
        assert codes[0] == 201 and codes[1] == 201
        assert codes[2] == 429
    finally:
        app.dependency_overrides[get_rate_limiter] = lambda: NoLimitRateLimiter()


def test_honeypot_rejects(anon_client, spot_id):
    resp = anon_client.post(f"/spots/{spot_id}/ratings", json={
        "stars": 4, "skill_level": "advanced", "sport": "kitesurf",
        "conditions": "solid wind", "author_name": "Kai", "website": "http://spam",
    })
    assert resp.status_code == 400


def test_license_endpoint(anon_client):
    body = anon_client.get("/community/license").json()
    assert body["version"] == "v1"
    assert "Einwilligung" in body["terms"]
