"""Shared helpers for tests that intentionally publish catalogue spots."""


def verify_spot_content(admin, spot_id: str) -> None:
    """Fill the editorial fields needed by catalogue publication tests."""
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
