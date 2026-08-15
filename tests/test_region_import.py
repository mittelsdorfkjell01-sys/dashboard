from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from app.importers.regions import import_regions, normalize_row
from app.models import Region


def test_normalize_review_row_maps_country_and_derived_centre():
    row = normalize_row(
        {
            "region_slug": "test-kueste",
            "region": "Test Küste",
            "country": "Deutschland",
            "spot_count": 2,
            "status": "DB-Abgleich erforderlich",
        },
        1,
        {"test-kueste": (54.5, 10.2, [10.0, 54.3, 10.4, 54.7])},
    )
    assert row["slug"] == "test-kueste"
    assert row["country"] == "DE"
    assert (row["lat"], row["lon"]) == (54.5, 10.2)


def test_region_import_is_dry_run_safe_and_idempotent(db, tmp_path):
    token = uuid.uuid4().hex[:10]
    slug = f"region-import-{token}"
    path = tmp_path / "regions.json"
    path.write_text(
        json.dumps({"regions": [{"slug": slug, "name": f"Region Import {token}", "country": "DE", "lat": 54.4, "lon": 10.2}]}),
        encoding="utf-8",
    )

    dry = import_regions(path, db=db, dry_run=True)
    assert dry.ok and dry.created == [slug]
    assert db.scalar(select(Region).where(Region.slug == slug)) is None

    real = import_regions(path, db=db)
    assert real.ok and real.created == [slug]
    again = import_regions(path, db=db)
    assert again.ok and again.skipped == [slug]

    region = db.scalar(select(Region).where(Region.slug == slug))
    assert region is not None and region.status == "draft"
    db.delete(region)
    db.commit()
