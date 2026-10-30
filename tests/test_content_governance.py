from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.admin.content_governance import (
    REQUIRED_SOURCE_MAX_AGE_DAYS,
    content_governance_checklist,
    content_governance_warnings,
    content_attention_flags,
    mark_content_changed,
    verification_prerequisite_gaps,
)


def _spot(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "location": object(),
        "sports": ["surf"],
        "level": ["advanced"],
        "editorial": {
            "description": "Schneller Beachbreak über Sand.",
            "safety_notice": "Kräftige Brandung und wechselnde Strömungen.",
        },
        "image": {
            "url": "https://images.example.test/spot.jpg",
            "source": "https://images.example.test/source",
            "license": "CC BY 4.0",
            "credit": "Example Photographer",
        },
        "content_status": "unreviewed",
        "content_reviewed_at": None,
        "content_review_due_at": None,
        "content_sources": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data), now


def _sources(now):
    return [
        SimpleNamespace(
            field_path=field,
            verification_status="verified",
            checked_at=now - timedelta(days=1),
        )
        for field in REQUIRED_SOURCE_MAX_AGE_DAYS
    ]


def test_unreviewed_spot_has_explicit_content_and_source_gaps():
    spot, now = _spot()

    checklist = content_governance_checklist(spot, now=now)
    gaps = {item["field"] for item in checklist if not item["ok"]}

    assert "content.source.location" in gaps
    assert "content.source.editorial.description" in gaps
    assert "content.status.verified" in gaps
    assert "content.reviewed_at" in gaps
    assert "content.review_due" in gaps


def test_verified_spot_with_current_field_sources_passes_governance():
    spot, now = _spot()
    spot.content_sources = _sources(now)
    spot.content_status = "verified"
    spot.content_reviewed_at = now
    spot.content_review_due_at = now + timedelta(days=365)

    assert all(item["ok"] for item in content_governance_checklist(spot, now=now))
    assert verification_prerequisite_gaps(spot, now=now) == []


def test_stale_safety_source_is_blocking_and_visible():
    spot, now = _spot()
    spot.content_sources = _sources(now)
    safety = next(
        source
        for source in spot.content_sources
        if source.field_path == "editorial.safety_notice"
    )
    safety.checked_at = now - timedelta(days=366)

    gaps = verification_prerequisite_gaps(spot, now=now)

    assert "content.source.editorial.safety_notice" in gaps
    assert content_governance_warnings(spot, now=now) == ["content.sources.stale"]


def test_verified_content_change_becomes_review_due_without_erasing_history():
    spot, now = _spot(
        content_status="verified",
        content_reviewed_at=datetime.now(timezone.utc) - timedelta(days=5),
        content_review_due_at=datetime.now(timezone.utc) + timedelta(days=360),
    )

    changed = mark_content_changed(spot, fields={"editorial"})

    assert changed is True
    assert spot.content_status == "review_due"
    assert spot.content_reviewed_at is not None
    assert spot.content_review_due_at <= now + timedelta(seconds=1)


def test_non_claim_operational_change_does_not_invalidate_review():
    spot, _ = _spot(content_status="verified")

    assert mark_content_changed(spot, fields={"model_pref"}) is False
    assert spot.content_status == "verified"


def test_attention_flags_keep_conflict_staleness_and_license_separate():
    spot, now = _spot(image=None)
    spot.content_sources = _sources(now)
    spot.content_sources[0].verification_status = "conflict"

    flags = content_attention_flags(spot, now=now)

    assert flags["incomplete"] is True
    assert flags["unreviewed"] is True
    assert flags["conflict"] is True
    assert flags["license"] is True
    assert flags["stale"] is False


def test_ranked_spot_needs_an_editorial_reason_before_verification():
    spot, now = _spot(editorial_classification="worth_trip")
    spot.content_sources = _sources(now)

    assert "content.field.editorial.classification_reason" in verification_prerequisite_gaps(
        spot, now=now
    )

    spot.editorial["classification_reason"] = "Eigenständige Reiseattraktivität."
    assert verification_prerequisite_gaps(spot, now=now) == []
