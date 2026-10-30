"""Secret-free, read-only probes for the public and admin deployments."""

from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PUBLIC = "https://surfwinddata.com/api"
ADMIN = "https://dashboardsurfwind.vercel.app/api"


def probe(base: str, path: str) -> dict[str, object]:
    started = time.monotonic()
    try:
        with urlopen(
            Request(base + path, headers={"Accept": "application/json"}), timeout=15
        ) as response:
            status = response.status
            payload = json.load(response)
    except HTTPError as exc:
        status = exc.code
        try:
            payload = json.load(exc)
        except (ValueError, TypeError):
            payload = {}
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "path": path,
            "status": "unreachable",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": type(exc).__name__,
        }
    safe = {"path": path, "status": status, "latency_ms": round((time.monotonic() - started) * 1000)}
    if path == "/health/ready" and isinstance(payload, dict):
        safe["health"] = {
            key: payload.get(key) for key in ("status", "db", "schema", "redis")
        }
    elif path == "/spots/version" and isinstance(payload, dict):
        safe["catalog_version"] = payload.get("version")
    return safe


def report() -> dict[str, object]:
    public = [
        probe(PUBLIC, "/health/live"),
        probe(PUBLIC, "/health/ready"),
        probe(PUBLIC, "/spots/version"),
        probe(PUBLIC, "/auth/me"),
        probe(PUBLIC, "/admin/overview"),
    ]
    admin = [
        probe(ADMIN, "/health/live"),
        probe(ADMIN, "/health/ready"),
        probe(ADMIN, "/spots/version"),
        probe(ADMIN, "/auth/me"),
        probe(ADMIN, "/admin/overview"),
    ]
    return {"public": public, "admin": admin}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict", action="store_true", help="Fail unless both deployments are release-ready"
    )
    args = parser.parse_args(argv)
    result = report()
    print(json.dumps(result, indent=2))
    if not args.strict:
        return 0
    public, admin = result["public"], result["admin"]
    statuses_ok = [item["status"] for item in public] == [200, 200, 200, 404, 404]
    statuses_ok &= [item["status"] for item in admin] == [200, 200, 200, 401, 401]
    public_version = public[2].get("catalog_version")
    admin_version = admin[2].get("catalog_version")
    return 0 if statuses_ok and public_version == admin_version else 1


if __name__ == "__main__":
    raise SystemExit(main())
