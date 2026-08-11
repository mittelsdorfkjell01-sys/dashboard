"""Fail when the latest stored hero or any stored gallery blob is orphaned."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Spot, SpotImage

BLOB_API = "https://blob.vercel-storage.com"
PATH_RE = re.compile(r"^spots/([0-9a-f-]{36})/(hero|gallery)-[^/]+\.(?:avif|webp|jpe?g|png)$")


def _blobs(token: str) -> list[dict]:
    items: list[dict] = []
    cursor = None
    while True:
        query = {"limit": "1000", "prefix": "spots/"}
        if cursor:
            query["cursor"] = cursor
        request = urllib.request.Request(
            f"{BLOB_API}?{urllib.parse.urlencode(query)}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            page = json.load(response)
        items.extend(page.get("blobs", []))
        if not page.get("hasMore") or not page.get("cursor"):
            return items
        cursor = page["cursor"]


def main() -> None:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    if not token:
        raise SystemExit("BLOB_READ_WRITE_TOKEN is required")
    latest_heroes: dict[UUID, dict] = {}
    gallery_urls: dict[UUID, list[str]] = {}
    for blob in _blobs(token):
        match = PATH_RE.match(blob.get("pathname", ""))
        if not match:
            continue
        spot_id, role = UUID(match.group(1)), match.group(2)
        if role == "gallery":
            gallery_urls.setdefault(spot_id, []).append(blob["url"])
            continue
        previous = latest_heroes.get(spot_id)
        uploaded = datetime.fromisoformat(blob["uploadedAt"].replace("Z", "+00:00"))
        if previous is None or uploaded > previous["uploaded"]:
            latest_heroes[spot_id] = {"url": blob["url"], "uploaded": uploaded}

    errors: list[str] = []
    with SessionLocal() as db:
        spots = {spot.id: spot for spot in db.scalars(select(Spot)).all()}
        recorded_gallery = set(db.scalars(select(SpotImage.url)).all())
        for spot_id, blob in latest_heroes.items():
            spot = spots.get(spot_id)
            if spot is None:
                errors.append(f"blob references missing spot {spot_id}")
            elif (spot.image or {}).get("url") != blob["url"]:
                errors.append(f"latest hero is orphaned for {spot.slug}: {blob['url']}")
        for spot_id, urls in gallery_urls.items():
            if spot_id not in spots:
                errors.append(f"gallery blob references missing spot {spot_id}")
            for url in urls:
                if url not in recorded_gallery:
                    errors.append(f"gallery blob is orphaned for {spot_id}: {url}")

    if errors:
        print("media integrity FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"media integrity OK: {len(latest_heroes)} latest heroes, {sum(map(len, gallery_urls.values()))} gallery blobs")


if __name__ == "__main__":
    main()
