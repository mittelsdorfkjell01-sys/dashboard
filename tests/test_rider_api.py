"""Rider-profile, gear, event, privacy-export and deletion API contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.account.security import create_app_session_token, hash_password
from app.config import get_settings
from app.csrf import new_csrf_token
from app.main import app
from app.models import AppUser, RiderProfile, UserEvent


@pytest.fixture
def rider_account(db):
    password = "rider-test-password"
    user = AppUser(
        email=f"rider-{uuid.uuid4().hex[:10]}@example.com",
        password_hash=hash_password(password),
        display_name="Rider Test",
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    client = TestClient(app)
    settings = get_settings()
    client.cookies.set(settings.app_auth_cookie_name, create_app_session_token(user.id))
    csrf = new_csrf_token()
    client.cookies.set(settings.csrf_cookie_name, csrf)
    client.headers["X-CSRF-Token"] = csrf
    yield client, user, password
    db.expire_all()
    remaining = db.get(AppUser, user_id)
    if remaining is not None:
        db.delete(remaining)
        db.commit()


def test_rider_profile_auth_validation_csrf_and_crud(db, rider_account):
    client, user, _ = rider_account
    assert TestClient(app).get("/account/rider-profile").status_code == 401
    assert client.put("/account/rider-profile", json={"weightKg": 29}).status_code == 422

    without_csrf = TestClient(app)
    without_csrf.cookies.set(
        get_settings().app_auth_cookie_name, create_app_session_token(user.id)
    )
    assert without_csrf.put("/account/rider-profile", json={"weightKg": 78}).status_code == 403

    base = client.put("/account/rider-profile", json={
        "weightKg": 82,
        "homeLocation": {"lat": 54.4, "lon": 10.2},
        "maxTravelKm": 250,
        "travelMode": "weekend",
        "availability": [5, 6],
        "minWaterTempC": 10,
        "excludedBottoms": ["reef"],
    })
    assert base.status_code == 200, base.text
    assert "band" not in str(base.json()).lower()

    sport = client.put("/account/rider-profile/kitesurf", json={
        "level": "advanced",
        "styleWeights": {"freeride": 3, "big_air": 1},
        "preferredWaterCharacter": ["flach", "chop"],
    })
    assert sport.status_code == 200, sport.text
    assert "band" not in str(sport.json()).lower()
    assert client.put("/account/rider-profile/kitesurf", json={
        "level": "advanced", "styleWeights": {"unknown": 1},
    }).status_code == 422

    kite = client.post("/account/gear", json={
        "sport": "kitesurf", "kind": "kite", "size": 9,
        "active": True, "sortOrder": 0,
    })
    board = client.post("/account/gear", json={
        "sport": "kitesurf", "kind": "board", "boardType": "foil",
        "active": True, "sortOrder": 1,
    })
    assert kite.status_code == board.status_code == 201
    items = client.get("/account/gear?sport=kitesurf").json()["items"]
    assert [item["kind"] for item in items] == ["kite", "board"]
    assert all("band" not in str(item).lower() for item in items)
    assert items[-1]["profileVersion"] > base.json()["profileVersion"]

    changed = client.put(f"/account/gear/{kite.json()['id']}", json={
        "sport": "kitesurf", "kind": "kite", "size": 10,
        "active": True, "sortOrder": 0,
    })
    assert changed.status_code == 200
    assert client.delete(f"/account/gear/{board.json()['id']}").status_code == 204
    assert db.scalar(select(RiderProfile).where(RiderProfile.app_user_id == user.id))


def test_events_export_and_account_deletion(db, rider_account):
    client, user, password = rider_account
    user_id = user.id
    anon_id = str(uuid.uuid4())
    anon = TestClient(app)
    response = anon.post("/events", json={"events": [{
        "type": "search", "anonId": anon_id,
        "surface": "search", "context": {"query": "Ostsee"},
    }]})
    assert response.status_code == 202, response.text

    response = client.post("/events", json={"events": [{
        "type": "favorite_add", "anonId": anon_id,
        "surface": "spot", "context": {},
    }]})
    assert response.status_code == 202, response.text
    db.expire_all()
    signed_in = db.scalar(select(UserEvent).where(UserEvent.app_user_id == user.id))
    assert signed_in is not None and signed_in.anon_id is None
    assert anon.post("/events", json={"events": [{
        "type": "notification_sent", "anonId": anon_id,
    }]}).status_code == 422
    assert anon.post("/events", json={"events": [{
        "type": "made_up", "anonId": anon_id,
    }]}).status_code == 422

    exported = client.get("/account/export")
    assert exported.status_code == 200
    assert exported.json()["events"][0]["type"] == "favorite_add"
    assert "rider_profile" in exported.json()
    assert "gear" in exported.json()

    deleted = client.request("DELETE", "/account", json={"password": password})
    assert deleted.status_code == 204, deleted.text
    db.expire_all()
    assert db.get(AppUser, user_id) is None
    assert db.scalar(select(UserEvent).where(UserEvent.app_user_id == user_id)) is None
