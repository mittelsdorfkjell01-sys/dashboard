"""Activate candidate sector versions — the WP1-gated enable step.

Two modes:
  # One spot from a gated run (same gate as batch mode).
  python -m scripts.activate_sectors --spot <UUID> --version 2 --run <GATED_RUN>

  # Gated batch: activate each spot's exactly scored candidate only where the WP1
  # within-run shadow comparison (serving baseline vs candidate) shows an MAE drop >=
  # threshold. Produce the run with run_gated_verification_scoring (cron
  # /cron/verification does this), then pass its run id:
  python -m scripts.activate_sectors --run <GATED_RUN> --min-bias-drop 0.2

The automatic producers never enable candidates; this is the gated path. On
overcorrection for a model family, lower settings.wind_sector_blend and
re-score before activating.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.live.cache import default_cache
from app.weather.sector_activation import (
    activate_spot_sectors,
    candidate_gate_results,
    latest_candidate_version,
)

ACTOR = "cli:activate_sectors"


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate candidate sectors (WP1-gated).")
    parser.add_argument("--spot", help="Spot id for direct activation.")
    parser.add_argument("--version", type=int, help="Sector version to activate (direct mode).")
    parser.add_argument("--reason", default=None)
    parser.add_argument("--run", help="Gated verification run id (baseline+candidate) for batch mode.")
    parser.add_argument("--min-bias-drop", type=float, default=0.0,
                        help="Minimum mean-MAE drop (m/s) required to activate a spot.")
    args = parser.parse_args()

    with SessionLocal() as db:
        cache = default_cache()
        if args.spot or args.version:
            if not (args.spot and args.version and args.run):
                raise SystemExit(
                    "direct spot activation requires --spot, --version and --run"
                )
            result = activate_spot_sectors(
                db,
                uuid.UUID(args.spot),
                args.version,
                actor=ACTOR,
                gate_run_id=uuid.UUID(args.run),
                min_bias_drop=args.min_bias_drop,
                reason=args.reason,
                cache=cache,
            )
            print(json.dumps(result, indent=2))
            return
        if args.run:
            gate_results = candidate_gate_results(db, uuid.UUID(args.run))
            activated, skipped = [], []
            for spot_id, gate in sorted(gate_results.items()):
                drop = float(gate["mae_drop"])
                version = int(gate["version"])
                if drop <= 0 or drop < args.min_bias_drop:
                    skipped.append({
                        "spot_id": spot_id,
                        "version": version,
                        "bias_drop": drop,
                        "reason": (
                            "mae_drop_not_positive"
                            if drop <= 0
                            else "mae_drop_below_threshold"
                        ),
                    })
                    continue
                current = latest_candidate_version(db, uuid.UUID(spot_id))
                if current != version:
                    skipped.append({
                        "spot_id": spot_id,
                        "version": version,
                        "bias_drop": drop,
                        "reason": "scored_candidate_is_no_longer_current",
                    })
                    continue
                activate_spot_sectors(
                    db,
                    uuid.UUID(spot_id),
                    version,
                    actor=ACTOR,
                    gate_run_id=uuid.UUID(args.run),
                    min_bias_drop=args.min_bias_drop,
                    reason=f"bias_drop={drop}",
                    cache=cache,
                )
                activated.append({"spot_id": spot_id, "version": version, "bias_drop": drop})
            print(json.dumps({"activated": activated, "skipped": skipped,
                              "min_bias_drop": args.min_bias_drop}, indent=2))
            return
    raise SystemExit(
        "use --spot/--version/--run, or --run [--min-bias-drop]"
    )


if __name__ == "__main__":
    main()
