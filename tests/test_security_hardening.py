"""Pure security regression tests that do not require Postgres."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.password_policy import ensure_password_safe


def test_common_password_is_rejected_without_network() -> None:
    with pytest.raises(ValueError, match="zu häufig"):
        ensure_password_safe("password1234")


def test_production_admin_requires_security_controls() -> None:
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        Settings(
            app_env="production",
            deployment_mode="admin",
            enable_admin_api=True,
            api_debug=False,
            cookie_secure=True,
            jwt_secret="x" * 48,
            cors_origins=["https://dashboard.example"],
        )


def test_browser_security_headers_are_present() -> None:
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "https://*.cartocdn.com" in response.headers["content-security-policy"]


def test_media_proxy_is_mounted_on_the_admin_deployment() -> None:
    """The picker's provider proxy holds the API keys, so it must live behind
    the same role guard as the rest of the back office."""
    paths = app.openapi()["paths"]
    assert "/admin/media/search" in paths
    assert "/admin/media/providers" in paths


def test_media_proxy_is_absent_from_a_public_deployment() -> None:
    """ENABLE_ADMIN_API=false must expose no admin surface at all — the public
    origin has no business holding provider credentials.

    Run in a subprocess: the app builds its router set at import time from a
    module-level settings object, so the only faithful way to check the other
    deployment mode is a fresh interpreter. Reloading the module in-process
    would re-register startup hooks and leak into the rest of the session.
    """
    import os
    import subprocess
    import sys

    script = (
        "from app.main import app;"
        "paths = list(app.openapi()['paths']);"
        "print(','.join(p for p in paths if p.startswith('/admin') or p.startswith('/auth')))"
    )
    env = {
        **os.environ,
        "DEPLOYMENT_MODE": "public",
        "ENABLE_ADMIN_API": "false",
        "APP_ENV": "development",
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"public build exposes: {result.stdout!r}"
