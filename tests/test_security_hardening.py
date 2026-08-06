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
