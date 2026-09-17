"""Drain a bounded batch of durable LiveWind shadow jobs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.weather.live_wind_jobs import run_live_wind_worker


if __name__ == "__main__":
    result = run_live_wind_worker()
    print(json.dumps(result, sort_keys=True))
    if result["failed"] or result["lease_lost"]:
        raise SystemExit(1)
