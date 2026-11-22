from pathlib import Path
import socket

import pytest
from sqlalchemy.engine import make_url

from scripts.database_ipv4_env import database_url_with_ipv4, write_github_environment


ROOT = Path(__file__).resolve().parents[1]


def _resolver(_host, port, *, family, type):
    assert port == 5432
    assert family == socket.AF_INET
    assert type == socket.SOCK_STREAM
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.20", port)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.10", port)),
    ]


def test_database_url_keeps_hostname_and_credentials_but_pins_ipv4():
    resolved, address = database_url_with_ipv4(
        "postgresql+psycopg://user:p%40ss@db.example.test:5432/surfwind?sslmode=require",
        resolver=_resolver,
    )

    url = make_url(resolved)
    assert address == "203.0.113.10"
    assert url.host == "db.example.test"
    assert url.password == "p@ss"
    assert url.query["sslmode"] == "require"
    assert url.query["hostaddr"] == "203.0.113.10"


def test_existing_hostaddr_is_replaced():
    resolved, _address = database_url_with_ipv4(
        "postgresql://user:secret@db.example.test/surfwind?hostaddr=192.0.2.1",
        resolver=_resolver,
    )
    assert make_url(resolved).query["hostaddr"] == "203.0.113.10"


def test_writer_appends_database_url_without_printing_it(tmp_path: Path):
    target = tmp_path / "github-env"
    address = write_github_environment(
        "postgresql://user:secret@localhost/surfwind",
        target,
    )
    payload = target.read_text(encoding="utf-8")
    assert address
    assert payload.startswith("DATABASE_URL=postgresql://")
    assert "hostaddr=" in payload


def test_non_postgresql_url_is_rejected():
    with pytest.raises(ValueError, match="must use PostgreSQL"):
        database_url_with_ipv4("sqlite:///local.db", resolver=_resolver)


def test_all_hosted_neon_workers_configure_ipv4_before_database_access():
    workflow_paths = (
        ".github/workflows/tide-station-import.yml",
        ".github/workflows/wave-backtest.yml",
        ".github/workflows/wave-field-publish.yml",
    )
    for relative_path in workflow_paths:
        workflow = (ROOT / relative_path).read_text(encoding="utf-8")
        guard = workflow.index("python -m scripts.neon_transfer_guard")
        route = workflow.index("python -m scripts.database_ipv4_env")
        assert "--require-config" in workflow
        assert guard < route
        if relative_path.endswith("tide-station-import.yml"):
            assert route < workflow.index("from app.db.session import engine")
        elif relative_path.endswith("wave-backtest.yml"):
            assert route < workflow.index("scripts.copernicus_wave_observations")
        else:
            assert route < workflow.index("alembic current")
