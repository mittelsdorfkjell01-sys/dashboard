"""Preflight doctor for the mounted WP5 microscale rasters.

Opens the WorldCover (3-degree) and GLO-30 WBM (1-degree) tiles a spot would use
and reports existence, CRS, NoData and code sanity, failing loudly (exit 1) when
a tile is missing/unreadable, the CRS is wrong, the layer is empty, or the codes
do not belong to the expected product. The tiles are per-location, so pass the
lat/lon of a representative spot to validate the exact tiles.

Usage:
    python -m scripts.check_microscale_raster --lat 43.66 --lon -1.44
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.forecast.microscale import microscale_raster_doctor


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the mounted microscale rasters.")
    parser.add_argument("--lat", type=float, help="Probe latitude (a representative spot).")
    parser.add_argument("--lon", type=float, help="Probe longitude (a representative spot).")
    args = parser.parse_args()

    probe = (args.lat, args.lon) if args.lat is not None and args.lon is not None else None
    report = microscale_raster_doctor(probe=probe)
    print(json.dumps(report, indent=2, default=str))
    raise SystemExit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
