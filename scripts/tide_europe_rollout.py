"""Preflight and bounded bootstrap for the private Europe FES worker."""

from __future__ import annotations

import argparse
import json

from app.config import get_settings
from app.db.session import SessionLocal
from app.tides.preflight import tide_asset_preflight
from app.tides.rollout import bootstrap_europe_profiles
from app.tides.service import monitoring


def main() -> None:
    parser = argparse.ArgumentParser(description="Operate the Europe FES tide rollout")
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--verify-checksums", action="store_true")
    bootstrap = commands.add_parser("bootstrap")
    bootstrap.add_argument("--apply", action="store_true")
    bootstrap.add_argument("--limit", type=int, default=25)
    commands.add_parser("status")
    args = parser.parse_args()

    if args.command == "preflight":
        result = tide_asset_preflight(
            get_settings(),
            verify_checksums=args.verify_checksums,
            load_pyfes=True,
        )
    else:
        db = SessionLocal()
        try:
            if args.command == "bootstrap":
                result = bootstrap_europe_profiles(
                    db,
                    apply=args.apply,
                    limit=max(1, args.limit),
                )
            else:
                result = monitoring(db=db)
        finally:
            db.close()

    print(json.dumps(result, default=str, indent=2, sort_keys=True))
    if args.command == "preflight" and not result["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
