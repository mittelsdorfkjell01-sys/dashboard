"""Bounded local pilot catalogue, import, review and status commands.

Mutations require --apply and a disposable local *_test database. Review actions
also require an existing active admin password entered interactively.
"""

import argparse
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
import sys
import uuid

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.service import authenticate
from app.config import get_settings
from app.db.schema import EXPECTED_DB_REVISION
from app.db.session import SessionLocal
from app.models import (
    WeatherStation, WeatherStationApprovalAudit, WeatherStationDossier,
    WeatherStationGroupDecision, WeatherStationProviderCursor,
)
from app.weather.observation_worker import run_observation_import
from app.weather.station_catalog_job import run_station_catalog_refresh
from app.weather.station_approval import approval_reasons, decide_station_scope
from app.weather.station_identity import possible_duplicate_candidates
from app.weather.station_qualification import (
    QualificationPolicy, decide_group, persist_dossier, propose_group_candidates,
    review_epoch,
)
from app.weather.station_report import station_report

DEFAULT_BOUNDS = (53.0, 56.5, 7.5, 12.5)  # south, north, west, east
MUTATIONS = {"catalog", "cycle", "import", "backfill", "dossier", "group-review",
             "epoch-review", "approve", "revoke", "pause", "resume"}


def _station(db, station_id):
    if not station_id:
        raise SystemExit("--station-id required")
    try:
        station = db.get(WeatherStation, uuid.UUID(station_id))
    except ValueError as exc:
        raise SystemExit("invalid station UUID") from exc
    if station is None:
        raise SystemExit("station not found")
    return station


def _admin(db, email):
    if not email:
        raise SystemExit("--actor admin email required")
    user = authenticate(db, email, getpass.getpass("Admin password: "))
    if user is None or user.role != "admin":
        raise SystemExit("authenticated active admin required")
    return user


def _policy(path):
    if not path:
        return QualificationPolicy()
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    return QualificationPolicy(**values)


def _catalog(db, args, *, dry_run):
    return run_station_catalog_refresh(
        db,
        providers=tuple(args.providers),
        dry_run=dry_run,
        force=True,
        bounds=tuple(args.bounds),
        spot_limit=args.limit,
        candidate_limit=args.candidate_limit,
        max_km=args.max_km,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("catalog", "cycle", "import", "backfill", "status",
                                            "dossier", "dossier-show", "groups", "group-review",
                                            "epoch-review", "approval-preview", "approve", "revoke",
                                            "audit", "readiness", "pause", "resume"))
    parser.add_argument("--providers", nargs="+", choices=("dwd", "dmi"), default=("dwd", "dmi"))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--max-km", type=float, default=250.0)
    parser.add_argument("--bounds", nargs=4, type=float, default=DEFAULT_BOUNDS,
                        metavar=("SOUTH", "NORTH", "WEST", "EAST"))
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--station-id")
    parser.add_argument("--scope", choices=("monitoring", "residual_source", "holdout_input", "holdout_target"))
    parser.add_argument("--group-type", choices=("physical", "sensor", "correlation"))
    parser.add_argument("--group-key")
    parser.add_argument("--group-status", choices=("confirmed", "rejected"))
    parser.add_argument("--evidence-file")
    parser.add_argument("--reason")
    parser.add_argument("--actor")
    parser.add_argument("--policy-file")
    parser.add_argument("--dossier-hash")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if settings.app_env == "production" or settings.database_target != "local":
        raise SystemExit("local database only; production writes forbidden")
    if args.apply and (args.dry_run or not settings.database_url.rsplit("/", 1)[-1].endswith("_test")):
        raise SystemExit("--apply requires a disposable local *_test database")
    if args.command in MUTATIONS and not (args.dry_run or args.apply):
        raise SystemExit("choose --dry-run or --apply")
    if args.limit < 1 or args.candidate_limit < 1 or args.window_days < 1 or args.max_km <= 0:
        raise SystemExit("positive limits required")
    with SessionLocal() as db:
        from sqlalchemy import text
        head = db.scalar(text("SELECT version_num FROM alembic_version"))
        if head != EXPECTED_DB_REVISION:
            raise SystemExit(
                f"database migration head {head!r} is not "
                f"{EXPECTED_DB_REVISION}"
            )
        if args.command in {"catalog", "cycle"}:
            report = {"catalog": _catalog(db, args, dry_run=not args.apply)}
            if args.command == "cycle":
                report["observations"] = run_observation_import(
                    db, providers=args.providers, limit=args.limit, dry_run=not args.apply)
        elif args.command in {"import", "backfill"}:
            report = run_observation_import(
                db, providers=args.providers, limit=args.limit, dry_run=not args.apply,
                capture_mode="historical_backfill" if args.command == "backfill" else "operational")
        elif args.command in {"status", "readiness"}:
            report = station_report(db)
        elif args.command in {"pause", "resume"}:
            report = {"providers": args.providers, "paused": args.command == "pause", "dry_run": not args.apply}
            if args.apply:
                for provider in args.providers:
                    cursor = db.get(WeatherStationProviderCursor, provider) or WeatherStationProviderCursor(provider=provider)
                    cursor.paused = args.command == "pause"
                    db.add(cursor)
                db.commit()
        elif args.command == "groups":
            stations = db.scalars(select(WeatherStation).order_by(WeatherStation.provider,
                                                                   WeatherStation.provider_station_id)).all()
            report = {"candidates": [{"left": str(stations[a].id), "right": str(stations[b].id),
                                       "reasons": list(reasons)}
                                      for a, b, reasons in possible_duplicate_candidates(stations)],
                      "persistence": propose_group_candidates(db, stations, dry_run=not args.apply)}
        else:
            station = _station(db, args.station_id)
            if args.command == "dossier":
                payload, dossier_hash = persist_dossier(db, station, end=datetime.now(timezone.utc),
                                                        window_days=args.window_days, dry_run=not args.apply)
                report = {"dossier_hash": dossier_hash, "payload": payload, "dry_run": not args.apply}
            elif args.command == "dossier-show":
                dossier = db.scalar(select(WeatherStationDossier).where(
                    WeatherStationDossier.epoch_id == station.current_epoch_id
                ).order_by(WeatherStationDossier.generated_at.desc(), WeatherStationDossier.id.desc()))
                report = {"dossier_hash": dossier.dossier_hash, "payload": dossier.payload} if dossier else {"missing": True}
            elif args.command == "approval-preview":
                report = {"scope": args.scope, "blockers": approval_reasons(
                    db, station, scope=args.scope or "", policy=_policy(args.policy_file))}
            elif args.command in {"approve", "revoke"}:
                if not args.scope or not args.reason:
                    raise SystemExit("--scope and --reason required")
                report = {"scope": args.scope, "approved": args.command == "approve", "dry_run": not args.apply}
                if args.apply:
                    reviewer = _admin(db, args.actor)
                    decide_station_scope(db, station, scope=args.scope, approved=args.command == "approve",
                                         actor=reviewer.email, reason=args.reason, reviewer=reviewer,
                                         policy=_policy(args.policy_file), expected_dossier_hash=args.dossier_hash)
                    db.commit()
                else:
                    report["blockers"] = approval_reasons(db, station, scope=args.scope,
                                                          policy=_policy(args.policy_file))
            elif args.command == "group-review":
                if not all((args.group_type, args.group_key, args.group_status, args.reason, args.evidence_file)):
                    raise SystemExit("group decision requires type, key, status, reason and evidence file")
                evidence = json.loads(Path(args.evidence_file).read_text(encoding="utf-8"))
                report = {"group": args.group_key, "status": args.group_status, "dry_run": not args.apply}
                if args.apply:
                    decide_group(db, station, group_type=args.group_type, group_key=args.group_key,
                                 status=args.group_status, reviewer=_admin(db, args.actor),
                                 reason=args.reason, evidence=evidence)
                    db.commit()
            elif args.command == "epoch-review":
                report = {"epoch_id": str(station.current_epoch_id), "dry_run": not args.apply}
                if args.apply:
                    review_epoch(db, station, reviewer=_admin(db, args.actor), reason=args.reason or "")
                    db.commit()
            elif args.command == "audit":
                decisions = db.scalars(select(WeatherStationApprovalAudit).where(
                    WeatherStationApprovalAudit.station_id == station.id
                ).order_by(WeatherStationApprovalAudit.decided_at, WeatherStationApprovalAudit.id)).all()
                groups = db.scalars(select(WeatherStationGroupDecision).where(
                    WeatherStationGroupDecision.epoch_id == station.current_epoch_id
                ).order_by(WeatherStationGroupDecision.decided_at, WeatherStationGroupDecision.id)).all()
                report = {"approvals": [{"scope": row.scope, "approved": row.approved,
                                         "actor": row.actor, "dossier_hash": row.dossier_hash,
                                         "epoch_id": str(row.epoch_id), "decided_at": row.decided_at}
                                        for row in decisions],
                          "groups": [{"type": row.group_type, "key": row.group_key,
                                      "status": row.status, "actor": row.actor,
                                      "decided_at": row.decided_at} for row in groups]}
            else:
                raise SystemExit("unsupported command")
    print(json.dumps(report, default=str, sort_keys=True))


if __name__ == "__main__":
    main()
