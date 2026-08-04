"""Idempotent seed command.

Run with:  python -m app.seed.seed

Inserts the regions and spots from ``data.py``. Existing rows (matched by slug)
are left untouched, so the command is safe to re-run. The CLI additionally loads
the researched European draft batch (``data_europe.py``); ``seed(db)`` without the
flag stays on the small core catalogue so tests remain small and deterministic.
"""

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Region, Spot
from app.seed.data import REGIONS, SPOTS


def _point(lon_lat: tuple[float, float]):
    lon, lat = lon_lat
    return from_shape(Point(lon, lat), srid=4326)


def _polygon(ring: list[tuple[float, float]]):
    return from_shape(Polygon(ring), srid=4326)


def _as_list(value) -> list[str]:
    """Coerce a seed scalar (or None/list) into a multi-select array column."""
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def seed(db: Session, *, include_europe: bool = False) -> dict[str, int]:
    """Seed regions, spots, scoring_params and required_fields. Counts of new rows.

    ``include_europe`` also loads the researched European draft batch
    (``app/seed/data_europe.py``). Off by default so the test catalogue stays
    small; the seed CLI turns it on.
    """
    from app.admin.readiness import seed_required_fields
    from app.scoring.params import seed_scoring_params

    regions = list(REGIONS)
    spots = list(SPOTS)
    if include_europe:
        from app.seed.data_europe import REGIONS as EU_REGIONS, SPOTS as EU_SPOTS

        regions = regions + EU_REGIONS
        spots = spots + EU_SPOTS

    created = {"regions": 0, "spots": 0, "scoring_params": 0, "required_fields": 0}

    region_by_slug: dict[str, Region] = {}
    for r in regions:
        existing = db.scalar(select(Region).where(Region.slug == r["slug"]))
        if existing is not None:
            region_by_slug[r["slug"]] = existing
            continue
        region = Region(
            slug=r["slug"],
            name=r["name"],
            country=r["country"],
            center=_point(r["center"]),
            bounds=_polygon(r["bounds"]),
            description=r["description"],
            season=r["season"],
            defaults=r["defaults"],
            image=r["image"],
        )
        db.add(region)
        region_by_slug[r["slug"]] = region
        created["regions"] += 1

    db.flush()  # assign region ids before linking spots

    for s in spots:
        existing = db.scalar(select(Spot).where(Spot.slug == s["slug"]))
        if existing is not None:
            continue
        region = region_by_slug[s["region_slug"]]
        # water_type / level / water_character are multi-select arrays now; the
        # seed data still carries a single scalar each, so wrap into a list.
        spot = Spot(
            slug=s["slug"],
            name=s["name"],
            region_id=region.id,
            location=_point(s["location"]),
            sports=s["sports"],
            water_type=_as_list(s.get("water_type")),
            bottom_type=s["bottom_type"],
            level=_as_list(s.get("level")),
            water_character=_as_list(s.get("water_character")),
            style=s.get("style", []),
            facilities=s.get("facilities"),
            status=s["status"],
            facing=s.get("facing"),
            confidence=s.get("confidence"),
            editorial=s.get("editorial"),
            model_pref=region.defaults.get("model_pref") if region.defaults else None,
        )
        db.add(spot)
        created["spots"] += 1

    db.commit()
    created["scoring_params"] = seed_scoring_params(db)
    created["required_fields"] = seed_required_fields(db)
    return created


def main() -> None:
    db = SessionLocal()
    try:
        created = seed(db, include_europe=True)
    finally:
        db.close()
    print(
        f"Seed complete: {created['regions']} region(s), "
        f"{created['spots']} spot(s), "
        f"{created['scoring_params']} scoring_params row(s) inserted."
    )


if __name__ == "__main__":
    main()
