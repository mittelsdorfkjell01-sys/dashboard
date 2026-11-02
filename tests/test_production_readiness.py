from types import SimpleNamespace

import pytest

from scripts import production_readiness


def test_wave_api_smoke_checks_ten_day_chain_manifest_and_series(monkeypatch):
    requested = []

    def get_json(_base_url, path):
        requested.append(path)
        if path == "/weather-fields/waves/health":
            return {
                "status": "ok",
                "primary": {"active_publication": {"publication_id": "ewam"}},
                "fallback": {"active_publication": {"publication_id": "gwam"}},
                "extended": {"active_publication": {"publication_id": "gfs-wave"}},
            }
        if "valid_at=2026-10-20" in path:
            return {"selection": {"selected_model": "noaa-gfs-wave"}}
        if path.startswith("/weather-fields/waves?"):
            return {
                "publication_id": "ewam",
                "manifest": {"valid_times": ["2026-10-10T12:00:00Z"]},
            }
        if path.startswith("/weather-fields/waves/sample?"):
            return {"total_wave_height_m": 1.7}
        if path.startswith("/weather-fields/waves/sample/series?"):
            return {
                "samples": [
                    {"valid_at": "2026-10-10T12:00:00Z"},
                    {"valid_at": "2026-10-20T12:00:00Z"},
                ],
                "sources": [
                    {
                        "model": "noaa-gfs-wave",
                        "model_run": "2026-10-10T12:00:00Z",
                        "valid_to": "2026-10-20T12:00:00Z",
                    }
                ],
            }
        raise AssertionError(path)

    monkeypatch.setattr(production_readiness, "_get_json", get_json)

    production_readiness.wave_api_smoke("https://surfwinddata.example")

    assert requested[0] == "/weather-fields/waves/health"
    assert "lat=54.4" in requested[1]
    assert "valid_at=2026-10-10T12%3A00%3A00Z" in requested[2]
    assert "/sample/series?" in requested[3]
    assert "valid_at=2026-10-20T12%3A00%3A00Z" in requested[4]


def test_api_smoke_requires_database_attestation(monkeypatch):
    requested = []

    def get_json(_base_url, path):
        requested.append(path)
        if path == "/health/ready":
            return {"db": "ok", "schema": "ok", "schema_fingerprint": "schema-ok"}
        if path == "/spots/version":
            return {"version": "2:2026-10-27T12:00:00+00:00"}
        if path == "/spots?limit=1":
            return [{"id": "spot-1", "slug": "laboe", "name": "Laboe"}]
        if path == "/spots/laboe":
            return {"id": "spot-1"}
        if path == "/regions?limit=1":
            return [{"id": "region-1"}]
        if path.startswith("/search?"):
            return {"spots": [{"id": "spot-1"}]}
        if path in ("/spots/spot-1/live", "/spots/spot-1/forecast"):
            return {"spot_id": "spot-1"}
        raise AssertionError(path)

    monkeypatch.setattr(production_readiness, "_get_json", get_json)
    monkeypatch.setenv("PRODUCTION_API_BASE_URL", "https://surfwinddata.example")
    monkeypatch.setenv("EXPECTED_SCHEMA_FINGERPRINT", "schema-ok")
    monkeypatch.setenv("EXPECTED_CATALOG_VERSION", "2:2026-10-27T12:00:00+00:00")

    production_readiness.api_smoke()
    assert requested[:2] == ["/health/ready", "/spots/version"]


def test_database_preflight_rejects_different_direct_and_pooled_targets(monkeypatch):
    direct = SimpleNamespace(close=lambda: None)
    pooled = SimpleNamespace(close=lambda: None)
    connections = iter((direct, pooled))
    monkeypatch.setattr(production_readiness, "_connect", lambda *_args: next(connections))
    monkeypatch.setattr(
        production_readiness,
        "_database_state",
        lambda connection, _label: (
            ((production_readiness.EXPECTED_DB_REVISION,), "1:none")
            if connection is direct
            else ((production_readiness.EXPECTED_DB_REVISION,), "2:none")
        ),
    )

    with pytest.raises(SystemExit):
        production_readiness.database_preflight(require_target=True)



def test_app_imports_on_vercel_when_the_local_asset_store_cannot_be_created(tmp_path):
    """Vercel's read-only filesystem must cost the mount, not the whole API.

    `weather_field_storage_backend` defaults to "local", so app.main ran
    os.makedirs at import. On Vercel everything outside /tmp is read-only, the
    OSError escaped during module import, and every API route answered
    FUNCTION_INVOCATION_FAILED before FastAPI ever saw a request.

    A directory under a regular file is the portable stand-in: makedirs raises
    NotADirectoryError, an OSError like the read-only one.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", "import app.main; print(len(app.main.app.routes))"],
        cwd=root,
        env={
            **os.environ,
            "VERCEL": "1",
            "WEATHER_FIELD_STORAGE_BACKEND": "local",
            "WEATHER_FIELD_STORAGE_DIR": str(blocker / "fields"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert int(result.stdout.strip()) > 0
    assert str(blocker / "fields") in result.stderr


def test_app_import_fails_outside_vercel_when_the_local_asset_store_cannot_be_created(tmp_path):
    """A persistent local backend must expose an invalid storage directory."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")

    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "WEATHER_FIELD_STORAGE_BACKEND": "local",
        "WEATHER_FIELD_STORAGE_DIR": str(blocker / "fields"),
    }
    env.pop("VERCEL", None)
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not-a-directory" in result.stderr
    assert "fields" in result.stderr
