"""Sprint A auth tests: login flow, session cookie, role guards, bootstrap, audit.

DB-gated (skips when the test database is unavailable) — the auth flow touches
the ``admin_users`` table.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.main import app
from app.models import Spot, SpotAudit
from tests.conftest import TEST_ADMIN, TEST_CURATOR

COOKIE = get_settings().auth_cookie_name


# --- login / me / logout ---------------------------------------------------

def test_login_success_sets_cookie(anon_client):
    resp = anon_client.post(
        "/auth/login",
        json={"email": TEST_ADMIN["email"], "password": TEST_ADMIN["password"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == TEST_ADMIN["email"]
    assert body["role"] == "admin"
    assert anon_client.cookies.get(COOKIE)


def test_login_wrong_password_401(anon_client):
    resp = anon_client.post(
        "/auth/login",
        json={"email": TEST_ADMIN["email"], "password": "nope"},
    )
    assert resp.status_code == 401
    assert not anon_client.cookies.get(COOKIE)


def test_login_recovers_from_stale_session_without_csrf_cookie(anon_client):
    anon_client.cookies.set(COOKIE, "stale-session")
    anon_client.cookies.pop(get_settings().csrf_cookie_name, None)

    resp = anon_client.post(
        "/auth/login",
        json={"email": TEST_ADMIN["email"], "password": TEST_ADMIN["password"]},
    )

    assert resp.status_code == 200, resp.text
    assert anon_client.cookies.get(get_settings().csrf_cookie_name)


def test_me_requires_auth(anon_client):
    assert anon_client.get("/auth/me").status_code == 401


def test_me_returns_current_user(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == TEST_ADMIN["email"]


def test_logout_clears_session(client):
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204
    # cookie deleted → subsequent call is unauthenticated
    assert client.get("/auth/me").status_code == 401


def test_mfa_endpoints_are_removed(client):
    assert client.post("/auth/mfa/setup", json={"password": "unused"}).status_code == 404


# --- guards ----------------------------------------------------------------

def test_admin_routes_require_auth(anon_client):
    # No cookie → the /admin router guard rejects before any handler runs.
    assert anon_client.post("/admin/regions", json={}).status_code == 401


def test_curator_cannot_manage_users(curator_client):
    assert curator_client.get("/admin/users").status_code == 403


def test_admin_can_manage_users(client):
    # list
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    assert any(u["email"] == TEST_ADMIN["email"] for u in resp.json())

    # create a fresh curator
    email = f"new-{uuid.uuid4().hex[:8]}@test.local"
    created = client.post(
        "/admin/users",
        json={"email": email, "password": "pw-123456789", "role": "curator"},
    )
    assert created.status_code == 201, created.text
    uid = created.json()["id"]
    assert created.json()["role"] == "curator"

    # duplicate email → 409
    dup = client.post(
        "/admin/users", json={"email": email, "password": "pw-123456789"}
    )
    assert dup.status_code == 409

    # promote to admin
    patched = client.patch(f"/admin/users/{uid}", json={"role": "admin"})
    assert patched.status_code == 200
    assert patched.json()["role"] == "admin"

    # reset password
    assert (
        client.post(f"/admin/users/{uid}/password", json={"password": "brandnew-123"}).status_code
        == 204
    )

    # the new account can now log in with the new password
    other = TestClient(app)
    login = other.post("/auth/login", json={"email": email, "password": "brandnew-123"})
    assert login.status_code == 200


def test_curator_can_still_curate(curator_client):
    # curator keeps access to the regular /admin surface (not user mgmt)
    resp = curator_client.post(
        "/admin/regions",
        json={
            "name": "Curator Region",
            "slug": f"cur-region-{uuid.uuid4().hex[:8]}",
            "country": "DE",
            "lat": 54.0,
            "lon": 10.0,
        },
    )
    assert resp.status_code == 201, resp.text


# --- bootstrap -------------------------------------------------------------

def test_bootstrap_creates_exactly_one_admin_idempotent(monkeypatch):
    """With an empty admin_users table, bootstrap creates one admin; a second
    call is a no-op. State is restored afterwards so other tests are unaffected."""
    from tests.conftest import require_db

    require_db()  # this test talks to the DB directly (no client fixture)

    from app.auth import service
    from app.db.session import SessionLocal
    from app.models import AdminUser

    class _FakeSettings:
        admin_bootstrap_email = "boot@test.local"
        admin_bootstrap_password = "boot-pw-123456"

    monkeypatch.setattr(service, "get_settings", lambda: _FakeSettings)

    db = SessionLocal()
    try:
        db.query(AdminUser).delete()
        db.commit()

        first = service.bootstrap_admin(db)
        second = service.bootstrap_admin(db)

        assert first is not None
        assert first.role == "admin"
        assert first.email == "boot@test.local"
        assert second is None  # idempotent — users already exist
        assert service.count_users(db) == 1
    finally:
        # restore the session's known users for the rest of the suite
        db.query(AdminUser).delete()
        db.commit()
        for u in (TEST_ADMIN, TEST_CURATOR):
            service.create_user(
                db,
                email=u["email"],
                password=u["password"],
                display_name=u["role"].title(),
                role=u["role"],
            )
        db.commit()
        db.close()


# --- audit actor -----------------------------------------------------------

def test_audit_actor_is_logged_in_email(client, db):
    """A spot created by the logged-in admin records that admin's email as the
    audit actor (not the old static 'admin')."""
    from app.admin.deps import get_extract_client
    from tests.era5_helpers import FakeCdsClient, make_synthetic_series

    app.dependency_overrides[get_extract_client] = lambda: FakeCdsClient(
        make_synthetic_series()
    )
    try:
        suffix = uuid.uuid4().hex[:8]
        region = client.post(
            "/admin/regions",
            json={
                "name": f"Audit Region {suffix}",
                "slug": f"audit-region-{suffix}",
                "country": "DE",
                "lat": 54.4,
                "lon": 10.2,
            },
        )
        assert region.status_code == 201, region.text
        region_id = region.json()["id"]

        spot = client.post(
            "/admin/spots",
            json={
                "name": f"Audit Spot {suffix}",
                "slug": f"audit-spot-{suffix}",
                "region_id": region_id,
                "lat": 54.41,
                "lon": 10.22,
                "sports": ["kitesurf"],
            },
        )
        assert spot.status_code == 201, spot.text
        spot_id = uuid.UUID(spot.json()["id"])

        audits = db.execute(
            select(SpotAudit).where(SpotAudit.spot_id == spot_id)
        ).scalars().all()
        assert audits, "expected at least one audit row for the created spot"
        assert all(a.actor == TEST_ADMIN["email"] for a in audits)
    finally:
        app.dependency_overrides.pop(get_extract_client, None)
        # cascade-clean the region we created
        from app.models import Region

        r = db.get(Region, uuid.UUID(region_id))
        if r is not None:
            db.delete(r)
            db.commit()


# --- Sprint 3: user management (delete + guards + default role) -------------

def test_create_user_defaults_to_admin(client):
    email = f"defadm-{uuid.uuid4().hex[:8]}@test.local"
    created = client.post("/admin/users", json={"email": email, "password": "pw-123456789"})
    assert created.status_code == 201, created.text
    # No role granularity: new accounts are admins.
    assert created.json()["role"] == "admin"


def test_delete_admin_user(client):
    email = f"deltarget-{uuid.uuid4().hex[:8]}@test.local"
    uid = client.post(
        "/admin/users", json={"email": email, "password": "pw-123456789"}
    ).json()["id"]

    assert client.delete(f"/admin/users/{uid}").status_code == 204
    assert all(u["id"] != uid for u in client.get("/admin/users").json())
    # Deleting again → 404.
    assert client.delete(f"/admin/users/{uid}").status_code == 404


def test_cannot_delete_self(client):
    me = client.get("/auth/me").json()
    resp = client.delete(f"/admin/users/{me['id']}")
    assert resp.status_code == 422
    assert "eigenes Konto" in resp.json()["detail"]


def test_update_user_email_and_name(client):
    email = f"e-{uuid.uuid4().hex[:8]}@test.local"
    uid = client.post(
        "/admin/users", json={"email": email, "password": "pw-123456789"}
    ).json()["id"]

    new_email = f"e2-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.patch(
        f"/admin/users/{uid}",
        json={"email": new_email, "display_name": "Neuer Name"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == new_email
    assert resp.json()["display_name"] == "Neuer Name"

    # Taking another account's email → 409.
    dup = client.patch(f"/admin/users/{uid}", json={"email": TEST_ADMIN["email"]})
    assert dup.status_code == 409
