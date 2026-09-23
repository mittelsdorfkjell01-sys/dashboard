"""Run the personalized-scoring backtest against archives or a JSON fixture."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.db.session import SessionLocal
from app.scoring.params import get_params
from app.scoring.personal.backtest import (
    HistoricalHour,
    evaluate_backtest,
    profile_archetypes,
    run_database_backtest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=get_settings().scoring_backtest_default_days)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.fixture:
        raw = json.loads(args.fixture.read_text(encoding="utf-8"))
        rows = [HistoricalHour(**{
            **item, "valid_at": datetime.fromisoformat(item["valid_at"])
        }) for item in raw]
        params = get_params("kitesurf")
        payload = {
            "fixture": str(args.fixture), "k": args.k,
            "data_availability": {
                surface: sum(1 for row in rows if row.surface == surface)
                for surface in ("now", "next_week", "season", "region", "search")
            },
            "metrics": [asdict(row) for row in evaluate_backtest(
                rows, profiles=profile_archetypes(params), params=params, k=args.k
            )],
        }
    else:
        db = SessionLocal()
        try:
            payload = run_database_backtest(db, days=args.days, k=args.k)
        finally:
            db.close()
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
