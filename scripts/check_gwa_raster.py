"""Preflight doctor for the mounted GWA raster.

Opens the expected 10 m GWA layer(s) under GWA_RASTER_DIR and reports variable,
CRS, NoData and value range, failing loudly (exit 1) when a file is missing, the
CRS is wrong, or values are implausible (e.g. a 100 m layer or power-density was
mounted instead of the 10 m wind-speed layer). Run this before the producer so a
wrong mount surfaces immediately instead of spot-by-spot gwa_nodata.

Usage:
    python -m scripts.check_gwa_raster
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.forecast.gwa_producer import gwa_raster_doctor


def main() -> None:
    report = gwa_raster_doctor()
    print(json.dumps(report, indent=2, default=str))
    raise SystemExit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
