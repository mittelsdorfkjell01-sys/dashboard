"""Validate and optionally import reviewed gear research.

Examples:
  python -m scripts.import_gear_staging research/gear/staging/pilot.json
  python -m scripts.import_gear_staging research/gear/staging/pilot.json --apply
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.gear.importer import GearImportError, import_staging_records, load_staging_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--apply", action="store_true", help="commit changes; default is validation/dry-run")
    args = parser.parse_args(argv)
    try:
        records = load_staging_file(args.file.resolve())
        with SessionLocal() as db:
            summary = import_staging_records(db, records)
            if args.apply:
                db.commit()
            else:
                db.rollback()
    except GearImportError as exc:
        parser.error(str(exc))
    print(json.dumps({
        "mode": "applied" if args.apply else "dry-run",
        "records": summary.records,
        "created": summary.created,
        "skippedClaims": summary.skipped_claims,
        "skippedRelations": summary.skipped_relations,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
