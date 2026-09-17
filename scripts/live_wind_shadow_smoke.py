"""Bounded, destructive-only-to-local-test-DB fixture acceptance command.

The existing pytest session fixture recreates the public schema of the
dedicated surfwind_test database. Never run this against any other database.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from sqlalchemy.engine import make_url

from app.config import Settings


def main() -> None:
    cfg = Settings()
    test_url = make_url(cfg.test_database_url)
    if test_url.host not in {"localhost", "127.0.0.1", "::1"} or test_url.database != "surfwind_test":
        print(json.dumps({"status": "failed", "reason": "local_test_database_required"}))
        raise SystemExit(2)
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="exact-run-shadow-fixture-") as cache_dir:
        env = dict(os.environ)
        env.update({
            "APP_ENV": "test", "DEPLOYMENT_MODE": "admin",
            "ENABLE_ADMIN_API": "true", "CI": "1",
            "DATABASE_URL": cfg.test_database_url,
            "TEST_DATABASE_URL": cfg.test_database_url,
            "LIVE_WIND_EXACT_RUN_CACHE_DIR": cache_dir,
            "EXACT_RUN_SMOKE_CACHE_DIR": cache_dir,
        })
        stages = (
            ("preflight", [sys.executable, "-m", "scripts.exact_run_preflight",
                           "--require-test-database", "--allow-migration-pending"]),
            ("fixture_acceptance", [sys.executable, "-m", "pytest", "-q",
                                    "tests/test_exact_run_integration.py",
                                    "tests/test_exact_dataset_migration.py"]),
            ("schema_and_dependencies", [sys.executable, "-m", "scripts.exact_run_preflight",
                                         "--require-test-database"]),
        )
        results = []
        for name, command in stages:
            completed = subprocess.run(command, cwd=root, env=env,
                                       capture_output=True, text=True, check=False)
            results.append({"stage": name, "exit_code": completed.returncode,
                            "output": completed.stdout.strip()[-4000:],
                            "error": completed.stderr.strip()[-1200:]})
            if completed.returncode:
                break
        status = "accepted" if len(results) == len(stages) and all(
            item["exit_code"] == 0 for item in results) else "failed"
        print(json.dumps({"status": status, "test_database": "surfwind_test",
                          "network_weather_used": False, "public_effect": "none",
                          "stages": results}, sort_keys=True))
        if status != "accepted":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
