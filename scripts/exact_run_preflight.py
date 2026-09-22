"""Read-only dependency and shared raw-cache preflight for Exact-Run workers."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
import os
from pathlib import Path
import platform
import shutil
import socket
import stat
import time
import uuid
from urllib.parse import urlsplit

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db.session import engine
from app.weather.exact_run import EXACT_DATASET_MANIFEST_VERSION, EXACT_LOADER_VERSION, exact_cache_preflight


def _runner_id() -> str | None:
    """Stable runner identity; retain the legacy Canary variable as fallback."""
    return (
        os.environ.get("LIVE_WIND_RUNNER_ID")
        or os.environ.get("LIVE_WIND_CANARY_RUNNER_ID")
    )


def cache_persistence_probe(root: str | Path, *, mode: str, expected_id: str,
                            require_new_job: bool = False,
                            expected_sha256: str | None = None) -> dict:
    """Two-process cache proof. The verify step never creates the artifact."""
    import fcntl

    base = Path(root).resolve()
    directory = base / ".preflight-probes"
    if directory.is_symlink():
        raise ValueError("probe_directory_symlink")
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.stat().st_mode & stat.S_IWOTH:
        raise ValueError("probe_directory_world_writable")
    artifact = directory / "persistence.json"
    lock_path = directory / "persistence.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if mode == "create":
                if not artifact.exists():
                    payload = {"cache_id": expected_id, "host": socket.gethostname(),
                               "pid": os.getpid(), "nonce": uuid.uuid4().hex,
                               "runner_id": _runner_id(),
                               "runner_job_id": os.environ.get("LIVE_WIND_RUNNER_JOB_ID"),
                               "created_at": datetime.now().astimezone().isoformat()}
                    body = json.dumps(payload, sort_keys=True).encode()
                    temporary = directory / ("." + uuid.uuid4().hex + ".tmp")
                    try:
                        with temporary.open("xb") as out:
                            os.chmod(temporary, 0o600)
                            out.write(body)
                            out.flush()
                            os.fsync(out.fileno())
                        os.replace(temporary, artifact)
                        directory_fd = os.open(directory, os.O_RDONLY)
                        try:
                            os.fsync(directory_fd)
                        finally:
                            os.close(directory_fd)
                    finally:
                        temporary.unlink(missing_ok=True)
            elif mode != "verify":
                raise ValueError("invalid_probe_mode")
            if artifact.is_symlink() or not artifact.is_file():
                raise ValueError("persistence_probe_missing_or_redirected")
            body = artifact.read_bytes()
            payload = json.loads(body)
            checksum = hashlib.sha256(body).hexdigest()
            if expected_sha256 is not None and checksum != expected_sha256:
                raise ValueError("persistence_probe_checksum_changed")
            if require_new_job and not expected_sha256:
                raise ValueError("persistence_probe_external_checksum_missing")
            if payload.get("cache_id") != expected_id:
                raise ValueError("persistence_probe_cache_identity_changed")
            if require_new_job and payload.get("runner_id") != _runner_id():
                raise ValueError("persistence_probe_runner_identity_changed")
            if mode == "verify" and payload.get("pid") == os.getpid() and payload.get("host") == socket.gethostname():
                raise ValueError("persistence_probe_same_process")
            new_job = bool(os.environ.get("LIVE_WIND_RUNNER_JOB_ID")) and (
                payload.get("runner_job_id") != os.environ.get("LIVE_WIND_RUNNER_JOB_ID"))
            if require_new_job and not new_job:
                raise ValueError("persistence_probe_new_runner_job_unverified")
            return {"status": "process_restart_verified" if mode == "verify" else "created",
                    "checksum_sha256": checksum,
                    "cache_id": expected_id,
                    "host_restart_verified": False,
                    "runner_job_restart_verified": bool(mode == "verify" and new_job),
                    "assessment": "persistence_not_fully_verified"}
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run_preflight(*, require_test_database: bool = False,
                  allow_migration_pending: bool = False,
                  canary: bool = False, persistence_mode: str | None = None,
                  expected_probe_sha256: str | None = None,
                  require_new_job: bool = False) -> dict:
    cfg = get_settings()
    output = {"status": "failed", "checks": {}, "errors": []}
    url = make_url(cfg.database_url)
    if engine.url != url:
        output["errors"].append("database_engine_target_mismatch")
    if require_test_database and (
        cfg.app_env == "production"
        or url.database != "surfwind_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("smoke_requires_local_surfwind_test_database")
    root = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(root / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        output["errors"].append("migration_multiple_heads")
    if cfg.live_wind_rollout_stage != "shadow":
        output["errors"].append("public_rollout_not_shadow")
    if cfg.live_wind_enabled_region_slugs:
        output["errors"].append("public_region_allowlist_not_empty")
    if canary:
        if not cfg.live_wind_canary_mode:
            output["errors"].append("canary_mode_not_enabled")
        if platform.system() != "Linux":
            output["errors"].append("canary_requires_linux")
        if cfg.app_env == "production" or cfg.database_target != "local":
            output["errors"].append("canary_requires_verified_local_staging_database")
        staging_name = os.environ.get("LIVE_WIND_CANARY_STAGING_DATABASE", "").strip()
        if (not staging_name or url.database != staging_name
                or not staging_name.startswith(("surfwind_staging_", "surfwind_canary_"))):
            output["errors"].append("canary_staging_database_identity_mismatch")
        if not cfg.live_wind_force_baseline:
            output["errors"].append("canary_requires_force_baseline")
        if not (_runner_id() or "").strip():
            output["errors"].append("canary_runner_identity_missing")
        if not os.environ.get("LIVE_WIND_CANARY_ID", "").strip():
            output["errors"].append("canary_id_missing")
        if not os.environ.get("LIVE_WIND_RUNNER_JOB_ID", "").strip():
            output["errors"].append("canary_runner_job_id_missing")
        for variable in ("WEATHER_OBSERVATION_ENDPOINT", "LIVE_WIND_ENDPOINT"):
            endpoint = os.environ.get(variable, "").strip()
            if endpoint and (urlsplit(endpoint).scheme not in {"http", "https"}
                             or urlsplit(endpoint).hostname not in {"localhost", "127.0.0.1", "::1"}):
                output["errors"].append(f"canary_nonlocal_endpoint:{variable}")
        if persistence_mode != "verify":
            output["errors"].append("canary_persistence_not_verified")
        output["checks"]["runner_identity"] = _runner_id() or ""
    if require_new_job and persistence_mode != "verify":
        output["errors"].append("new_job_proof_requires_persistence_verify")
    if cfg.live_wind_exact_capture_mode != "scheduled":
        output["errors"].append("exact_capture_mode_not_scheduled")
    if (canary or cfg.app_env == "production") and (
        datetime.now().astimezone().utcoffset().total_seconds() != 0
        or cfg.live_wind_enabled_region_slugs
    ):
        output["errors"].append("runner_utc_or_public_region_configuration_invalid")
    if canary:
        try:
            import eccodes

            output["checks"]["eccodes_python"] = all(callable(getattr(eccodes, name, None)) for name in (
                "codes_get", "codes_get_array", "codes_grib_new_from_file",
                "codes_new_from_message", "codes_release",
            ))
        except ImportError:
            output["checks"]["eccodes_python"] = False
        output["checks"]["eccodes_grib_get"] = shutil.which("grib_get") is not None
        if not output["checks"]["eccodes_python"]:
            output["errors"].append("eccodes_tools_missing")
    output["checks"]["capture_mode"] = cfg.live_wind_exact_capture_mode
    output["checks"]["loader_version"] = EXACT_LOADER_VERSION
    output["checks"]["dataset_manifest_version"] = EXACT_DATASET_MANIFEST_VERSION
    try:
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
            database_epoch = float(db.scalar(text("SELECT EXTRACT(EPOCH FROM now())")))
            current = (tuple(db.execute(text("SELECT version_num FROM alembic_version")).scalars())
                       if inspect(db).has_table("alembic_version") else ())
        output["checks"]["postgresql"] = "reachable"
        output["checks"]["database_target"] = {"host": url.host, "database": url.database,
                                                  "classification": cfg.database_target}
        output["checks"]["database_clock_skew_seconds"] = round(database_epoch - time.time(), 3)
        if abs(database_epoch - time.time()) > 120:
            output["errors"].append("database_clock_skew")
        output["checks"]["migration_head"] = current
        if current != tuple(heads) and not allow_migration_pending:
            output["errors"].append("migration_head_mismatch")
    except Exception as exc:
        output["errors"].append(f"postgresql_unavailable:{type(exc).__name__}")
    try:
        import redis

        client = redis.Redis.from_url(cfg.redis_url, socket_connect_timeout=2, socket_timeout=2)
        if not client.ping():
            raise ConnectionError("redis_ping_failed")
        output["checks"]["redis"] = "reachable"
        redis_time = client.time()
        redis_epoch = float(redis_time[0]) + float(redis_time[1]) / 1_000_000
        output["checks"]["redis_clock_skew_seconds"] = round(redis_epoch - time.time(), 3)
        if abs(redis_epoch - time.time()) > 120:
            output["errors"].append("redis_clock_skew")
    except Exception as exc:
        output["errors"].append(f"redis_unavailable:{type(exc).__name__}")
    try:
        if not cfg.live_wind_exact_run_cache_dir:
            raise ValueError("cache_dir_unconfigured")
        output["checks"]["cache"] = exact_cache_preflight(
            cfg.live_wind_exact_run_cache_dir,
            expected_id=cfg.live_wind_exact_run_cache_id,
            require_persistent=canary or cfg.app_env == "production",
            minimum_free_bytes=(cfg.live_wind_exact_run_min_free_bytes
                                if canary or cfg.app_env == "production" else 0),
        )
        if persistence_mode:
            if platform.system() != "Linux":
                raise ValueError("persistence_probe_requires_linux")
            output["checks"]["persistence"] = cache_persistence_probe(
                cfg.live_wind_exact_run_cache_dir, mode=persistence_mode,
                expected_id=cfg.live_wind_exact_run_cache_id or "",
                require_new_job=canary or require_new_job,
                expected_sha256=expected_probe_sha256)
    except Exception as exc:
        output["errors"].append(f"cache_unavailable:{type(exc).__name__}:{exc}")
    output["status"] = "ready" if not output["errors"] else "failed"
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-test-database", action="store_true")
    parser.add_argument("--allow-migration-pending", action="store_true")
    parser.add_argument("--canary", action="store_true")
    parser.add_argument("--persistence", choices=("create", "verify"))
    parser.add_argument("--expected-probe-sha256")
    parser.add_argument("--require-new-job", action="store_true")
    args = parser.parse_args()
    try:
        result = run_preflight(
            require_test_database=args.require_test_database,
            allow_migration_pending=args.allow_migration_pending,
            canary=args.canary, persistence_mode=args.persistence,
            expected_probe_sha256=args.expected_probe_sha256,
            require_new_job=args.require_new_job,
        )
    except ValueError as exc:
        result = {"status": "failed", "checks": {}, "errors": [str(exc)]}
    print(json.dumps(result, sort_keys=True, default=str))
    if result["status"] != "ready":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
