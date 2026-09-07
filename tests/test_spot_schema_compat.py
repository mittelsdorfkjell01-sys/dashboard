from types import SimpleNamespace
from uuid import uuid4

from app.schemas.spot import SpotSummary


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
        image=None,
    )

    summary = SpotSummary.from_orm_spot(row)

    assert summary.water_type == ["ocean"]
    assert summary.bottom_type == ["sand", "reef"]
    assert summary.level == ["beginner", "advanced"]
    assert summary.water_character == []
