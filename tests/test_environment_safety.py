"""Local/prod safety net: DB classification + the remote-write guard.

Pure, DB-less tests — they neither touch Postgres nor any real remote host.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.environment import classify_db, db_host
import app.safety as safety


def test_classify_local_hosts():
    assert classify_db("postgresql+psycopg://surf:surf@localhost:5432/surfwind") == "local"
    assert classify_db("postgresql+psycopg://surf:surf@127.0.0.1:5432/surfwind") == "local"
    assert classify_db("postgresql+psycopg://surf:surf@db:5432/surfwind") == "local"
    assert classify_db("postgresql://u:p@10.0.0.5:5432/x") == "local"
    assert classify_db("postgresql://u:p@192.168.1.10:5432/x") == "local"
    assert classify_db("postgresql://u:p@172.16.0.2:5432/x") == "local"


def test_classify_remote_hosts():
    neon = "postgresql://neondb_owner:pw@ep-wild-violet-al8cbqvv.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require"
    assert classify_db(neon) == "remote"
    assert db_host(neon).endswith("neon.tech")
    assert classify_db("postgresql://u:p@db.example.com:5432/x") == "remote"


def test_classify_unknown():
    assert classify_db("not-a-url") == "unknown"


def _guarded_app():
    app = FastAPI()
    app.add_middleware(safety.RemoteWriteGuardMiddleware)

    @app.get("/admin/spots")
    def _g():
        return {"ok": True}

    @app.post("/admin/spots")
    def _p():
        return {"ok": True}

    @app.post("/auth/login")
    def _login():
        return {"ok": True}

    return app


def test_guard_blocks_admin_writes_when_flagged(monkeypatch):
    monkeypatch.setattr(safety, "get_settings", lambda: type("S", (), {"admin_writes_blocked": True}))
    c = TestClient(_guarded_app())
    assert c.get("/admin/spots").status_code == 200      # reads always allowed
    assert c.post("/admin/spots").status_code == 403      # writes blocked
    assert c.post("/auth/login").status_code == 200        # auth never blocked


def test_guard_allows_admin_writes_when_not_flagged(monkeypatch):
    monkeypatch.setattr(safety, "get_settings", lambda: type("S", (), {"admin_writes_blocked": False}))
    c = TestClient(_guarded_app())
    assert c.post("/admin/spots").status_code == 200
