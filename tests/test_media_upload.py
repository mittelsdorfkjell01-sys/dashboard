"""Hero-image upload endpoint: server-side validation + storage.

DB-gated (needs a spot to attach to). Images are generated with Pillow and the
storage dir is redirected to a tmp path so the repo stays clean.
"""

from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image
from sqlalchemy import select

from app.admin.deps import get_cds_client
from app.config import get_settings
from app.main import app
from app.media import validate_hero_image
from app.media.hero import HeroImageError
from app.seed.seed import seed
from tests.era5_helpers import FakeCdsClient, make_synthetic_series


def _img_bytes(w: int, h: int, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 80, 140)).save(buf, fmt)
    return buf.getvalue()


# --- pure validation -------------------------------------------------------

def test_validate_hero_accepts_large_landscape():
    w, h, ext = validate_hero_image(_img_bytes(3840, 2100), "image/jpeg")
    assert (w, h, ext) == (3840, 2100, "jpg")


def test_validate_hero_rejects_small():
    with pytest.raises(HeroImageError):
        validate_hero_image(_img_bytes(1200, 800), "image/jpeg")


def test_validate_hero_rejects_portrait():
    with pytest.raises(HeroImageError):
        validate_hero_image(_img_bytes(2100, 3840), "image/jpeg")


def test_validate_hero_rejects_wrong_format():
    with pytest.raises(HeroImageError):
        validate_hero_image(_img_bytes(3840, 2100, "GIF"), "image/gif")


# --- DB-gated endpoint tests -----------------------------------------------

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


@pytest.fixture
def admin(client, tmp_path, monkeypatch):
    app.dependency_overrides[get_cds_client] = lambda: FakeCdsClient(
        make_synthetic_series()
    )
    # Redirect uploads to a tmp dir so the repo working tree stays clean.
    monkeypatch.setattr(get_settings(), "media_dir", str(tmp_path))
    yield client
    app.dependency_overrides.pop(get_cds_client, None)


@pytest.fixture(autouse=True)
def _cleanup(db):
    yield
    from app.models import Region

    for region in db.scalars(
        select(Region).where(Region.slug.like("up-region-%"))
    ).all():
        db.delete(region)
    db.commit()


@pytest.fixture
def spot_id(admin):
    suffix = uuid.uuid4().hex[:8]
    r = admin.post("/admin/regions", json={
        "name": f"Up Region {suffix}", "slug": f"up-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    })
    rid = r.json()["id"]
    s = admin.post("/admin/spots", json={
        "name": f"Up Spot {suffix}", "slug": f"up-spot-{suffix}",
        "region_id": rid, "lat": 54.41, "lon": 10.22, "sports": ["kitesurf"],
    })
    return s.json()["id"]


def _upload(admin, sid, data, credit="Jo", filename="hero.jpg", ct="image/jpeg"):
    return admin.post(
        f"/admin/spots/{sid}/image/upload",
        files={"file": (filename, data, ct)},
        data={"credit": credit},
    )


def test_upload_valid_sets_image_record(admin, spot_id):
    resp = _upload(admin, spot_id, _img_bytes(3840, 2100))
    assert resp.status_code == 200, resp.text
    img = resp.json()["image"]
    assert img["source"] == "upload" and img["license"] == "own"
    assert img["credit"] == "Jo"
    assert img["url"].startswith("/media/images/")
    assert "-responsive-" in img["url"]


def test_upload_below_min_accepted_for_admin(admin, spot_id):
    # Admin operators may upload below-minimum-resolution heroes (the client
    # shows a blur warning); the server mirrors that and stores it.
    resp = _upload(admin, spot_id, _img_bytes(1000, 700))
    assert resp.status_code == 200, resp.text
    assert resp.json()["image"]["url"].startswith("/media/images/")


def test_upload_portrait_still_rejected(admin, spot_id):
    # allow_below_min only relaxes resolution — orientation is still enforced.
    resp = _upload(admin, spot_id, _img_bytes(700, 1000))
    assert resp.status_code == 422
    assert "Querformat" in resp.json()["detail"]


def test_upload_wrong_format_rejected(admin, spot_id):
    resp = _upload(admin, spot_id, _img_bytes(3840, 2100, "GIF"), ct="image/gif")
    assert resp.status_code == 422


def test_upload_requires_credit(admin, spot_id):
    resp = admin.post(
        f"/admin/spots/{spot_id}/image/upload",
        files={"file": ("h.jpg", _img_bytes(3840, 2100), "image/jpeg")},
        data={"credit": "   "},
    )
    assert resp.status_code == 422


def test_upload_unknown_spot_404(admin):
    resp = _upload(admin, uuid.uuid4(), _img_bytes(3840, 2100))
    assert resp.status_code == 404
