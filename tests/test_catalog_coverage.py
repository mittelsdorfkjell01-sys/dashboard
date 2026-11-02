from types import SimpleNamespace
from uuid import uuid4

from app.admin.catalog_coverage import build_coverage_matrix


def test_coverage_matrix_keeps_publication_maturity_and_relevance_separate():
    region = SimpleNamespace(id=uuid4(), name="Test Coast", country="DE")
    spots = [
        SimpleNamespace(
            region_id=region.id,
            sports=["surf", "wing"],
            status="published",
            content_status="review_due",
            editorial_classification="worth_trip",
        ),
        SimpleNamespace(
            region_id=region.id,
            sports=["surf"],
            status="draft",
            content_status="unreviewed",
            editorial_classification=None,
        ),
    ]

    report = build_coverage_matrix([region], spots)
    surf = next(row for row in report["rows"] if row["sport"] == "surf")
    wing = next(row for row in report["rows"] if row["sport"] == "wing")
    windsurf = next(row for row in report["rows"] if row["sport"] == "windsurf")

    assert surf["total"] == 2
    assert surf["publication"] == {"draft": 1, "published": 1, "archived": 0}
    assert surf["content"]["review_due"] == 1
    assert surf["classification"]["unranked"] == 1
    assert wing["total"] == 1
    assert windsurf["total"] == 0
    assert report["summary"]["spots"] == 2
    assert report["summary"]["single_spot_regions"] == 0


def test_coverage_reports_single_spot_regions_and_unassigned_without_double_counting():
    region = SimpleNamespace(id=uuid4(), name="Small Coast", country="PT")
    spots = [
        SimpleNamespace(
            region_id=region.id,
            sports=["surf", "kitesurf"],
            status="draft",
            content_status="unreviewed",
            editorial_classification=None,
        ),
        SimpleNamespace(
            region_id=None,
            sports=["surf"],
            status="draft",
            content_status="unreviewed",
            editorial_classification=None,
        ),
    ]
    report = build_coverage_matrix([region], spots)
    assert report["summary"]["spots"] == 2
    assert report["summary"]["single_spot_regions"] == 1
    assert report["summary"]["unassigned"] == 1
