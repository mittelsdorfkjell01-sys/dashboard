"""Explicit local dry-run entry point. Production activation is blocked."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import SessionLocal
from app.forecast.refresh_worker import enqueue_due


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args()
    settings = get_settings()
    if settings.app_env == "production" or settings.database_target != "local":
        raise SystemExit("forecast refresh worker is restricted to a local database")
    with SessionLocal() as db:
        print(json.dumps(enqueue_due(db, dry_run=args.dry_run), sort_keys=True))


if __name__ == "__main__":
    main()
