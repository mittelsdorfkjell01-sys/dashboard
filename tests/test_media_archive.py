"""Compressed image evidence, with DB retention checks where Postgres exists."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.media.archive import (
    archive_retired_images,
    decode_archive_payload,
    encode_archive_payload,
)
from app.models import (
    ImageReport,
    ModerationAudit,
    SpotImage,
    SpotImageArchive,
)
from app.models import Spot
from tests.conftest import require_db


@pytest.fixture(scope="module", autouse=True)
def _catalogue(_migrated_db):
    from app.db.session import SessionLocal
    from app.seed.seed import seed

    require_db()
    with SessionLocal() as session:
        seed(session)


@pytest.fixture
def spot_id(db):
    return db.scalar(select(Spot.id).where(Spot.slug == "tarifa-los-lances"))


def _retired_image(*, spot_id=None, now=None) -> SpotImage:
    moment = now or datetime.now(timezone.utc)
    return SpotImage(
        id=uuid.uuid4(),
        spot_id=spot_id or uuid.uuid4(),
        url="/media/images/ab/hash-responsive-none.avif",
        kind="gallery",
        source="user_upload",
        credit="Mara",
        submitter_email="private@example.test",
        ip_hash="private-ip-hash",
        license_version="2026-01",
        license_name="own",
        delivery="hosted",
        geo_verified=False,
        status="removed",
        report_count=1,
        reviewed_by="curator@example.test",
        reviewed_at=moment,
        created_at=moment,
        updated_at=moment,
    )


def test_archive_payload_is_compact_checksummed_and_privacy_reduced():
    image = _retired_image()
    report = ImageReport(
        id=uuid.uuid4(),
        image_id=image.id,
        reason="rights",
        note="x" * 500,
        reporter_email="reporter@example.test",
        ip_hash="reporter-ip-hash",
        created_at=image.created_at,
        updated_at=image.updated_at,
    )
    audit = ModerationAudit(
        id=uuid.uuid4(),
        actor="curator@example.test",
        action="remove_image",
        target_type="image",
        target_id=image.id,
        note="rights checked",
        created_at=image.created_at,
    )
    payload, checksum, original_bytes = encode_archive_payload(
        image, [report], [audit]
    )
    archive = SpotImageArchive(
        id=image.id,
        entity_type="spot",
        entity_id=image.spot_id,
        status=image.status,
        created_at=image.created_at,
        archived_at=image.updated_at,
        payload=payload,
        payload_sha256=checksum,
        original_bytes=original_bytes,
        compressed_bytes=len(payload),
    )
    snapshot = decode_archive_payload(archive)
    assert snapshot["image"]["license_version"] == "2026-01"
    assert snapshot["reports"][0]["reason"] == "rights"
    assert snapshot["moderation"][0]["action"] == "remove_image"
    serialized = str(snapshot)
    assert "private@example.test" not in serialized
    assert "private-ip-hash" not in serialized
    assert "reporter@example.test" not in serialized
    assert len(payload) < original_bytes


def test_archive_payload_detects_corruption():
    image = _retired_image()
    payload, checksum, original_bytes = encode_archive_payload(image)
    archive = SpotImageArchive(
        id=image.id,
        entity_type="spot",
        entity_id=image.spot_id,
        status=image.status,
        created_at=image.created_at,
        archived_at=image.updated_at,
        payload=payload,
        payload_sha256="0" * 64,
        original_bytes=original_bytes,
        compressed_bytes=len(payload),
    )
    with pytest.raises(ValueError, match="checksum"):
        decode_archive_payload(archive)


def test_old_terminal_row_moves_to_archive_with_reports_and_audit(db, spot_id):
    now = datetime.now(timezone.utc)
    image = _retired_image(spot_id=spot_id, now=now - timedelta(days=200))
    db.add(image)
    db.flush()
    db.add(
        ImageReport(
            image_id=image.id,
            reason="rights",
            note="source disputed",
            reporter_email="remove-me@example.test",
        )
    )
    db.add(
        ModerationAudit(
            actor="curator@example.test",
            action="remove_image",
            target_type="image",
            target_id=image.id,
            note="verified",
        )
    )
    db.commit()

    result = archive_retired_images(db, retention_days=180, limit=10, now=now)

    assert result["archived"] == 1
    assert db.get(SpotImage, image.id) is None
    archive = db.get(SpotImageArchive, image.id)
    snapshot = decode_archive_payload(archive)
    assert snapshot["reports"][0]["note"] == "source disputed"
    assert snapshot["moderation"][0]["action"] == "remove_image"
