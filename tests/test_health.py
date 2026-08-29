from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.db.schema import EXPECTED_DB_REVISION
from app.health import DatabaseHealth, check_database
from app.main import app


class _Scalars:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class _Connection:
    def __init__(self, *, revisions=(), schema_error=None, ping_error=None):
        self.revisions = revisions
        self.schema_error = schema_error
        self.ping_error = ping_error

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement):
        sql = str(statement)
        if sql == "SELECT 1":
            if self.ping_error:
                raise self.ping_error
            return _Scalars(())
        if self.schema_error:
            raise self.schema_error
        return _Scalars(self.revisions)


@dataclass
class _Engine:
    connection: _Connection | None = None
    connect_error: Exception | None = None

    def connect(self):
        if self.connect_error:
            raise self.connect_error
        return self.connection


class _UndefinedTable:
    sqlstate = "42P01"


class _StatementError(Exception):
    def __init__(self, original):
        self.orig = original


def test_database_unreachable_makes_schema_unknown():
    result = check_database(_Engine(connect_error=ConnectionError("secret")))
    assert result.db == "down"
    assert result.schema == "unknown"
    assert result.db_error == "ConnectionError"
    assert "secret" not in repr(result)


def test_missing_alembic_table_is_outdated():
    error = _StatementError(_UndefinedTable())
    result = check_database(_Engine(_Connection(schema_error=error)))
    assert result.db == "ok"
    assert result.schema == "outdated"
    assert result.schema_error == "MissingAlembicVersionTable"


def test_wrong_revision_is_outdated():
    result = check_database(_Engine(_Connection(revisions=("old_revision",))))
    assert result == DatabaseHealth("ok", "outdated")


def test_expected_revision_is_ok():
    result = check_database(_Engine(_Connection(revisions=(EXPECTED_DB_REVISION,))))
    assert result == DatabaseHealth("ok", "ok")


def test_unexpected_schema_error_has_own_state():
    result = check_database(
        _Engine(_Connection(schema_error=RuntimeError("do not disclose")))
    )
    assert result.db == "ok"
    assert result.schema == "error"
    assert result.schema_error == "RuntimeError"
    assert "do not disclose" not in repr(result)


def test_liveness_does_not_probe_dependencies(monkeypatch):
    monkeypatch.setattr("app.main.check_database", lambda _engine: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr("app.main.check_redis", lambda _url: (_ for _ in ()).throw(AssertionError()))
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_redis_outage_is_degraded_but_ready(monkeypatch):
    monkeypatch.setattr("app.main.check_database", lambda _engine: DatabaseHealth("ok", "ok"))
    monkeypatch.setattr("app.main.check_redis", lambda _url: (False, "TimeoutError"))
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "db": "ok",
        "schema": "ok",
        "redis": "down",
        "diagnostics": {"redis_error": "TimeoutError"},
    }


def test_legacy_health_preserves_contract_with_unknown_schema(monkeypatch):
    monkeypatch.setattr(
        "app.main.check_database",
        lambda _engine: DatabaseHealth("down", "unknown", db_error="OperationalError"),
    )
    monkeypatch.setattr("app.main.check_redis", lambda _url: (True, None))
    response = TestClient(app).get("/health")
    assert response.status_code == 503
    assert response.json()["db"] == "down"
    assert response.json()["schema"] == "unknown"

