"""Shared helpers for tests that intentionally publish catalogue spots."""

from datetime import datetime, timezone


def verify_spot_content(admin, spot_id: str) -> None:
    """Satisfy the same evidence gate an editor must pass before publication."""
    editorial = admin.patch(
        f"/admin/spots/{spot_id}",
        json={
            "editorial": {
                "description": "Test spot for automated coverage.",
                "safety_notice": "Check current, access and local rules on site.",
            }
        },
    )
    assert editorial.status_code == 200, editorial.text

    checked_at = datetime.now(timezone.utc).isoformat()
    for field_path in (
        "location",
        "sports",
        "level",
        "editorial.description",
        "editorial.safety_notice",
    ):
        source = admin.post(
            f"/admin/spots/{spot_id}/content-sources",
            json={
                "field_path": field_path,
                "url": f"https://example.test/source/{field_path.replace('.', '-')}",
                "title": f"Test source for {field_path}",
                "publisher": "Test Publisher",
                "checked_at": checked_at,
                "verification_status": "verified",
            },
        )
        assert source.status_code == 201, source.text

    review = admin.patch(
        f"/admin/spots/{spot_id}/content-review", json={"status": "verified"}
    )
    assert review.status_code == 200, review.text
