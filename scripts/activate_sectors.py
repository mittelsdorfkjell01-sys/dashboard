"""Activate candidate sector versions — the WP1-gated enable step.

Two modes:
  # Direct: activate one spot's candidate version.
  python -m scripts.activate_sectors --spot <UUID> --version 2 --reason "..."

  # Gated batch: activate each spot's latest candidate only where the WP1
  # before/after comparison shows a mean-MAE drop >= threshold.
  python -m scripts.activate_sectors --compare <AFTER_RUN> --against <BASELINE_RUN> --min-bias-drop 0.2

The runner never enables sectors; this is the only path that does. On
overcorrection for a model family, lower settings.wind_sector_blend and
re-compare before activating.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.weather.sector_activation import (
    activate_spot_sectors,
    latest_candidate_version,
    spot_bias_improvement,
)

ACTOR = "cli:activate_sectors"


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate candidate sectors (WP1-gated).")
    parser.add_argument("--spot", help="Spot id for direct activation.")
    parser.add_argument("--version", type=int, help="Sector version to activate (direct mode).")
    parser.add_argument("--reason", default=None)
    parser.add_argument("--compare", help="AFTER verification run id (gated batch mode).")
    parser.add_argument("--against", help="BASELINE verification run id (gated batch mode).")
    parser.add_argument("--min-bias-drop", type=float, default=0.0,
                        help="Minimum mean-MAE drop (m/s) required to activate a spot.")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.spot and args.version:
            result = activate_spot_sectors(db, uuid.UUID(args.spot), args.version,
                                           actor=ACTOR, reason=args.reason)
            print(json.dumps(result, indent=2))
            return
        if args.compare and args.against:
            improvements = spot_bias_improvement(db, uuid.UUID(args.compare), uuid.UUID(args.against))
            activated, skipped = [], []
            for spot_id, drop in sorted(improvements.items()):
                if drop < args.min_bias_drop:
                    skipped.append({"spot_id": spot_id, "bias_drop": drop})
                    continue
                version = latest_candidate_version(db, uuid.UUID(spot_id))
                if version is None:
                    skipped.append({"spot_id": spot_id, "bias_drop": drop, "reason": "no_candidate"})
                    continue
                activate_spot_sectors(db, uuid.UUID(spot_id), version,
                                      actor=ACTOR, reason=f"bias_drop={drop}")
                activated.append({"spot_id": spot_id, "version": version, "bias_drop": drop})
            print(json.dumps({"activated": activated, "skipped": skipped,
                              "min_bias_drop": args.min_bias_drop}, indent=2))
            return
    raise SystemExit("use --spot/--version, or --compare/--against [--min-bias-drop]")


if __name__ == "__main__":
    main()
