"""Admin rider-model versioning and preview."""

from copy import deepcopy

from sqlalchemy import delete, select

from app.models import ScoringParams


def test_rider_model_admin_auth_preview_and_versioned_save(client, anon_client, db):
    assert anon_client.get("/admin/rider-model").status_code == 401
    current = client.get("/admin/rider-model")
    assert current.status_code == 200, current.text
    document = current.json()
    assert document["version"] >= 3

    preview = client.post("/admin/rider-model/preview", json={
        "rider_model": document["rider_model"],
        "default_rider": document["default_rider"],
        "weight_kg": 82,
        "level": "advanced",
        "quiver": [
            {"kind": "kite", "size": 9},
            {"kind": "kite", "size": 12},
            {"kind": "board", "board_type": "foil"},
        ],
        "style_weights": {"freeride": 2},
        "travel_mode": "day_trip",
    })
    assert preview.status_code == 200, preview.text
    assert preview.json()["min_kt"] < preview.json()["max_kt"]

    previous_version = document["version"]
    previous_payload = deepcopy(db.scalar(select(ScoringParams).where(
        ScoringParams.sport == "kitesurf", ScoringParams.version == previous_version,
    )).params)
    saved = client.put("/admin/rider-model", json={
        "rider_model": document["rider_model"],
        "default_rider": document["default_rider"],
    })
    assert saved.status_code == 201, saved.text
    new_version = saved.json()["version"]
    assert new_version > previous_version
    db.expire_all()
    assert db.scalar(select(ScoringParams).where(
        ScoringParams.sport == "kitesurf", ScoringParams.version == previous_version,
    )).params == previous_payload
    assert db.scalar(select(ScoringParams).where(
        ScoringParams.sport == "kitesurf", ScoringParams.version == new_version,
    )).active is True

    # Restore the seeded state so other tests still observe the code baseline.
    db.execute(delete(ScoringParams).where(
        ScoringParams.sport == "kitesurf", ScoringParams.version == new_version,
    ))
    old = db.scalar(select(ScoringParams).where(
        ScoringParams.sport == "kitesurf", ScoringParams.version == previous_version,
    ))
    old.active = True
    db.commit()


def test_rider_model_admin_rejects_incomplete_calibration(client):
    document = client.get("/admin/rider-model").json()
    del document["rider_model"]["k_board"]["foil"]
    response = client.put("/admin/rider-model", json={
        "rider_model": document["rider_model"],
        "default_rider": document["default_rider"],
    })
    assert response.status_code == 422
