from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.importers.spots import ImportFormatError, import_spots, load_rows, normalize_row
from app.models import Region, Spot


def test_load_json_accepts_spots_envelope(tmp_path):
    path = tmp_path / "spots.json"
    path.write_text(json.dumps({"spots": [{"slug": "one"}]}), encoding="utf-8")
    assert load_rows(path) == [{"slug": "one"}]


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
                "slug": spot_slug,
                "name": f"Import Spot {token}",
                "region_slug": region.slug,
                "lat": 54.4,
                "lon": 10.2,
                "sports": ["wing"],
            }]
        }),
        encoding="utf-8",
    )

    dry = import_spots(path, db=db, dry_run=True)
    assert dry.ok and dry.created == [spot_slug]
    assert db.scalar(select(Spot).where(Spot.slug == spot_slug)) is None

    real = import_spots(path, db=db)
    assert real.ok and real.created == [spot_slug]
    again = import_spots(path, db=db)
    assert again.ok and again.skipped == [spot_slug]

    spot = db.scalar(select(Spot).where(Spot.slug == spot_slug))
    assert spot is not None and spot.status == "draft"
    db.delete(spot)
    db.commit()
    db.delete(region)
    db.commit()
