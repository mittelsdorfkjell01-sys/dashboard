"""Classify the target database as *local* (safe/disposable) or *remote*
(production-like) so the app can refuse accidental production mutations from a
non-production ``app_env`` and surface a permanent indicator in the back office.

Pure, dependency-free helpers — imported by config and the write guard.
"""

from __future__ import annotations

from urllib.parse import urlsplit

# Hostnames that are always a local / disposable database.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", "postgres", "postgis"}


def db_host(database_url: str) -> str:
    """Extract the bare hostname from a SQLAlchemy/libpq URL.

    Handles the ``postgresql+psycopg://user:pw@host:port/name`` form (the driver
    suffix does not confuse ``urlsplit``'s netloc parsing).
    """
    try:
        netloc = urlsplit(database_url).netloc
        host = netloc.rsplit("@", 1)[-1]  # drop user:pw@
        host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host  # drop :port
        return host.strip("[]").lower()
    except Exception:  # pragma: no cover - defensive
        return ""


def classify_db(database_url: str) -> str:
    """Return ``"local"``, ``"remote"`` or ``"unknown"`` for a database URL.

    Loopback, Docker service names, ``*.local``/``*.internal`` and RFC-1918
    private ranges count as local; everything reachable elsewhere (managed
    cloud hosts such as ``*.neon.tech``/``*.aws``) counts as remote.
    """
    host = db_host(database_url)
    if not host:
        return "unknown"
    if host in _LOCAL_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return "local"
    if host.startswith("10.") or host.startswith("192.168.") or host.startswith("127."):
        return "local"
    if host.startswith("172."):  # 172.16.0.0 – 172.31.255.255
        try:
            if 16 <= int(host.split(".")[1]) <= 31:
                return "local"
        except (IndexError, ValueError):  # pragma: no cover - defensive
            pass
    return "remote"
