"""Preview or apply compressed archival of terminal image moderation rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import SessionLocal
from app.media.archive import archive_retired_images


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true", help="write archives and remove source rows"
    )
    parser.add_argument(
        "--days", type=int, default=settings.image_archive_retention_days
    )
    parser.add_argument("--limit", type=int, default=settings.image_archive_batch_size)
    args = parser.parse_args()
    with SessionLocal() as db:
        result = archive_retired_images(
            db,
            retention_days=args.days,
            limit=args.limit,
            dry_run=not args.apply,
        )
    result["applied"] = args.apply
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
