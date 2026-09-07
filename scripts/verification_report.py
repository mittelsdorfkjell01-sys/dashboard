"""WP1 validation harness runner: score the raw forecast against station wind.

Single command to produce a reproducible bias/MAE/RMSE report per lead-time
bucket and 30-degree direction sector, so a change can be measured before and
after. Station wind is only compared here; it never enters a forecast value.

Usage:
    python -m scripts.verification_report --persist
    python -m scripts.verification_report --spot <SPOT_UUID> --no-persist
    python -m scripts.verification_report --compare <RUN_ID> --against <RUN_ID>
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ForecastVerificationScore
from app.weather.verification import eligible_spot_ids, run_verification_scoring


def _score_map(db, run_id: uuid.UUID, variant: str) -> dict[tuple, ForecastVerificationScore]:
    rows = db.scalars(
        select(ForecastVerificationScore).where(
            ForecastVerificationScore.run_id == run_id,
            ForecastVerificationScore.variant == variant,
        )
    ).all()
    return {(str(r.spot_id), r.model_id, r.lead_bucket, r.direction_sector): r for r in rows}


def _compare(db, run_id: uuid.UUID, against: uuid.UUID, variant: str) -> dict:
    current = _score_map(db, run_id, variant)
    baseline = _score_map(db, against, variant)
    deltas = []
    for key, row in sorted(current.items()):
        base = baseline.get(key)
        if base is None:
            continue
        deltas.append({
            "spot_id": key[0], "model_id": key[1], "lead_bucket": key[2], "direction_sector": key[3],
            "bias_ms": [base.bias_ms, row.bias_ms, round(row.bias_ms - base.bias_ms, 3)],
            "mae_ms": [base.mae_ms, row.mae_ms, round(row.mae_ms - base.mae_ms, 3)],
            "rmse_ms": [base.rmse_ms, row.rmse_ms, round(row.rmse_ms - base.rmse_ms, 3)],
        })
    improved = sum(1 for d in deltas if d["mae_ms"][2] < 0)
    worsened = sum(1 for d in deltas if d["mae_ms"][2] > 0)
    return {"compared_cohorts": len(deltas), "mae_improved": improved,
            "mae_worsened": worsened, "deltas": deltas}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or diff the forecast verification harness.")
    parser.add_argument("--spot", action="append", default=None, help="Limit to one or more spot ids.")
    parser.add_argument("--lookback-days", type=int, default=45)
    parser.add_argument("--tolerance-min", type=int, default=20, help="Forecast/observation match window.")
    parser.add_argument("--variant", default="raw")
    parser.add_argument("--persist", dest="persist", action="store_true", default=True)
    parser.add_argument("--no-persist", dest="persist", action="store_false")
    parser.add_argument("--compare", default=None, help="Run id to report/diff.")
    parser.add_argument("--against", default=None, help="Baseline run id for --compare.")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.compare:
            if not args.against:
                raise SystemExit("--compare requires --against <RUN_ID>")
            report = _compare(db, uuid.UUID(args.compare), uuid.UUID(args.against), args.variant)
            print(json.dumps(report, indent=2))
            return
        spot_ids = [uuid.UUID(value) for value in args.spot] if args.spot else None
        if spot_ids is None:
            eligible = eligible_spot_ids(db)
            print(json.dumps({"eligible_spots": len(eligible)}))
        summary = run_verification_scoring(
            db, spot_ids=spot_ids, lookback_days=args.lookback_days,
            tolerance_s=max(60, args.tolerance_min * 60), variant=args.variant, persist=args.persist,
        )
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
