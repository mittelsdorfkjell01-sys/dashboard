"""Human-review evidence remains descriptive and never grants station roles."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import WeatherStationApprovalAudit
from app.weather.station_epochs import configuration_from_station, ensure_epoch
from app.weather.station_qualification import persist_dossier
from app.weather.station_report import station_report
from tests.test_station_qualification import _row, _station
from tests.station_qualification_fixture import persist_operational_fixture


def test_review_queue_exposes_evidence_questions_and_unapproved_role_candidates(db):
    station = _station(db)
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    persist_operational_fixture(
        db,
        station,
        [
            _row(station, end - timedelta(minutes=20), end - timedelta(minutes=18)),
            _row(station, end - timedelta(minutes=10), end - timedelta(minutes=8)),
        ],
        dry_run=False,
    )
    _, dossier_hash = persist_dossier(
        db, station, end=end, window_days=28, dry_run=False
    )

    report = station_report(db, now=end)
    item = next(
        row for row in report["station_review_queue"]
        if row["station_id"] == str(station.id)
    )
    assert item["dossier_hash"] == dossier_hash
    assert item["epoch"]["configuration_hash"]
    assert item["epoch"]["known_epochs_for_station"] == 1
    assert item["measurement_height_m"] == 10
    assert item["measurement_height_evidence"]["status"] == "unproven_or_unknown"
    assert "confirm_physical_station_identity" in item["open_questions"]
    assert "confirm_correlation_group_independence" in item["open_questions"]
    assert item["proposed_roles_for_human_review"] == ["monitoring"]
    assert item["role_proposal_is_approval"] is False
    assert item["remaining_days_to_unapproved_28_day_proposal"] > 27
    assert report["independent_holdout_target_groups"] == 0
    assert report["independent_holdout_input_groups"] == 0
    assert db.scalars(select(WeatherStationApprovalAudit).where(
        WeatherStationApprovalAudit.station_id == station.id
    )).all() == []


def test_review_queue_keeps_unknown_measurement_height_as_visible_blocker(db):
    station = _station(db)
    station.measurement_height_m = None
    ensure_epoch(
        db,
        station,
        configuration_from_station(station),
        first_seen_at=datetime.now(timezone.utc),
    )
    db.commit()
    report = station_report(db)
    item = next(
        row for row in report["station_review_queue"]
        if row["station_id"] == str(station.id)
    )
    assert item["measurement_height_known"] is False
    assert "obtain_official_individual_wind_measurement_height" in item["open_questions"]
    assert not set(item["proposed_roles_for_human_review"]).intersection(
        {"residual_source", "holdout_input", "holdout_target"}
    )
