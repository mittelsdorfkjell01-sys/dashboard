"""Prune archived development evidence with explicit, verifiable safeguards."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.config import Settings


CONFIRMATION = "PRUNE-DEVELOPMENT-EVIDENCE"
ARCHIVED_TABLES = (
    "weather_observation_revisions",
    "weather_observations",
    "weather_forecast_samples",
)


def _database_fingerprint(url: str) -> str:
    parsed = make_url(url)
    identity = f"{parsed.host or ''}:{parsed.port or ''}/{parsed.database or ''}"
    return hashlib.sha256(identity.encode()).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_manifest(path: Path, settings: Settings) -> dict:
    manifest_path = path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "surfwind-development-evidence-v1":
        raise SystemExit("unsupported archive manifest")
    if manifest.get("database_fingerprint") != _database_fingerprint(
        settings.database_url
    ):
        raise SystemExit("archive belongs to a different database")
    for table_name in ARCHIVED_TABLES:
        item = manifest.get("tables", {}).get(table_name)
        if not item:
            raise SystemExit(f"archive is missing {table_name}")
        data_path = manifest_path.parent / item["file"]
        if not data_path.is_file() or _sha256(data_path) != item["sha256"]:
            raise SystemExit(f"archive checksum failed for {table_name}")
    return manifest


def _parse_cutoff(value: str) -> datetime:
    cutoff = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise SystemExit("--before must include a timezone")
    return cutoff.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-manifest", type=Path, required=True)
    parser.add_argument("--before", required=True, help="ISO-8601 UTC cutoff")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 100 or args.batch_size > 50_000:
        raise SystemExit("--batch-size must be between 100 and 50000")
    if args.apply and args.confirmation != CONFIRMATION:
        raise SystemExit(f"--apply requires --confirmation {CONFIRMATION}")
    if args.compact and not args.apply:
        raise SystemExit("--compact requires --apply")

    settings = (
        Settings(_env_file=(str(args.env_file),)) if args.env_file else Settings()
    )
    manifest = _verified_manifest(args.archive_manifest, settings)
    cutoff = _parse_cutoff(args.before)
    engine = create_engine(settings.database_url, poolclass=NullPool)
    counts = {}
    try:
        with engine.connect() as conn:
            current = {
                name: conn.scalar(text(f'SELECT count(*) FROM "{name}"'))
                for name in ARCHIVED_TABLES
            }
            for name, count in current.items():
                if count > manifest["tables"][name]["rows"]:
                    raise SystemExit(
                        f"{name} grew after the archive; create a new archive before pruning"
                    )
            counts = {
                "weather_observations": conn.scalar(
                    text(
                        """
                        SELECT count(*) FROM weather_observations o
                        WHERE o.observed_at < :cutoff
                          AND NOT EXISTS (
                            SELECT 1 FROM weather_live_wind_holdout_cases h
                            WHERE h.target_observation_id = o.id
                          )
                        """
                    ),
                    {"cutoff": cutoff},
                ),
                "weather_forecast_samples": conn.scalar(
                    text(
                        "SELECT count(*) FROM weather_forecast_samples "
                        "WHERE valid_at < :cutoff"
                    ),
                    {"cutoff": cutoff},
                ),
            }
        if not args.apply:
            print(json.dumps({"mode": "dry_run", "cutoff": cutoff.isoformat(), **counts}))
            return

        deleted = {name: 0 for name in ARCHIVED_TABLES}
        with engine.begin() as conn:
            while True:
                rows = conn.execute(
                    text(
                        """
                        DELETE FROM weather_observations
                        WHERE id IN (
                          SELECT o.id FROM weather_observations o
                          WHERE o.observed_at < :cutoff
                            AND NOT EXISTS (
                              SELECT 1 FROM weather_live_wind_holdout_cases h
                              WHERE h.target_observation_id = o.id
                            )
                          ORDER BY o.observed_at
                          LIMIT :batch_size
                        ) RETURNING id
                        """
                    ),
                    {"cutoff": cutoff, "batch_size": args.batch_size},
                ).all()
                deleted["weather_observations"] += len(rows)
                if len(rows) < args.batch_size:
                    break
            while True:
                rows = conn.execute(
                    text(
                        """
                        DELETE FROM weather_observation_revisions
                        WHERE id IN (
                          SELECT r.id FROM weather_observation_revisions r
                          WHERE r.received_at < :cutoff
                            AND NOT EXISTS (
                              SELECT 1 FROM weather_observations o
                              WHERE o.raw_revision_id = r.id
                            )
                          ORDER BY r.received_at
                          LIMIT :batch_size
                        ) RETURNING id
                        """
                    ),
                    {"cutoff": cutoff, "batch_size": args.batch_size},
                ).all()
                deleted["weather_observation_revisions"] += len(rows)
                if len(rows) < args.batch_size:
                    break
            while True:
                rows = conn.execute(
                    text(
                        """
                        DELETE FROM weather_forecast_samples
                        WHERE id IN (
                          SELECT id FROM weather_forecast_samples
                          WHERE valid_at < :cutoff
                          ORDER BY valid_at
                          LIMIT :batch_size
                        ) RETURNING id
                        """
                    ),
                    {"cutoff": cutoff, "batch_size": args.batch_size},
                ).all()
                deleted["weather_forecast_samples"] += len(rows)
                if len(rows) < args.batch_size:
                    break
        if args.compact:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                for table_name in ARCHIVED_TABLES:
                    conn.execute(text(f'VACUUM (FULL, ANALYZE) "{table_name}"'))
        print(json.dumps({"mode": "applied", "cutoff": cutoff.isoformat(), **deleted}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
