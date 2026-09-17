"""Bounded, resumable internal LiveWind holdout collection and verification."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from app.config import get_settings
from app.db.session import SessionLocal
from app.weather.exact_run import ExactRunAssetCache, ExactRunLoader
from app.weather.live_wind_holdouts import (
    build_live_wind_holdout_cases, holdout_status, verify_persisted_holdouts,
)
from app.weather.live_wind_verification import LiveWindVerificationPolicy
from scripts.exact_run_preflight import run_preflight


def _time(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("time_must_include_utc_offset")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("status", "build", "verify"))
    parser.add_argument("--candidate-version")
    parser.add_argument("--training-manifest", type=Path)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()
    cfg = get_settings()
    candidate = args.candidate_version or cfg.live_wind_candidate_version
    if cfg.live_wind_rollout_stage != "shadow":
        raise SystemExit("holdout_worker_requires_shadow_stage")
    proof = json.loads(args.training_manifest.read_text(encoding="utf-8")) if args.training_manifest else None
    if args.mode != "status":
        preflight = run_preflight()
        if preflight["status"] != "ready":
            print(json.dumps({"status": "failed", "stage": "preflight", "errors": preflight["errors"]}))
            raise SystemExit(1)
    with SessionLocal() as db:
        if args.mode == "status":
            result = holdout_status(db, candidate_version=candidate)
        elif args.mode == "build":
            loader = ExactRunLoader(ExactRunAssetCache(
                cfg.live_wind_exact_run_cache_dir,
                require_persistent=cfg.app_env == "production" or cfg.live_wind_canary_mode,
                expected_id=cfg.live_wind_exact_run_cache_id,
                minimum_free_bytes=cfg.live_wind_exact_run_min_free_bytes,
            ))
            result = build_live_wind_holdout_cases(
                db, loader, candidate_version=candidate, training_proof=proof,
                since=_time(args.since), until=_time(args.until), limit=args.limit,
                dry_run=args.dry_run, recompute=args.recompute,
            )
        else:
            result = verify_persisted_holdouts(
                db, candidate_version=candidate, training_proof=proof,
                policy=LiveWindVerificationPolicy(
                    minimum_samples=cfg.live_wind_verification_min_samples,
                    minimum_days=cfg.live_wind_verification_min_days,
                    minimum_stations=cfg.live_wind_verification_min_stations,
                    minimum_uv_mae_drop_ms=cfg.live_wind_verification_min_uv_mae_drop_ms,
                    minimum_wind_sectors=cfg.live_wind_readiness_min_wind_sectors,
                    maximum_fallback_rate=cfg.live_wind_readiness_max_fallback_rate,
                    subgroup_policy_version=cfg.live_wind_verification_subgroup_policy_version,
                    maximum_subgroup_regression_ms=cfg.live_wind_verification_max_subgroup_regression_ms,
                ), dry_run=args.dry_run,
            )
    print(json.dumps(result, sort_keys=True, default=str))
    if result.get("errors") or result.get("status") in {"failed", "gate_blocked"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
