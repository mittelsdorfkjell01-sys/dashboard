"""Sprint D moderation tests: review queue + decisions + audit trail. DB-gated.

Uses the admin `client` (moderation is admin/curator only) and `anon_client` for
the public writes that create the review items.
"""

from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.admin.deps import get_cds_client, get_extract_client
from app.community.ratelimit import NoLimitRateLimiter, get_rate_limiter
from app.config import get_settings
from app.main import app
from app.models import (
    LocalTip,
    ModerationAudit,
    Spot,
    SpotImage,
    SpotRating,
    SpotSubmission,
)
from app.seed.seed import seed
from tests.conftest import TEST_ADMIN
from tests.era5_helpers import FakeCdsClient, make_synthetic_series


def _img_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 80, 140)).save(buf, "JPEG")
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
    fake = lambda: FakeCdsClient(make_synthetic_series())
    app.dependency_overrides[get_cds_client] = fake
    app.dependency_overrides[get_extract_client] = fake
    app.dependency_overrides[get_rate_limiter] = lambda: NoLimitRateLimiter()
    monkeypatch.setattr(get_settings(), "media_dir", str(tmp_path))
    yield
    for dep in (get_cds_client, get_extract_client, get_rate_limiter):
        app.dependency_overrides.pop(dep, None)


@pytest.fixture(autouse=True)
def _cleanup(db):
    """Remove this module's fixture rows after each test.

    Spots first, explicitly, before the region. Otherwise SQLAlchemy orphans
    them (region_id → NULL, which 0014 allowed) and later tests in the shared
    session find spots the seed did not create — same fix as in
    test_admin_api._cleanup_test_rows.
    """
    from sqlalchemy import delete

    yield
    from app.models import Region, Spot

    regions = db.scalars(
        select(Region).where(Region.slug.like("mod-region-%"))
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
    rid = client.post("/admin/regions", json={
        "name": f"Mod Region {suffix}", "slug": f"mod-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    }).json()["id"]
    sid = client.post("/admin/spots", json={
        "name": f"Mod Spot {suffix}", "slug": f"mod-spot-{suffix}",
        "region_id": rid, "lat": 54.41, "lon": 10.22, "sports": ["kitesurf"],
        "water_type": ["sea"], "bottom_type": ["sand"], "level": ["beginner"],
        "water_character": ["chop"],
        "editorial": {"description": "Test spot for automated coverage."},
    }).json()["id"]
    client.post(f"/admin/spots/{sid}/image", json={
        "url": "https://images.example.com/hero.jpg", "source": "unsplash",
        "license": "Unsplash License", "credit": "Test",
    })
    # The community routes (ratings/tips/images) reject non-public spots, so
    # every moderation test that goes through those needs the spot live.
    # Go-live enforces editorial completeness (Aug 2026), so the fields above
    # satisfy every required readiness gap.
    live = client.post(f"/admin/spots/{sid}/live")
    assert live.status_code == 200, live.text
    return sid, rid


def _audit_count(db, target_type, action=None) -> int:
    stmt = select(func.count()).select_from(ModerationAudit).where(
        ModerationAudit.target_type == target_type
    )
    if action:
        stmt = stmt.where(ModerationAudit.action == action)
    return int(db.scalar(stmt) or 0)


# --- submissions -----------------------------------------------------------

def test_submission_approve_creates_draft_spot(client, anon_client, spot_id, db):
    _, region_id = spot_id
    before = db.scalar(select(func.count()).select_from(Spot))
    payload = {
        "name": "Genehmigter Spot", "region_id": region_id,
        "lat": 54.5, "lon": 10.35, "sports": ["windsurf"],
    }
    sub_id = anon_client.post("/submissions", json={
        "payload": payload, "submitter_name": "Vorschlager",
    }).json()["id"]

    resp = client.post(f"/admin/submissions/{sub_id}/approve")
    assert resp.status_code == 201, resp.text
    new_spot_id = resp.json()["spot_id"]
    assert resp.json()["status"] == "draft"
    # a spot was created and the submission was linked + merged
    assert db.scalar(select(func.count()).select_from(Spot)) == before + 1
    sub = db.get(SpotSubmission, uuid.UUID(sub_id))
    assert sub.status == "merged"
    assert str(sub.resulting_spot_id) == new_spot_id
    assert _audit_count(db, "submission", "submission_approve") >= 1


def test_name_only_submission_needs_completion_then_approves(client, spot_id, db):
    """A name-only account proposal can't approve as-is (missing region/coords);
    once the admin supplies them it becomes a draft spot, keeping the proposed
    name and taking region + sports from the completion."""
    _, region_id = spot_id
    sub = SpotSubmission(
        payload={"name": "Nur ein Name"}, submitter_name="Gast", status="pending"
    )
    db.add(sub)
    db.commit()
    sid = str(sub.id)

    # no completion → 422 naming what's missing
    r0 = client.post(f"/admin/submissions/{sid}/approve")
    assert r0.status_code == 422, r0.text
    assert "Region" in r0.json()["detail"]

    # region only, still no coordinates → still 422
    r1 = client.post(f"/admin/submissions/{sid}/approve", json={"region_id": region_id})
    assert r1.status_code == 422

    # region + coordinates (+ sports) → draft spot
    ok = client.post(f"/admin/submissions/{sid}/approve", json={
        "region_id": region_id, "lat": 54.6, "lon": 10.4, "sports": ["wing"],
    })
    assert ok.status_code == 201, ok.text
    new_id = ok.json()["spot_id"]
    assert ok.json()["status"] == "draft"

    db.expire_all()
    spot = db.get(Spot, uuid.UUID(new_id))
    assert spot.name == "Nur ein Name"        # kept from the proposal
    assert str(spot.region_id) == region_id   # from the completion
    assert spot.sports == ["wing"]            # from the completion
    merged = db.get(SpotSubmission, uuid.UUID(sid))
    assert merged.status == "merged"
    assert str(merged.resulting_spot_id) == new_id


def test_submission_approval_uses_duplicate_warning_and_explicit_override(
    client, spot_id, db
):
    existing_id, region_id = spot_id
    existing = db.get(Spot, uuid.UUID(existing_id))
    sub = SpotSubmission(
        payload={
            "name": f"{existing.name} West",
            "region_id": region_id,
            "lat": 54.411,
            "lon": 10.221,
            "sports": ["kitesurf"],
        },
        submitter_name="Gast",
        status="pending",
    )
    db.add(sub)
    db.commit()

    warning = client.post(f"/admin/submissions/{sub.id}/approve")
    assert warning.status_code == 409, warning.text
    assert warning.json()["detail"]["code"] == "likely_duplicate"
    db.refresh(sub)
    assert sub.status == "pending"

    approved = client.post(
        f"/admin/submissions/{sub.id}/approve",
        json={"allow_duplicate": True},
    )
    assert approved.status_code == 201, approved.text


def test_already_decided_submission_conflicts(client, spot_id, db):
    """A submission that was already merged/rejected → 409, not 422."""
    _, region_id = spot_id
    sub = SpotSubmission(
        payload={"name": "Schon weg", "region_id": region_id, "lat": 54.5, "lon": 10.3},
        submitter_name="Gast", status="rejected",
    )
    db.add(sub)
    db.commit()
    resp = client.post(f"/admin/submissions/{sub.id}/approve")
    assert resp.status_code == 409, resp.text


def test_submission_reject_sets_status_and_note(client, anon_client, spot_id, db):
    _, region_id = spot_id
    sub_id = anon_client.post("/submissions", json={
        "payload": {"name": "Nein", "region_id": region_id, "lat": 54.5, "lon": 10.3},
        "submitter_name": "x",
    }).json()["id"]
    resp = client.post(f"/admin/submissions/{sub_id}/reject", json={"note": "Duplikat"})
    assert resp.status_code == 200
    sub = db.get(SpotSubmission, uuid.UUID(sub_id))
    assert sub.status == "rejected" and sub.review_note == "Duplikat"


# --- hero image approve ----------------------------------------------------

def test_hero_approve_writes_spot_image(client, anon_client, spot_id, db):
    sid, _ = spot_id
    img_id = anon_client.post(
        f"/spots/{sid}/images",
        files={"file": ("h.jpg", _img_bytes(3840, 2100), "image/jpeg")},
        data={"kind": "hero_candidate", "license_accept": "true", "credit": "Kai"},
    ).json()["id"]

    resp = client.post(f"/admin/images/{img_id}/approve")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "published_hero"
    spot = db.get(Spot, uuid.UUID(sid))
    assert spot.image and spot.image["url"]
    assert spot.image["source"] == "user_upload"
    assert _audit_count(db, "image", "image_approve") >= 1


def test_removing_a_published_hero_clears_the_spot_image(client, anon_client, spot_id, db):
    sid, _ = spot_id
    img_id = anon_client.post(
        f"/spots/{sid}/images",
        files={"file": ("h.jpg", _img_bytes(3840, 2100), "image/jpeg")},
        data={"kind": "hero_candidate", "license_accept": "true", "credit": "Kai"},
    ).json()["id"]
    assert client.post(f"/admin/images/{img_id}/approve").status_code == 200

    removed = client.post(f"/admin/images/{img_id}/remove", json={})
    assert removed.status_code == 200, removed.text
    db.expire_all()
    assert db.get(Spot, uuid.UUID(sid)).image is None
    assert db.get(SpotImage, uuid.UUID(img_id)).status == "removed"


def test_gallery_approve_makes_it_public_without_touching_spot_image(client, anon_client, spot_id, db):
    """A pending gallery photo (standalone upload form, review=true) approves
    via the same endpoint as hero candidates, but just flips its own status —
    it never becomes the spot's hero image."""
    sid, _ = spot_id
    before = db.get(Spot, uuid.UUID(sid)).image
    img_id = anon_client.post(
        f"/spots/{sid}/images",
        files={"file": ("g.jpg", _img_bytes(1600, 1000), "image/jpeg")},
        data={"kind": "gallery", "license_accept": "true", "review": "true"},
    ).json()["id"]
    assert img_id not in {
        i["id"] for i in anon_client.get(f"/spots/{sid}/images").json()["items"]
    }

    resp = client.post(f"/admin/images/{img_id}/approve")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"
    assert db.get(Spot, uuid.UUID(sid)).image == before
    assert img_id in {
        i["id"] for i in anon_client.get(f"/spots/{sid}/images").json()["items"]
    }


# --- reported image remove / dismiss ---------------------------------------

def test_report_then_remove_hides_image(client, anon_client, spot_id, db):
    sid, _ = spot_id
    img_id = anon_client.post(
        f"/spots/{sid}/images",
        files={"file": ("g.jpg", _img_bytes(1600, 1000), "image/jpeg")},
        data={"kind": "gallery", "license_accept": "true"},
    ).json()["id"]
    anon_client.post(f"/images/{img_id}/report", json={"reason": "copyright"})

    # appears in the reported queue
    queue = client.get("/admin/review/queue").json()
    assert any(i["id"] == img_id for i in queue["reported_images"])

    # remove → gone from the public gallery
    assert client.post(f"/admin/images/{img_id}/remove", json={}).status_code == 200
    visible = anon_client.get(f"/spots/{sid}/images").json()["items"]
    assert img_id not in {i["id"] for i in visible}
    assert db.get(SpotImage, uuid.UUID(img_id)).status == "removed"


def test_dismiss_reports_resets_count(client, anon_client, spot_id, db):
    sid, _ = spot_id
    img_id = anon_client.post(
        f"/spots/{sid}/images",
        files={"file": ("g.jpg", _img_bytes(1600, 1000), "image/jpeg")},
        data={"kind": "gallery", "license_accept": "true"},
    ).json()["id"]
    anon_client.post(f"/images/{img_id}/report", json={"reason": "other"})

    resp = client.post(f"/admin/images/{img_id}/dismiss-reports")
    assert resp.status_code == 200
    assert resp.json()["report_count"] == 0
    assert db.get(SpotImage, uuid.UUID(img_id)).report_count == 0


# --- tip / rating hide -----------------------------------------------------

def test_tip_hide_removes_from_public_keeps_in_db(client, anon_client, spot_id, db):
    sid, _ = spot_id
    tip_id = anon_client.post(f"/spots/{sid}/tips", json={
        "body": "Zu versteckender Tipp", "author_name": "Local",
    }).json()["id"]

    assert client.post(f"/admin/tips/{tip_id}/hide").status_code == 200
    public = anon_client.get(f"/spots/{sid}/tips").json()["items"]
    assert tip_id not in {t["id"] for t in public}
    # still present in the DB (reversible), just hidden
    assert db.get(LocalTip, uuid.UUID(tip_id)).status == "hidden"
    assert _audit_count(db, "tip", "tip_hide") >= 1

    # restore brings it back
    assert client.post(f"/admin/tips/{tip_id}/restore").status_code == 200
    public2 = anon_client.get(f"/spots/{sid}/tips").json()["items"]
    assert tip_id in {t["id"] for t in public2}


def test_rating_hide_removes_from_public(client, anon_client, spot_id, db):
    sid, _ = spot_id
    rating_id = anon_client.post(f"/spots/{sid}/ratings", json={
        "stars": 5, "skill_level": "expert", "sport": "kitesurf",
        "conditions": "böig", "author_name": "Kai",
    }).json()["id"]

    assert client.post(f"/admin/ratings/{rating_id}/hide").status_code == 200
    public = anon_client.get(f"/spots/{sid}/ratings").json()["items"]
    assert rating_id not in {r["id"] for r in public}
    assert db.get(SpotRating, uuid.UUID(rating_id)).status == "hidden"


def test_review_queue_lists_published_tips_and_ratings(client, anon_client, spot_id):
    """The Tips & Bewertungen tab shows all published items (not only flagged).

    author_name is server-controlled for anonymous posts (spoofing
    protection — see test_anonymous_author_identity_is_server_controlled), so
    entries are matched by their distinctive content, not a claimed name.
    """
    sid, _ = spot_id
    marker = uuid.uuid4().hex[:8]
    anon_client.post(f"/spots/{sid}/tips", json={"body": f"Guter Tipp {marker}", "author_name": "Max"})
    anon_client.post(f"/spots/{sid}/ratings", json={
        "stars": 5, "skill_level": "expert", "sport": "kitesurf",
        "conditions": f"top {marker}", "author_name": "Max",
    })
    q = client.get("/admin/review/queue").json()
    assert any(t["author_name"] == "Anonym" and marker in t["body"] for t in q["tips"])
    assert any(r["author_name"] == "Anonym" and marker in r["conditions"] for r in q["ratings"])


# --- audit actor + overview ------------------------------------------------

def test_audit_actor_is_logged_in_email(client, anon_client, spot_id, db):
    sid, region_id = spot_id
    sub_id = anon_client.post("/submissions", json={
        "payload": {"name": "Aktor", "region_id": region_id, "lat": 54.5, "lon": 10.3},
        "submitter_name": "x",
    }).json()["id"]
    client.post(f"/admin/submissions/{sub_id}/reject", json={"note": "nope"})
    entry = db.scalars(
        select(ModerationAudit)
        .where(ModerationAudit.target_id == uuid.UUID(sub_id))
        .order_by(ModerationAudit.created_at.desc())
    ).first()
    assert entry is not None and entry.actor == TEST_ADMIN["email"]


def test_overview_includes_review_counts(client, anon_client, spot_id):
    sid, region_id = spot_id
    anon_client.post("/submissions", json={
        "payload": {"name": "Q", "region_id": region_id, "lat": 54.5, "lon": 10.3},
        "submitter_name": "x",
    })
    review = client.get("/admin/overview").json()["review"]
    assert "submissions_pending" in review
    assert review["submissions_pending"] >= 1


def test_moderation_requires_auth(anon_client):
    assert anon_client.get("/admin/review/queue").status_code == 401
