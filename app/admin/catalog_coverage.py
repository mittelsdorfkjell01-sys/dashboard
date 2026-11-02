"""Editorial catalogue coverage matrix for controlled expansion batches."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.admin.constants import SPORTS
from app.models import Region, Spot


PUBLICATION_STATES = ("draft", "published", "archived")
CONTENT_STATES = ("unreviewed", "in_review", "verified", "review_due", "conflict")
CLASSIFICATIONS = ("world_class", "worth_trip", "worth_checking_out", "unranked")


def _counts(keys: tuple[str, ...]) -> dict[str, int]:
    return {key: 0 for key in keys}


def build_coverage_matrix(regions: list[Any], spots: list[Any]) -> dict[str, Any]:
    """Build Region × Sport rows without treating multi-sport spots as unique totals."""
    by_region: dict[Any, list[Any]] = {region.id: [] for region in regions}
    unassigned: list[Any] = []
    for spot in spots:
        bucket = by_region.get(getattr(spot, "region_id", None))
        (bucket if bucket is not None else unassigned).append(spot)

    rows: list[dict[str, Any]] = []
    single_spot_regions = 0
    for region in sorted(regions, key=lambda item: item.name.casefold()):
        region_spots = by_region[region.id]
        if len(region_spots) == 1:
            single_spot_regions += 1
        for sport in SPORTS:
            matches = [spot for spot in region_spots if sport in (spot.sports or [])]
            publication = _counts(PUBLICATION_STATES)
            content = _counts(CONTENT_STATES)
            classification = _counts(CLASSIFICATIONS)
            for spot in matches:
                publication[getattr(spot, "status", "draft")] += 1
                content[getattr(spot, "content_status", "unreviewed")] += 1
                classification[
                    getattr(spot, "editorial_classification", None) or "unranked"
                ] += 1
            rows.append({
                "region_id": str(region.id),
                "region_name": region.name,
                "country": getattr(region, "country", None),
                "region_spot_count": len(region_spots),
                "sport": sport,
                "total": len(matches),
                "publication": publication,
                "content": content,
                "classification": classification,
            })

    publication_total = Counter(getattr(spot, "status", "draft") for spot in spots)
    content_total = Counter(getattr(spot, "content_status", "unreviewed") for spot in spots)
    return {
        "summary": {
            "spots": len(spots),
            "regions": len(regions),
            "unassigned": len(unassigned),
            "single_spot_regions": single_spot_regions,
            "publication": {key: publication_total.get(key, 0) for key in PUBLICATION_STATES},
            "content": {key: content_total.get(key, 0) for key in CONTENT_STATES},
        },
        "rows": rows,
    }


def catalogue_coverage(db: Session) -> dict[str, Any]:
    regions = list(db.scalars(select(Region).order_by(Region.name)).all())
    spots = list(db.scalars(select(Spot).options(selectinload(Spot.content_sources))).all())
    return build_coverage_matrix(regions, spots)
