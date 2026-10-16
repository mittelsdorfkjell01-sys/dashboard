"""Create a verifiable, read-only archive of high-churn development evidence."""

from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.config import Settings


EVIDENCE_TABLES = (
    "weather_observation_revisions",
    "weather_observations",
    "weather_forecast_samples",
    "weather_station_metadata_revisions",
    "weather_station_epochs",
    "weather_live_wind_jobs",
    "weather_live_wind_holdout_cases",
    "weather_live_wind_verification_evidence",
    "forecast_snapshots",
    "forecast_processing_jobs",
    "recommendation_log",
)


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return {"encoding": "base64", "value": base64.b64encode(value).decode()}
    raise TypeError(f"unsupported archive value: {type(value).__name__}")


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


def archive(*, settings: Settings, output_root: Path, allow_remote_read: bool) -> Path:
    if settings.database_target == "remote" and not allow_remote_read:
        raise SystemExit("remote archive requires --allow-remote-read")
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    archive_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_dir = output_root / archive_id
    work_dir = output_root / f".{archive_id}.partial"
    if final_dir.exists() or work_dir.exists():
        raise SystemExit(f"archive destination already exists: {final_dir}")
    work_dir.mkdir()

    engine = create_engine(settings.database_url, poolclass=NullPool)
    manifest = {
        "format": "surfwind-development-evidence-v1",
        "archive_id": archive_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database_target": settings.database_target,
        "database_fingerprint": _database_fingerprint(settings.database_url),
        "tables": {},
    }
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                manifest["alembic_revision"] = conn.scalar(
                    text("SELECT version_num FROM alembic_version")
                )
                for table_name in EVIDENCE_TABLES:
                    table = Table(
                        table_name,
                        MetaData(),
                        autoload_with=conn,
                        resolve_fks=False,
                    )
                    statement = select(table)
                    if table.primary_key.columns:
                        statement = statement.order_by(*table.primary_key.columns)
                    file_path = work_dir / f"{table_name}.ndjson.gz"
                    rows = 0
                    with gzip.open(file_path, "wt", encoding="utf-8", newline="\n") as out:
                        result = conn.execution_options(stream_results=True).execute(statement)
                        for row in result.mappings():
                            out.write(
                                json.dumps(
                                    dict(row),
                                    default=_json_value,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                )
                                + "\n"
                            )
                            rows += 1
                    manifest["tables"][table_name] = {
                        "rows": rows,
                        "file": file_path.name,
                        "bytes": file_path.stat().st_size,
                        "sha256": _sha256(file_path),
                        "columns": [column.name for column in table.columns],
                    }
        manifest_path = work_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        work_dir.rename(final_dir)
        return final_dir
    except BaseException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Explicit settings file; use .env only when intentionally archiving remote data.",
    )
    parser.add_argument("--allow-remote-read", action="store_true")
    args = parser.parse_args()
    settings = (
        Settings(_env_file=(str(args.env_file),)) if args.env_file else Settings()
    )
    destination = archive(
        settings=settings,
        output_root=args.output,
        allow_remote_read=args.allow_remote_read,
    )
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "archive": str(destination),
                "tables": len(manifest["tables"]),
                "rows": sum(item["rows"] for item in manifest["tables"].values()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
