"""Create and persist a deterministic wave verification artefact."""

from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
import hashlib
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.models.wave_verification import WaveVerificationRun, WaveVerificationScore
from app.weather.wave_verification import POLICY_VERSION, evaluate_wave_verification


def _day(value: str, *, end: bool) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.combine(
        parsed,
        time.max if end else time.min,
        tzinfo=timezone.utc,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="UTC date, YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="UTC date, YYYY-MM-DD")
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tolerance-minutes", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    start = _day(args.start, end=False)
    end = _day(args.end, end=True)
    with SessionLocal() as db:
        artifact = evaluate_wave_verification(
            db,
            start=start,
            end=end,
            model_keys=args.models,
            tolerance_minutes=args.tolerance_minutes,
        )
        summary = {
            key: artifact[key]
            for key in (
                "forecast_samples",
                "matched_values",
                "score_groups",
                "skipped",
                "coverage",
            )
        }
        payload = json.dumps(
            artifact, sort_keys=True, indent=2, ensure_ascii=False
        ).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "artifact_sha256": digest,
                        "summary": summary,
                    },
                    sort_keys=True,
                )
            )
            return 0

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
        run = WaveVerificationRun(
            status="completed",
            dataset_start=start.date(),
            dataset_end=end.date(),
            policy_version=POLICY_VERSION,
            configuration=artifact["configuration"],
            artifact_uri=str(args.output),
            artifact_sha256=digest,
            summary=summary,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()
        for row in artifact["scores"]:
            db.add(
                WaveVerificationScore(
                    verification_run_id=run.id,
                    model_key=row["model_key"],
                    parameter=row["parameter"],
                    lead_bucket=row["lead_bucket"],
                    region_code=row["region_code"],
                    location_class=row["location_class"],
                    sample_count=row["sample_count"],
                    distinct_days=row["distinct_days"],
                    bias=row["bias"],
                    mae=row["mae"],
                    rmse=row["rmse"],
                    correlation=row["correlation"],
                    scatter_index=row["scatter_index"],
                    within_tolerance_ratio=row["within_tolerance_ratio"],
                    metrics=row["metrics"],
                )
            )
        db.commit()
        print(
            json.dumps(
                {
                    "verification_run_id": str(run.id),
                    "artifact": str(args.output),
                    "artifact_sha256": digest,
                    "score_groups": artifact["score_groups"],
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
