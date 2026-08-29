"""Dependency probes with deliberately sanitized diagnostics."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text

from app.db.schema import EXPECTED_DB_REVISION

SchemaStatus = Literal["ok", "outdated", "unknown", "error"]


@dataclass(frozen=True)
class DatabaseHealth:
    db: Literal["ok", "down"]
    schema: SchemaStatus
    db_error: str | None = None
    schema_error: str | None = None


def _error_class(exc: BaseException) -> str:
    """Return only a type name; exception messages may contain credentials."""
    return type(exc).__name__


def _is_missing_alembic_table(exc: BaseException) -> bool:
    original = getattr(exc, "orig", exc)
    return getattr(original, "sqlstate", None) == "42P01"


def check_database(engine) -> DatabaseHealth:
    try:
        connection = engine.connect()
    except Exception as exc:
        return DatabaseHealth("down", "unknown", db_error=_error_class(exc))

    try:
        with connection as conn:
            try:
                conn.execute(text("SELECT 1"))
            except Exception as exc:
                return DatabaseHealth("down", "unknown", db_error=_error_class(exc))

            try:
                revisions = tuple(
                    conn.execute(text("SELECT version_num FROM alembic_version")).scalars()
                )
            except Exception as exc:
                if _is_missing_alembic_table(exc):
                    return DatabaseHealth("ok", "outdated", schema_error="MissingAlembicVersionTable")
                return DatabaseHealth("ok", "error", schema_error=_error_class(exc))

            if revisions == (EXPECTED_DB_REVISION,):
                return DatabaseHealth("ok", "ok")
            return DatabaseHealth("ok", "outdated")
    except Exception as exc:
        return DatabaseHealth("down", "unknown", db_error=_error_class(exc))


def check_redis(url: str) -> tuple[bool, str | None]:
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        return bool(client.ping()), None
    except Exception as exc:
        return False, _error_class(exc)
