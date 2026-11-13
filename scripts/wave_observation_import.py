"""Import normalized, freely sourced Copernicus wave observations from CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.weather.wave_verification import import_wave_observation_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--provider", default="copernicus-marine")
    parser.add_argument("--region-code", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = args.path.read_bytes()
    source_sha256 = hashlib.sha256(payload).hexdigest()
    with args.path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with SessionLocal() as db:
        result = import_wave_observation_rows(
            db,
            rows,
            provider_key=args.provider,
            region_code=args.region_code,
            source_revision=args.source_revision,
            source_file=args.path.name,
            source_sha256=source_sha256,
            dry_run=args.dry_run,
        )
    print(json.dumps({**result, "source_sha256": source_sha256}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
