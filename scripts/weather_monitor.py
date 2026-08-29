"""Evaluate a local monitoring snapshot. No production fetching or writes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.weather.monitoring import evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True, help="Local JSON snapshot fixture")
    args = parser.parse_args()
    result = evaluate(json.loads(args.snapshot.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
