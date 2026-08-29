"""Find or enqueue local media files that are no longer referenced by the DB.

The command is dry-run by default. Objects newer than the grace period are
left alone so it can safely overlap an in-flight upload. ``--delete`` retains
its historical name but now uses the race-safe persistent deletion queue.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import SessionLocal
from app.media.gc import schedule_media_gc
from app.media.lifecycle import ACTIVE_ROW_STATUSES
from app.media.storage import canonical_image_url, responsive_variant_urls
from app.models import Region, Spot, SpotImage


def _local_key(url: str | None, prefix: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    marker = f"{prefix.rstrip('/')}/"
    if parsed.scheme or parsed.netloc or not parsed.path.startswith(marker):
        return None
    return parsed.path[len(marker):].replace("/", os.sep)


def referenced_keys(prefix: str) -> set[str]:
    keys: set[str] = set()

    def add_image_set(url: str | None) -> None:
        for candidate in [url, *responsive_variant_urls(url)]:
            if key := _local_key(candidate, prefix):
                keys.add(key)

    with SessionLocal() as db:
        for image in db.scalars(select(Spot.image)).all():
            url = image.get("url") if isinstance(image, dict) else None
            add_image_set(url)
        for image in db.scalars(select(Region.image)).all():
            url = image.get("url") if isinstance(image, dict) else None
            add_image_set(url)
        for url in db.scalars(
            select(SpotImage.url).where(SpotImage.status.in_(ACTIVE_ROW_STATUSES))
        ).all():
            add_image_set(url)
    return keys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delete",
        action="store_true",
        help="enqueue orphaned files for locked, retryable deletion",
    )
    parser.add_argument("--grace-hours", type=float, default=24.0)
    args = parser.parse_args()

    settings = get_settings()
    if settings.media_backend != "local":
        raise SystemExit("cleanup_media only scans the local media backend")

    root = Path(settings.media_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    referenced = referenced_keys(settings.media_url_prefix)
    cutoff = time.time() - max(0.0, args.grace_hours) * 3600
    orphans = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not path.name.startswith(".upload-")
        and str(path.relative_to(root)) not in referenced
        and path.stat().st_mtime <= cutoff
    ]
    canonical_urls = {
        canonical_image_url(
            f"{settings.media_url_prefix.rstrip('/')}/"
            f"{path.relative_to(root).as_posix()}"
        )
        for path in orphans
    }
    for path in orphans:
        print(f"{'QUEUE' if args.delete else 'ORPHAN'} {path}")
    queued = 0
    if args.delete:
        with SessionLocal() as db:
            for url in sorted(canonical_urls):
                queued += int(
                    schedule_media_gc(
                        db,
                        url,
                        delete_set=True,
                        grace_hours=max(1, round(args.grace_hours)),
                    )
                )
    print(
        f"{len(orphans)} orphaned file(s) in {len(canonical_urls)} set(s); "
        f"queued={queued}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
