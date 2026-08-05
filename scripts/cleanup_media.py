"""Find or delete local media files that are no longer referenced by the DB.

The command is dry-run by default. Objects newer than the grace period are
left alone so it can safely overlap an in-flight upload.
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
    with SessionLocal() as db:
        for image in db.scalars(select(Spot.image)).all():
            url = image.get("url") if isinstance(image, dict) else None
            if key := _local_key(url, prefix):
                keys.add(key)
        for image in db.scalars(select(Region.image)).all():
            url = image.get("url") if isinstance(image, dict) else None
            if key := _local_key(url, prefix):
                keys.add(key)
        for url in db.scalars(select(SpotImage.url)).all():
            if key := _local_key(url, prefix):
                keys.add(key)
    return keys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="delete orphaned files")
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
    for path in orphans:
        print(f"{'DELETE' if args.delete else 'ORPHAN'} {path}")
        if args.delete:
            path.unlink(missing_ok=True)
    print(f"{len(orphans)} orphaned file(s); delete={args.delete}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
