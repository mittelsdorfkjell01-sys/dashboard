from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.importers.spots import ImportFormatError, import_spots, load_rows, normalize_row
from app.models import Region, Spot, SpotContentSource


def test_load_json_accepts_spots_envelope(tmp_path):
    path = tmp_path / "spots.json"
    path.write_text(json.dumps({"spots": [{"slug": "one"}]}), encoding="utf-8")
    assert load_rows(path) == [{"slug": "one"}]


def test_load_json_accepts_transactional_spot_and_sources_envelope(tmp_path):
    path = tmp_path / "spots.json"
    path.write_text(json.dumps({"spots": [{
        "spot": {"slug": "one", "name": "One"},
        "sources": [{"field_path": "name"}],
    }]}), encoding="utf-8")
    assert load_rows(path) == [{
        "slug": "one", "name": "One", "sources": [{"field_path": "name"}],
    }]


def test_normalize_json_row_supports_location_and_description():
    row = normalize_row(
        {
            "slug": "nordstrand",
            "name": "Nordstrand",
            "region_slug": "kiel",
            "location": [10.22, 54.41],
            "sports": ["kitesurf", "wing"],
            "description": "Viel Platz",
        },
        1,
    )
    assert (row["lat"], row["lon"]) == (54.41, 10.22)
    assert row["sports"] == ["kitesurf", "wing"]
    assert row["editorial"] == {"description": "Viel Platz"}


def test_normalize_csv_row_parses_pipe_lists_and_json_objects():
    row = normalize_row(
        {
            "slug": "nordstrand",
            "name": "Nordstrand",
            "region_slug": "kiel",
            "lat": "54.41",
            "lon": "10.22",
            "sports": "kitesurf|wing",
            "facilities": '{"parking":{"available":true}}',
        },
        2,
    )
    assert row["sports"] == ["kitesurf", "wing"]
    assert row["facilities"] == {"parking": {"available": True}}


def test_normalize_supports_aliases_variants_wind_and_field_sources():
    row = normalize_row(
        {
            "slug": "nordstrand",
            "name": "Nordstrand",
            "region_slug": "kiel",
            "lat": 54.41,
            "lon": 10.22,
            "sports": ["kitesurf"],
            "aliases": ["Nordstrand Beach"],
            "best_wind_directions": ["W", "NW"],
            "variant_conditions": {
                "kitesurf:foil": {"suitability": "eingeschraenkt", "usable_depth_m": 1.5}
            },
            "sources": [{
                "field_path": "best_wind_directions",
                "url": "https://example.test/spot",
                "title": "Local spot guide",
                "publisher": "Example Club",
                "checked_at": "2026-11-09T12:00:00+01:00",
                "verification_status": "verified",
                "note": "Belegt W und NW.",
            }],
        },
        1,
    )
    assert row["editorial"]["aliases"] == ["Nordstrand Beach"]
    assert row["best_wind_directions"] == ["W", "NW"]
    assert row["variant_conditions"]["kitesurf:foil"]["usable_depth_m"] == 1.5
    assert row["sources"][0]["checked_at"].utcoffset() is not None


def test_normalize_rejects_incomplete_or_ambiguous_sources():
    base = {
        "slug": "nordstrand", "name": "Nordstrand", "region_slug": "kiel",
        "lat": 54.41, "lon": 10.22, "sports": ["wing"],
    }
    with pytest.raises(ImportFormatError, match="checked_at"):
        normalize_row({**base, "sources": [{
            "field_path": "sports", "url": "https://example.test/spot", "title": "Guide",
        }]}, 1)
    with pytest.raises(ImportFormatError, match="Zeitzone"):
        normalize_row({**base, "sources": [{
            "field_path": "sports", "url": "https://example.test/spot", "title": "Guide",
            "checked_at": "2026-11-09T12:00:00",
        }]}, 1)


def test_normalize_validates_image_rights():
    row = normalize_row(
        {
            "slug": "nordstrand",
            "name": "Nordstrand",
            "region_slug": "kiel",
            "lat": 54.41,
            "lon": 10.22,
            "sports": ["wing"],
            "image": {
                "url": "https://example.test/photo.jpg",
                "source": "Official gallery",
                "license": "CC BY 4.0",
                "credit": "Example Photographer",
            },
        },
        1,
    )
    assert row["image"]["credit"] == "Example Photographer"
def test_normalize_rejects_unknown_columns_and_missing_coordinates():
    base = {
        "slug": "nordstrand",
        "name": "Nordstrand",
        "region_slug": "kiel",
        "sports": "wing",
    }
    with pytest.raises(ImportFormatError, match="unbekannte Felder"):
        normalize_row({**base, "sportz": "wing", "lat": 1, "lon": 2}, 2)
    with pytest.raises(ImportFormatError, match="lat, lon"):
        normalize_row(base, 2)


def test_import_is_dry_run_safe_and_idempotent(db, tmp_path):
    token = uuid.uuid4().hex[:10]
    region = Region(slug=f"import-region-{token}", name=f"Import Region {token}")
    db.add(region)
    db.commit()

    spot_slug = f"import-spot-{token}"
    path = tmp_path / "spots.json"
    path.write_text(
        json.dumps({
            "spots": [{
                "spot": {
                    "slug": spot_slug,
                    "name": f"Import Spot {token}",
                    "region_slug": region.slug,
                    "lat": 54.4,
                    "lon": 10.2,
                    "sports": ["wing"],
                    "aliases": [f"Import Beach {token}"],
                },
                "sources": [{
                    "field_path": "sports",
                    "url": f"https://example.test/{spot_slug}",
                    "title": "Local watersports club",
                    "publisher": "Example Club",
                    "checked_at": "2026-11-09T12:00:00+01:00",
                    "verification_status": "verified",
                    "note": "Belegt Wing-Nutzung.",
                }],
            }]
        }),
        encoding="utf-8",
    )

    dry = import_spots(path, db=db, dry_run=True)
    assert dry.ok and dry.created == [spot_slug]
    assert dry.source_records == 1
    assert dry.preview[0]["action"] == "would_create"
    assert db.scalar(select(Spot).where(Spot.slug == spot_slug)) is None
    assert db.scalar(select(SpotContentSource).where(SpotContentSource.url == f"https://example.test/{spot_slug}")) is None

    real = import_spots(path, db=db)
    assert real.ok and real.created == [spot_slug]
    again = import_spots(path, db=db)
    assert again.ok and again.skipped == [spot_slug]

    spot = db.scalar(select(Spot).where(Spot.slug == spot_slug))
    assert spot is not None and spot.status == "draft"
    assert spot.editorial["aliases"] == [f"Import Beach {token}"]
    source = db.scalar(select(SpotContentSource).where(SpotContentSource.spot_id == spot.id))
    assert source is not None
    assert source.field_path == "sports"
    assert source.verification_status == "verified"
    assert source.created_by == "bulk-import"
    assert source.reviewed_by == "bulk-import"

    alias_path = tmp_path / "alias-duplicate.json"
    alias_path.write_text(json.dumps({"spots": [{
        "slug": f"alias-duplicate-{token}",
        "name": f"Import Beach {token}",
        "region_slug": region.slug,
        "lat": 54.401,
        "lon": 10.201,
        "sports": ["wing"],
    }]}), encoding="utf-8")
    alias_result = import_spots(alias_path, db=db)
    assert alias_result.ok
    assert alias_result.created == []
    assert alias_result.skipped == [f"alias-duplicate-{token}"]
    assert alias_result.preview[0]["action"] == "skip_exact_duplicate"

    db.delete(spot)
    db.commit()
    db.delete(region)
    db.commit()
