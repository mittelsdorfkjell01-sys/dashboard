"""Print a machine-readable weather-field operations report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.session import SessionLocal
from app.spatial_fields.doctor import build_weather_field_doctor_report
from app.spatial_fields.storage import configured_field_storage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-public", action="store_true")
    parser.add_argument("--fail-on-alert", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    settings = get_settings()
    with SessionLocal() as db:
        report = build_weather_field_doctor_report(
            db,
            storage=configured_field_storage(),
            settings=settings,
            require_public=args.require_public,
        )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    has_critical = any(
        alert.get("severity") == "critical" for alert in report["alerts"]
    )
    return 2 if args.fail_on_alert and has_critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
