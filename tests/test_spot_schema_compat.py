from types import SimpleNamespace
from uuid import uuid4

from app.schemas.region import RegionRead
from app.schemas.spot import SpotRead, SpotSummary, _public_editorial


def test_spot_summary_passes_through_array_backed_categories() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        slug="array-backed",
        name="Array Backed",
        region_id=uuid4(),
        location=None,
        sports=["surf"],
        water_type=["ocean"],
        bottom_type=["sand", "reef"],
        level=["beginner", "advanced"],
        water_character=[],
        style=[],
        facilities=None,
        status="published",
        confidence=None,
        facing=None,
        editorial_classification="worth_trip",
        image=None,
    )

    summary = SpotSummary.from_orm_spot(row)

    assert summary.water_type == ["ocean"]
    assert summary.bottom_type == ["sand", "reef"]
    assert summary.level == ["beginner", "advanced"]
    assert summary.water_character == []
    assert summary.editorial_classification == "worth_trip"


def test_public_schemas_do_not_expose_retired_content_review_metadata() -> None:
    retired_fields = {
        "content_status",
        "content_reviewed_at",
        "content_review_due_at",
        "content_sources",
    }

    assert retired_fields.isdisjoint(SpotSummary.model_fields)
    assert retired_fields.isdisjoint(SpotRead.model_fields)
    assert retired_fields.isdisjoint(RegionRead.model_fields)
    assert _public_editorial({
        "description": "Useful spot description.",
        "classification_reason": "Internal reasoning.",
        "confidence_override": 0.9,
    }) == {"description": "Useful spot description."}
