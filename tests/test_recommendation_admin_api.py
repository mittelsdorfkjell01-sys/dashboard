"""Admin contracts for quality metrics and human-approved calibration."""

import uuid

from sqlalchemy import delete, select, update

from app.config import get_settings
from app.models import ScoringCalibrationProposal, ScoringParams
from app.scoring.params import seed_scoring_params


def test_recommendation_quality_and_calibration_read_contract(client):
    quality = client.get("/admin/recommendation-quality", params={"days": 30})
    assert quality.status_code == 200, quality.text
    assert set(quality.json()) == {"period", "rows", "totals"}
    assert quality.json()["period"]["days"] == 30

    calibration = client.get("/admin/scoring-calibration")
    assert calibration.status_code == 200, calibration.text
    assert {
        "active_params_version", "default_rider", "personal_band", "social", "proposals"
    } == set(calibration.json())
    assert calibration.json()["social"]["min_group_size"] >= 5


def test_social_proposal_requires_measured_improvement_and_admin_approval(
    client, curator_client, db,
):
    # Keep this test independent from modules that happen to seed the full
    # immutable history before it runs.
    seed_scoring_params(db)
    active = db.scalar(select(ScoringParams).where(
        ScoringParams.sport == "kitesurf", ScoringParams.active.is_(True)
    ).order_by(ScoringParams.version.desc()))
    assert active is not None
    base_version = active.version
    sample_size = get_settings().scoring_social_min_group_size

    no_improvement = client.post("/admin/scoring-calibration/proposals", json={
        "kind": "social_weight",
        "social_weight": 0.02,
        "evidence_source": "backtest",
        "baseline_metric": 0.6,
        "candidate_metric": 0.59,
        "sample_size": sample_size,
    })
    assert no_improvement.status_code == 409

    created = client.post("/admin/scoring-calibration/proposals", json={
        "kind": "social_weight",
        "social_weight": 0.02,
        "evidence_source": "backtest",
        "baseline_metric": 0.6,
        "candidate_metric": 0.64,
        "sample_size": sample_size,
    })
    assert created.status_code == 201, created.text
    proposal_id = created.json()["id"]
    assert created.json()["evidence"]["measured_improvement"] > 0

    forbidden = curator_client.post(
        f"/admin/scoring-calibration/proposals/{proposal_id}/approve",
        json={"note": "curator must not activate"},
    )
    assert forbidden.status_code == 403

    approved = client.post(
        f"/admin/scoring-calibration/proposals/{proposal_id}/approve",
        json={"note": "fixture comparison"},
    )
    assert approved.status_code == 200, approved.text
    activated_version = approved.json()["activated_params_version"]
    assert activated_version > base_version
    db.expire_all()
    activated = db.scalar(select(ScoringParams).where(
        ScoringParams.sport == "kitesurf", ScoringParams.version == activated_version
    ))
    assert activated is not None
    assert activated.active is True
    assert activated.params["social"]["validated"] is True
    assert seed_scoring_params(db) == 0
    db.expire_all()
    assert db.scalar(select(ScoringParams).where(
        ScoringParams.sport == "kitesurf", ScoringParams.version == activated_version
    )).active is True

    # Restore the shared seeded state for the remaining database tests.
    db.execute(delete(ScoringCalibrationProposal).where(
        ScoringCalibrationProposal.id == uuid.UUID(proposal_id)
    ))
    db.execute(delete(ScoringParams).where(
        ScoringParams.sport == "kitesurf",
        ScoringParams.version == activated_version,
    ))
    db.execute(update(ScoringParams).where(
        ScoringParams.sport == "kitesurf"
    ).values(active=False))
    db.execute(update(ScoringParams).where(
        ScoringParams.sport == "kitesurf",
        ScoringParams.version == base_version,
    ).values(active=True))
    db.commit()
