"""Process one queued Phase-4 collection job."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.weather.shadow_jobs import run_next_shadow_cycle


if __name__ == "__main__":
    result = run_next_shadow_cycle()
    print(json.dumps(result))
    if result["status"] == "failed":
        raise SystemExit(1)
