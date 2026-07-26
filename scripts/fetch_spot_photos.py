"""Fetch real Wikimedia Commons photos for every spot.

For each spot it runs a Commons geosearch near the spot's coordinates, stores
the hits as approved gallery images (via the existing
``create_commons_image_records``), and — when the spot has no hero yet — picks a
landscape hit as the hero (``spot.image`` JSONB). Idempotent: already-stored
Commons photos are skipped, and ``--only-empty`` skips spots that already have a
hero.

Run (uses the DIRECT, non-pooled DB URL):
    DATABASE_URL="postgresql+psycopg://…" python -m scripts.fetch_spot_photos
    …python -m scripts.fetch_spot_photos --only-empty --sleep 1.0 --limit 5
"""
from __future__ import annotations

import argparse
import time

from geoalchemy2.shape import to_shape
from sqlalchemy import select

from app.admin.commons import default_commons_client
from app.community.service import create_commons_image_records
from app.db.session import SessionLocal
from app.models import Spot


def _pick_hero(images: list):
    """Prefer a landscape photo (wide reads best as a hero), else the largest."""
    usable = [i for i in images if i.width and i.height]
    landscape = [i for i in usable if i.width >= i.height]
    pool = landscape or usable or images
    if not pool:
        return None
    return max(pool, key=lambda i: (i.width or 0) * (i.height or 0))


def main() -> None:
    ap = argparse.ArgumentParser(description="Populate spot photos from Wikimedia Commons.")
    ap.add_argument("--only-empty", action="store_true", help="skip spots that already have a hero")
    ap.add_argument("--limit", type=int, default=None, help="process at most N spots")
    ap.add_argument("--sleep", type=float, default=1.0, help="pause between Commons calls (s)")
    ap.add_argument("--dry-run", action="store_true", help="search + report, write nothing")
    args = ap.parse_args()

    client = default_commons_client()
    db = SessionLocal()
    processed = galleries = heroes = no_hits = 0
    try:
        spots = db.scalars(select(Spot).order_by(Spot.name)).all()
        for spot in spots:
            if args.limit is not None and processed >= args.limit:
                break
            if spot.location is None:
                continue
            has_hero = bool(spot.image and spot.image.get("url"))
            if args.only_empty and has_hero:
                continue

            pt = to_shape(spot.location)  # shapely Point(lon, lat)
            try:
                results = client.search(pt.y, pt.x)
            except Exception as exc:  # pragma: no cover - live network
                print(f"[skip] {spot.slug}: search failed: {exc}")
                continue

            processed += 1
            if not results:
                no_hits += 1
                print(f"[--] {spot.slug}: no Commons photos nearby")
                continue

            if args.dry_run:
                print(f"[dry] {spot.slug}: {len(results)} hit(s)")
                continue

            created = create_commons_image_records(db, spot.id, results)
            galleries += len(created)

            hero_now = has_hero
            if not has_hero:
                hero = _pick_hero(created)
                if hero is not None:
                    spot.image = {"url": hero.url, "credit": hero.credit}
                    db.add(spot)
                    heroes += 1
                    hero_now = True
            db.commit()
            print(f"[ok] {spot.slug}: +{len(created)} gallery, hero={'set' if hero_now else 'none'}")
            time.sleep(args.sleep)

        print(
            f"\nDone: {processed} spot(s) processed, {galleries} gallery image(s) added, "
            f"{heroes} hero(es) set, {no_hits} without nearby photos."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
