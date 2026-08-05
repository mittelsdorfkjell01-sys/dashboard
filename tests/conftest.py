"""Pytest fixtures.

The suite runs against a real Postgres+PostGIS database (TEST_DATABASE_URL) so
the migration, geography columns and ST_DWithin can be exercised for real.

Before anything from ``app`` that builds an engine is imported, we redirect
DATABASE_URL to the test database and reset the cached settings.
"""

import os
from pathlib import Path

from app.config import Settings, get_settings

# --- redirect the app to the test database BEFORE engine creation ---------
_TEST_URL = Settings().test_database_url
os.environ["DATABASE_URL"] = _TEST_URL
os.environ["APP_ENV"] = "test"
os.environ["DEPLOYMENT_MODE"] = "admin"
os.environ["ENABLE_ADMIN_API"] = "true"
# Keep ERA5 background auto-processing off in tests (a dev .env may enable it);
# tests that exercise it flip the setting explicitly.
os.environ["ERA5_AUTOPROCESS"] = "false"
get_settings.cache_clear()

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.community.ratelimit import NoLimitRateLimiter, get_rate_limiter  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Set by the session fixture: False when the test database can't be reached, so
# DB-backed tests skip instead of erroring (pure-function tests still run).
DB_AVAILABLE = True


def require_db() -> None:
    if not DB_AVAILABLE:
        pytest.skip("test database unavailable (start docker compose)")


def _alembic_config() -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", _TEST_URL)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _migrated_db():
    """Reset the test schema and run the migration to head, once per session.

    If the database is unreachable the suite does not error: ``DB_AVAILABLE`` is
    flipped and DB-backed fixtures skip, so pure-function tests still run.
    """
    global DB_AVAILABLE
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        command.upgrade(_alembic_config(), "head")
    except OperationalError as exc:
        if os.environ.get("CI"):
            raise RuntimeError("CI integration database unavailable") from exc
        DB_AVAILABLE = False
        print(f"\n[tests] test database unavailable — DB tests skipped: {exc}")
    yield


# --- auth (Sprint A): every /admin/* route now needs a session cookie --------
# Seed a known admin + curator once per session; the default `client` logs in as
# the admin so pre-auth admin tests keep working. Tests that need a different
# principal use `curator_client` / `anon_client` or build their own TestClient.
TEST_ADMIN = {"email": "admin@test.local", "password": "admin-pw-123", "role": "admin"}
TEST_CURATOR = {
    "email": "curator@test.local",
    "password": "curator-pw-123",
    "role": "curator",
}


def _ensure_auth_users() -> None:
    """Create the known admin/curator users if missing. Idempotent, so it also
    heals the schema after the migration round-trip test drops admin_users."""
    from app.auth import service

    db = SessionLocal()
    try:
        for u in (TEST_ADMIN, TEST_CURATOR):
            if service.get_by_email(db, u["email"]) is None:
                service.create_user(
                    db,
                    email=u["email"],
                    password=u["password"],
                    display_name=u["role"].title(),
                    role=u["role"],
                )
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def _auth_users(_migrated_db):
    if not DB_AVAILABLE:
        return
    _ensure_auth_users()


def _login(c: TestClient, creds: dict) -> TestClient:
    resp = c.post(
        "/auth/login", json={"email": creds["email"], "password": creds["password"]}
    )
    assert resp.status_code == 200, resp.text
    c.headers["X-CSRF-Token"] = c.cookies.get(get_settings().csrf_cookie_name)
    return c


@pytest.fixture(autouse=True)
def _unlimited_default_rate_limiter():
    """Keep general tests independent; limiter-specific tests replace this."""
    app.dependency_overrides[get_rate_limiter] = lambda: NoLimitRateLimiter()
    yield
    app.dependency_overrides[get_rate_limiter] = lambda: NoLimitRateLimiter()


@pytest.fixture
def db():
    require_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(_auth_users):
    require_db()
    _ensure_auth_users()  # heal after any mid-session schema reset
    return _login(TestClient(app), TEST_ADMIN)


@pytest.fixture
def curator_client(_auth_users):
    require_db()
    _ensure_auth_users()
    return _login(TestClient(app), TEST_CURATOR)


@pytest.fixture
def anon_client():
    require_db()
    return TestClient(app)
