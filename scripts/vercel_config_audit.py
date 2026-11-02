"""Read-only Vercel project metadata audit without exposing environment values."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen


EXPECTED_ENV = {
    "surfwinddata": {
        "APP_ENV",
        "DEPLOYMENT_MODE",
        "ENABLE_ADMIN_API",
        "API_DEBUG",
        "COOKIE_SECURE",
        "JWT_SECRET",
        "PASSWORD_BREACH_CHECK_ENABLED",
        "CORS_ORIGINS",
        "DATABASE_URL",
        "DATABASE_URL_UNPOOLED",
        "DB_SERVERLESS",
        "REDIS_URL",
        "MEDIA_BACKEND",
    },
    "dashboard": {
        "APP_ENV",
        "DEPLOYMENT_MODE",
        "ENABLE_ADMIN_API",
        "API_DEBUG",
        "COOKIE_SECURE",
        "JWT_SECRET",
        "PASSWORD_BREACH_CHECK_ENABLED",
        "CORS_ORIGINS",
        "DATABASE_URL",
        "DATABASE_URL_UNPOOLED",
        "DB_SERVERLESS",
        "REDIS_URL",
        "MEDIA_BACKEND",
        "VITE_INCLUDE_ADMIN",
    },
}


def _get(url: str, token: str) -> dict:
    with urlopen(
        Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}),
        timeout=20,
    ) as response:
        return json.load(response)


def audit_project(name: str, *, token: str, team: str) -> dict[str, object]:
    root = "https://api.vercel.com"
    project = _get(f"{root}/v9/projects/{name}?teamId={quote(team)}", token)
    env = _get(f"{root}/v9/projects/{project['id']}/env?teamId={quote(team)}", token)
    domains = _get(f"{root}/v9/projects/{project['id']}/domains?teamId={quote(team)}", token)
    production_keys = {
        item["key"] for item in env.get("envs", []) if "production" in item.get("target", [])
    }
    actual_domains = sorted(item["name"] for item in domains.get("domains", []))
    missing = sorted(EXPECTED_ENV[name] - production_keys)
    build_command = project.get("buildCommand")
    build_ok = build_command is None or "build:release" in build_command
    domains_ok = (
        actual_domains == ["surfwinddata.com"]
        if name == "surfwinddata"
        else actual_domains == ["dashboardsurfwind.vercel.app"]
    )
    return {
        "project": name,
        "production_branch": project.get("link", {}).get("productionBranch"),
        "build_uses_release_guard": build_ok,
        "missing_environment_keys": missing,
        "domains": actual_domains,
        "domains_ok": domains_ok,
        "ok": build_ok and not missing and domains_ok,
    }


def main() -> int:
    token = os.getenv("VERCEL_TOKEN", "").strip()
    if not token:
        print("VERCEL_TOKEN is required", file=sys.stderr)
        return 2
    link_path = Path(".vercel/project.json")
    if not link_path.exists():
        print(".vercel/project.json is required", file=sys.stderr)
        return 2
    team = str(json.loads(link_path.read_text(encoding="utf-8"))["orgId"])
    results = [audit_project(name, token=token, team=team) for name in EXPECTED_ENV]
    print(json.dumps(results, indent=2))
    return 0 if all(result["ok"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
