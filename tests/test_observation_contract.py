from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.weather.observations import public_measurement
from app.weather.observation_worker import import_station
from app.weather.providers.common import deduplicate_observations, normalize_observation
from app.weather.vectors import uv_to_wind

NOW = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)


def station(**patch):
    data = dict(active=True, approved=True, blocked=False, representativeness_status="passed")
    data.update(patch)
    return SimpleNamespace(**data)


def observation(**patch):
    data = dict(observed_at=NOW-timedelta(minutes=10), wind_speed_ms=8.0,
                wind_gust_ms=11.0, wind_direction_deg=240.0,
                provider_quality="good", import_status="accepted")
    data.update(patch)
    return SimpleNamespace(**data)


@pytest.mark.parametrize("patch,reason", [
    ({"observed_at": NOW-timedelta(minutes=31)}, "observation_stale"),
    ({"observed_at": NOW+timedelta(minutes=3)}, "observation_future"),
    ({"wind_direction_deg": 360}, "wind_direction_invalid"),
    ({"wind_gust_ms": 7}, "gust_below_wind"),
])
def test_public_measurement_rejects_invalid_inputs(patch, reason):
    eligible, reasons = public_measurement(station(), observation(**patch), now=NOW)
    assert not eligible and reason in reasons


def test_unapproved_station_never_replaces_model():
    assert public_measurement(station(approved=False), observation(), now=NOW)[0] is False


def test_normalized_contract_keeps_provider_capture_and_problems():
    row = normalize_observation(provider="dmi", station_id="x", observed_at=NOW,
                                wind_speed_ms=8, wind_direction_deg=400,
                                wind_gust_ms=7, provider_quality="suspect", fetched_at=NOW)
    assert row.provider == "dmi" and row.fetched_at == NOW
    assert row.import_status == "rejected"
    assert {"wind_direction:invalid", "wind_gust:invalid"} <= set(row.data_issues)


def test_normalized_contract_separates_all_utc_instants_and_computes_vector():
    local_time = datetime(2026, 8, 26, 14, tzinfo=timezone(timedelta(hours=2)))
    received = NOW + timedelta(minutes=2)
    imported = NOW + timedelta(minutes=3)
    row = normalize_observation(
        provider="DMI",
        station_id="06123",
        observed_at=local_time,
        received_at=received,
        imported_at=imported,
        wind_speed_ms=8,
        wind_direction_deg=270,
        wind_gust_ms=10,
        gust_period_seconds=600,
        wigos_id="0-20000-0-06123",
        icao_id="EKXX",
        latitude=55.2,
        longitude=10.1,
        elevation_m=4,
        measurement_height_m=10,
        license="CC BY 4.0",
        provenance={"collection": "metObs"},
    )
    assert row.station_identity == "dmi:06123"
    assert row.observed_at == NOW
    assert row.received_at == received
    assert row.imported_at == imported
    assert row.received_at is not row.imported_at
    speed, direction = uv_to_wind(row.wind_u_ms, row.wind_v_ms)
    assert speed == pytest.approx(row.wind_speed_ms)
    assert direction == pytest.approx(row.wind_direction_deg)
    assert row.gust_period_seconds == 600
    assert row.import_status == "accepted"


def test_naive_and_future_observations_are_quarantined_not_dropped():
    naive = normalize_observation(
        provider="dwd",
        station_id="00042",
        observed_at=NOW.replace(tzinfo=None),
        received_at=NOW,
        imported_at=NOW,
        wind_speed_ms=7,
        wind_direction_deg=180,
        raw_payload={"FF_10": "7", "MESS_DATUM": "bad-zone"},
    )
    future = normalize_observation(
        provider="dwd",
        station_id="00042",
        observed_at=NOW + timedelta(minutes=6),
        received_at=NOW,
        imported_at=NOW,
        wind_speed_ms=7,
        wind_direction_deg=180,
    )
    assert naive.import_status == "quarantined"
    assert naive.rejection_reason == "observed_at:naive"
    assert naive.raw_payload["MESS_DATUM"] == "bad-zone"
    assert future.import_status == "quarantined"
    assert future.rejection_reason == "observed_at:future"


def test_late_observation_is_accepted_but_explicitly_flagged():
    row = normalize_observation(
        provider="dwd",
        station_id="00042",
        observed_at=NOW - timedelta(hours=2),
        received_at=NOW,
        imported_at=NOW,
        wind_speed_ms=7,
        wind_direction_deg=180,
    )
    assert row.import_status == "accepted"
    assert row.rejection_reason is None
    assert row.data_issues == ("observed_at:late",)


def test_non_calm_wind_requires_direction_but_calm_has_zero_vector():
    missing = normalize_observation(
        provider="dwd", station_id="00042", observed_at=NOW,
        received_at=NOW, imported_at=NOW, wind_speed_ms=7,
    )
    calm = normalize_observation(
        provider="dwd", station_id="00042", observed_at=NOW,
        received_at=NOW, imported_at=NOW, wind_speed_ms=0,
    )
    assert missing.import_status == "rejected"
    assert missing.rejection_reason == "wind_direction:missing"
    assert calm.import_status == "accepted"
    assert (calm.wind_u_ms, calm.wind_v_ms) == (0.0, 0.0)


def test_deduplication_collapses_replay_and_quarantines_conflicts():
    base = dict(
        provider="dwd",
        station_id="00042",
        observed_at=NOW,
        received_at=NOW,
        imported_at=NOW,
        wind_direction_deg=180,
    )
    first = normalize_observation(**base, wind_speed_ms=7)
    replay = normalize_observation(**base, wind_speed_ms=7)
    assert deduplicate_observations([first, replay]) == [first]

    conflicting = normalize_observation(**base, wind_speed_ms=9)
    result = deduplicate_observations([first, conflicting])
    assert len(result) == 2
    assert all(row.import_status == "quarantined" for row in result)
    assert all("duplicate:conflict" in row.data_issues for row in result)


def test_persistence_is_idempotent_and_audits_invalid_rows(db):
    import uuid

    from geoalchemy2 import WKTElement
    from sqlalchemy import delete, select

    from app.models import (
        Region,
        Spot,
        WeatherObservation,
        WeatherObservationQuarantine,
        WeatherStation,
    )
    from app.weather.observation_worker import persist_batch

    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"obs-region-{suffix}",
        name=f"Observation {suffix}",
        normalized_name=f"observation {suffix}",
        country="DE",
        status="published",
    )
    db.add(region)
    db.flush()
    spot = Spot(
        slug=f"obs-spot-{suffix}",
        name=f"Observation Spot {suffix}",
        normalized_name=f"observation spot {suffix}",
        region_id=region.id,
        location=WKTElement("POINT(8.5 54.5)", srid=4326),
        sports=["wind"],
        water_type=["sea"],
        status="published",
    )
    db.add(spot)
    db.flush()
    station_row = WeatherStation(
        spot_id=spot.id,
        provider="dwd",
        provider_station_id="00042",
        latitude=54.5,
        longitude=8.5,
        active=True,
    )
    db.add(station_row)
    db.commit()

    received = datetime.now(timezone.utc)
    accepted_at = received - timedelta(minutes=2)
    rows = [
        normalize_observation(
            provider="dwd", station_id="00042", observed_at=accepted_at,
            received_at=received, imported_at=received + timedelta(seconds=1),
            wind_speed_ms=7.5, wind_direction_deg=245,
        ),
        normalize_observation(
            provider="dwd", station_id="00042",
            observed_at=accepted_at - timedelta(minutes=10),
            received_at=received, imported_at=received + timedelta(seconds=1),
            wind_speed_ms=-1, raw_payload={"FF_10": "-1"},
        ),
        normalize_observation(
            provider="dwd", station_id="00042",
            observed_at=received + timedelta(minutes=10),
            received_at=received, imported_at=received + timedelta(seconds=1),
            wind_speed_ms=8, raw_payload={"MESS_DATUM": "future"},
        ),
    ]
    try:
        first = persist_batch(db, station_row, rows, dry_run=False)
        second = persist_batch(db, station_row, rows, dry_run=False)
        assert first["persisted"] == 1
        assert first["rejected"] == 1 and first["quarantined"] == 1
        assert first["quarantine_persisted"] == 2
        assert second["persisted"] == 0
        assert second["quarantine_persisted"] == 0

        stored = db.scalar(select(WeatherObservation).where(
            WeatherObservation.station_id == station_row.id
        ))
        assert stored.received_at == received
        assert stored.imported_at == received + timedelta(seconds=1)
        speed, direction = uv_to_wind(stored.wind_u_ms, stored.wind_v_ms)
        assert speed == pytest.approx(7.5)
        assert direction == pytest.approx(245)

        conflict = normalize_observation(
            provider="dwd", station_id="00042", observed_at=accepted_at,
            received_at=received, imported_at=received + timedelta(seconds=2),
            wind_speed_ms=9, wind_direction_deg=245,
        )
        conflict_report = persist_batch(
            db, station_row, [conflict], dry_run=False
        )
        assert conflict_report["quarantined"] == 1
        assert conflict_report["quarantine_persisted"] == 1
        audit_rows = db.scalars(select(WeatherObservationQuarantine).where(
            WeatherObservationQuarantine.station_id == station_row.id
        )).all()
        assert len(audit_rows) == 3
        assert all(row.raw_payload is not None for row in audit_rows)
        assert any("duplicate:conflict" in row.data_issues for row in audit_rows)
    finally:
        db.execute(delete(WeatherObservationQuarantine).where(
            WeatherObservationQuarantine.station_id == station_row.id
        ))
        db.delete(station_row)
        db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()


def test_provider_failure_is_bounded_and_sanitized():
    calls = 0
    def fail(_station_id):
        nonlocal calls
        calls += 1
        raise RuntimeError("secret")
    report = import_station(SimpleNamespace(provider_station_id="x"), fail, object(), dry_run=True, attempts=2)
    assert calls == 2 and report["error_class"] == "RuntimeError"
    assert "secret" not in str(report)


def test_provider_failure_does_not_stop_other_sources(monkeypatch):
    from app.weather import observation_worker

    stations = [
        SimpleNamespace(
            id="awc", provider="awc_metar", provider_station_id="EDDH"
        ),
        SimpleNamespace(id="dwd", provider="dwd", provider_station_id="00042"),
    ]

    class Result:
        def all(self):
            return stations

    class Db:
        def scalars(self, _statement):
            return Result()

    calls = []

    def fake_import(station_row, _fetcher, _db, **_kwargs):
        calls.append(station_row.provider)
        if station_row.provider == "awc_metar":
            return {
                "persisted": 0, "accepted": 0, "rejected": 0,
                "quarantined": 0, "error_class": "ProviderBackoffError",
            }
        return {
            "persisted": 1, "accepted": 1, "rejected": 0,
            "quarantined": 0,
        }

    monkeypatch.setattr(
        observation_worker, "provider_fetchers", lambda: {
            "awc_metar": object(), "dwd": object()
        }
    )
    monkeypatch.setattr(observation_worker, "import_station", fake_import)
    report = observation_worker.run_observation_import(
        Db(), providers=("awc_metar", "dwd"), dry_run=True
    )
    assert calls == ["awc_metar", "dwd"]
    assert report["errors"] == 1
    assert report["persisted"] == 1
    assert report["provider_reports"]["dwd"]["accepted"] == 1


def test_import_state_records_sanitized_failure_and_recovery(db):
    import uuid

    from geoalchemy2 import WKTElement
    from sqlalchemy import select

    from app.models import Region, Spot, WeatherObservationImportState, WeatherStation

    suffix = uuid.uuid4().hex[:8]
    region = Region(
        slug=f"import-state-region-{suffix}", name=f"Import State {suffix}",
        normalized_name=f"import state {suffix}", country="DE", status="published",
    )
    db.add(region)
    db.flush()
    spot = Spot(
        slug=f"import-state-spot-{suffix}", name=f"Import State Spot {suffix}",
        normalized_name=f"import state spot {suffix}", region_id=region.id,
        location=WKTElement("POINT(8.5 54.5)", srid=4326), sports=["wind"],
        water_type=["sea"], status="published",
    )
    db.add(spot)
    db.flush()
    station_row = WeatherStation(
        spot_id=spot.id, provider="dwd", provider_station_id="00991",
        latitude=54.5, longitude=8.5, active=True,
    )
    db.add(station_row)
    db.commit()

    def fail(_station_id):
        raise RuntimeError("credential-that-must-not-be-stored")

    try:
        failed = import_station(station_row, fail, db, dry_run=False, attempts=2)
        assert failed["error_class"] == "RuntimeError"
        state = db.scalar(select(WeatherObservationImportState).where(
            WeatherObservationImportState.station_id == station_row.id
        ))
        assert state.status == "error"
        assert state.error_class == "RuntimeError"
        assert state.consecutive_failures == 1
        assert state.next_attempt_at > state.last_attempt_at
        assert "credential" not in str(state.last_counts)

        recovered = normalize_observation(
            provider="dwd", station_id="00991",
            observed_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            received_at=datetime.now(timezone.utc),
            imported_at=datetime.now(timezone.utc),
            wind_speed_ms=7, wind_direction_deg=180, provider_quality="1",
        )
        report = import_station(
            station_row, lambda _station_id: [recovered], db,
            dry_run=False, attempts=1,
        )
        assert report["persisted"] == 1
        db.refresh(state)
        assert state.status == "success"
        assert state.error_class is None
        assert state.consecutive_failures == 0
        assert state.next_attempt_at is None
        assert state.last_success_at is not None
    finally:
        db.delete(station_row)
        db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()
