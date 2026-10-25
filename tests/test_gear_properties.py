import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.gear.importer import (
    GearImportError,
    import_staging_records,
    load_staging_file,
    validate_staging_document,
)
from app.gear.catalog import _claim_payload, list_catalog
from app.gear.properties import PROPERTY_REGISTRY, PropertyValidationError, validate_property


def test_property_registry_validates_units_values_and_scope():
    result = validate_property(
        {"field": "weight_without_bag", "value": 3.5, "unit": "kg"},
        default_scope="size",
    )
    assert result.value == {"value": 3.5}
    assert result.group == "dimensions"

    with pytest.raises(PropertyValidationError, match="unit"):
        validate_property(
            {"field": "weight_without_bag", "value": 3.5, "unit": "lb"},
            default_scope="size",
        )
    with pytest.raises(PropertyValidationError, match="unknown gear property"):
        validate_property({"field": "marketing_superpower", "value": "yes"}, default_scope="version")
    with pytest.raises(PropertyValidationError, match="unknown gear property"):
        validate_property(
            {"field": "wind_range", "min": 15, "max": 30, "unit": "kn"},
            default_scope="size",
        )


def test_registry_contains_research_fields_needed_for_geometry_and_compatibility():
    assert {
        "catalogue_presence", "projected_area", "flat_span", "tip_sweep", "bar_compatibility"
    } <= PROPERTY_REGISTRY.keys()


def test_catalogue_presence_records_models_without_inventing_years_or_sizes():
    result = validate_property(
        {
            "field": "catalogue_presence",
            "value": "Listed on the manufacturer's current kite collection page.",
        },
        default_scope="version",
    )
    assert result.value == {
        "value": "Listed on the manufacturer's current kite collection page."
    }
    assert result.group == "identity"


def test_catalog_claim_payload_exposes_property_group():
    claim = SimpleNamespace(
        field_name="weight_without_bag", value={"value": 3.5}, unit="kg",
        verification_status="verified", verified_at=None, uncertainty_note=None,
    )
    source = SimpleNamespace(
        title="Official weights", publisher="CORE", url="https://example.com/weights",
        source_type="manufacturer_page", checked_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
    )
    assert _claim_payload(claim, source)["group"] == "dimensions"


def test_current_pilot_staging_file_passes_validation():
    records = load_staging_file(Path("research/gear/staging/pilot.json"))
    assert [record.brand for record in records] == ["CORE", "Duotone", "F-One"]
    assert sum(len(record.claims) for record in records) == 10


def test_core_gts6_complete_batch_passes_validation_without_wind_ranges():
    path = Path("research/gear/staging/core-gts6-complete-2026-10-24.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    records = validate_staging_document(document)
    assert len(records) == 24
    assert sum(len(record.claims) for record in records) == 45
    assert sum(len(record.compatibilities) for record in records) == 18
    assert sum(len(record.use_profiles) for record in records) == 8
    assert "windRangeKn" not in path.read_text(encoding="utf-8")


def test_remaining_supplied_list_batches_pass_validation_without_wind_ranges():
    paths = sorted(Path("research/gear/staging").glob("remaining-*-2026-10-24.json"))
    assert len(paths) == 5
    records = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "windRangeKn" not in text
        records.extend(validate_staging_document(json.loads(text)))
    assert len(records) == 690
    assert sum(record.size_label is not None for record in records) == 548
    assert sum(len(record.compatibilities) for record in records) == 7
    assert sum(len(record.use_profiles) for record in records) == 63
    assert all(
        any(claim.property.field == "catalogue_presence" for claim in record.claims)
        for record in records if record.size_label is None
    )


def test_review_example_covers_compatibility_and_use_profiles():
    path = Path("research/gear/review/core-xr8-catalog-example.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["reviewStatus"] == "review_requested"
    document["reviewStatus"] = "accepted_for_import"
    record = validate_staging_document(document)[0]
    assert record.model == "XR8"
    assert {item.target_category for item in record.compatibilities} == {"bar", "line_set"}
    assert {item.discipline for item in record.use_profiles} == {"big_air", "freeride"}
    assert any(item.condition == "strong_wind" and item.status == "review" for item in record.use_profiles)


def test_staging_requires_review_rights_source_and_known_properties():
    document = {
        "reviewStatus": "draft",
        "checkedAt": "2026-10-22T12:00:00Z",
        "rights": "Facts only.",
        "records": [],
    }
    with pytest.raises(GearImportError, match="accepted"):
        validate_staging_document(document)

    document["reviewStatus"] = "accepted_for_import"
    document["records"] = [{
        "brand": "Example", "model": "One", "season": "2026", "size": "9 m²",
        "source": "https://example.com/product",
        "claims": [{"field": "not_registered", "value": 1, "status": "verified"}],
    }]
    with pytest.raises(GearImportError, match="unknown gear property"):
        validate_staging_document(json.loads(json.dumps(document)))


def test_staging_rejects_invalid_category_and_claim_without_source():
    document = {
        "reviewStatus": "accepted_for_import",
        "checkedAt": "2026-10-22T12:00:00Z",
        "rights": "Facts only.",
        "records": [{
            "brand": "Example", "model": "One", "season": "2026",
            "category": "paraglider",
            "claims": [{"field": "strut_count", "value": 3}],
        }],
    }
    with pytest.raises(GearImportError, match="source"):
        validate_staging_document(document)
    document["records"][0]["source"] = "https://example.com/product"
    with pytest.raises(GearImportError, match="category"):
        validate_staging_document(document)


def test_importer_persists_compatibility_and_use_profiles(db):
    document = {
        "reviewStatus": "accepted_for_import",
        "checkedAt": "2026-10-23T17:00:00Z",
        "rights": "Facts only.",
        "records": [{
            "brand": "Review Example", "name": "Control", "category": "bar",
            "season": "Prototype",
            "source": "https://example.com/review-control",
            "claims": [{
                "field": "bar_compatibility", "value": "4-line control bar",
                "status": "review",
            }],
        }, {
            "brand": "Review Example", "name": "WindLab", "category": "kite",
            "season": "Prototype", "size": "9 m²",
            "source": "https://example.com/review-windlab",
            "compatibility": [{
                "targetCategory": "bar", "relation": "recommended",
                "targetProduct": {
                    "brand": "Review Example", "name": "Control", "season": "Prototype"
                },
                "specification": {"lineCount": 4}, "status": "review",
            }],
            "useProfiles": [{
                "sport": "kitesurf", "discipline": "wave", "condition": "waves",
                "suitability": "designed_for", "status": "review",
            }],
        }],
    }
    summary = import_staging_records(db, validate_staging_document(document))
    assert summary.created["compatibilities"] == 1
    assert summary.created["useProfiles"] == 1
    imported = next(
        item for item in list_catalog(db, "kite")
        if item["brand"]["name"] == "Review Example"
    )
    target = imported["compatibility"][0]["targetProduct"]
    assert target["brand"]["name"] == "Review Example"
    assert target["name"] == "Control"
    assert target["season"] == "Prototype"
    db.rollback()


def test_staging_rejects_numeric_wind_ranges():
    document = {
        "reviewStatus": "accepted_for_import",
        "checkedAt": "2026-10-23T17:00:00Z",
        "rights": "Facts only.",
        "records": [{
            "brand": "Example", "name": "Kite", "category": "kite",
            "season": "2026", "source": "https://example.com/kite",
            "useProfiles": [{
                "sport": "kitesurf", "discipline": "big_air",
                "condition": "strong_wind", "suitability": "suitable",
                "windRangeKn": {"min": 20, "max": 35},
            }],
        }],
    }
    with pytest.raises(GearImportError, match="must not define windRangeKn"):
        validate_staging_document(document)
