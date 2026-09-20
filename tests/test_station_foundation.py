from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import io
import zipfile
import uuid
import httpx
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.weather.observation_quality import evaluate_observation
from app.weather.providers.common import normalize_observation
from app.weather.station_approval import decide_station_scope
from app.weather.station_identity import duplicate_station_groups, spatial_duplicate_candidates
from app.weather.providers import dwd, dmi
from app.weather.providers.common import ObservationStation
from app.weather.observation_worker import catalog_candidates, sync_catalog_candidates
from app.weather.observation_worker import import_station
from app.weather.observation_worker import persist_batch

NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


def source(**overrides):
    values = dict(provider="dwd", station_id="00042", observed_at=NOW,
                  received_at=NOW + timedelta(minutes=1), imported_at=NOW + timedelta(minutes=2),
                  wind_speed_ms=10, wind_direction_deg=270,
                  measurement_period_seconds=600, averaging_period_seconds=600,
                  license="CC BY 4.0")
    values.update(overrides)
    return normalize_observation(**values)


def reviewed_station(**overrides):
    values = dict(active=True, blocked=False, approved=True, monitoring_approved=True,
                  residual_approved=True, holdout_target_approved=True,
                  holdout_input_approved=True, representativeness_status="passed",
                  identity_review_status="passed", physical_station_group="p-1",
                  correlation_group="c-1", measurement_height_m=10,
                  elevation_m=5, license="CC BY 4.0")
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("unit,raw", [("m/s", 10), ("km/h", 36), ("kt", 19.4384449244)])
def test_documented_units_and_meteorological_vector(unit, raw):
    row = source(wind_speed_ms=raw, original_speed_unit=unit)
    assert row.wind_speed_ms == pytest.approx(10, rel=1e-5)
    assert row.wind_u_ms == pytest.approx(10, rel=1e-5)
    assert row.wind_v_ms == pytest.approx(0, abs=1e-9)
    assert row.original_speed == raw and row.original_speed_unit == unit


def test_calm_missing_direction_and_gust_are_independent():
    calm = source(wind_speed_ms=0, wind_direction_deg=None, wind_gust_ms=7)
    assert calm.wind_direction_deg is None
    assert (calm.wind_u_ms, calm.wind_v_ms) == (0, 0)
    assert calm.wind_gust_ms == 7
    missing = source(wind_direction_deg=None)
    assert missing.wind_u_ms is None and missing.import_status == "rejected"


def test_missing_receipt_is_quarantined_not_backdated():
    row = source(received_at=None)
    assert row.import_status == "quarantined"
    assert "received_at:unproven" in row.data_issues


def test_nonstation_sources_and_bad_units_fail_closed():
    for provider in ("open_meteo", "era5", "forecast"):
        assert source(provider=provider).import_status == "quarantined"
    assert source(original_speed_unit="mph").import_status == "rejected"


def test_dst_ambiguity_fails_closed_but_explicit_offset_is_utc():
    ambiguous = source(observed_at=datetime(2026, 10, 25, 2, 30))
    assert ambiguous.import_status == "quarantined"
    explicit = source(observed_at=datetime(2026, 9, 17, 14, tzinfo=timezone(timedelta(hours=2))))
    assert explicit.observed_at == NOW


def test_qc_flags_preserve_raw_and_gate_unreviewed_station():
    row = source(raw_payload={"FF_10": "10.0"})
    decision = evaluate_observation(row, reviewed_station(identity_review_status="unreviewed"), now=NOW)
    assert decision.stage == "accepted_for_monitoring"
    assert "identity_unreviewed" in decision.reasons
    assert row.raw_payload == {"FF_10": "10.0"}


def test_cutoff_freshness_is_not_frozen_into_intrinsic_qc():
    row = source(observed_at=NOW - timedelta(hours=2), received_at=NOW)
    assert "observation_stale" not in evaluate_observation(
        row, reviewed_station(), now=NOW
    ).reasons
    current = source()
    prior = [SimpleNamespace(observed_at=NOW - timedelta(minutes=offset),
                             wind_u_ms=current.wind_u_ms, wind_v_ms=current.wind_v_ms)
             for offset in (40, 30, 20)]
    assert "sensor_stuck" in evaluate_observation(current, reviewed_station(), prior=prior, now=NOW).reasons


def test_spatial_proximity_only_proposes_review():
    left = SimpleNamespace(provider="dwd", provider_station_id="1", wigos_id=None, icao_id=None,
                           latitude=54, longitude=10, elevation_m=5)
    right = SimpleNamespace(provider="dmi", provider_station_id="2", wigos_id=None, icao_id=None,
                            latitude=54.0001, longitude=10.0001, elevation_m=5)
    assert duplicate_station_groups([left, right]) == []
    assert spatial_duplicate_candidates([left, right]) == [(0, 1)]
    right.wigos_id = left.wigos_id = "0-20000-0-12345"
    assert duplicate_station_groups([left, right]) == []
    left.sensor_metadata = right.sensor_metadata = {"sensor_instance_id": "wind-1",
                                                     "official_crosswalk": True}
    assert duplicate_station_groups([left, right]) == [(0, 1)]


def test_manual_scope_rejects_missing_identity_or_metadata():
    station = reviewed_station(identity_review_status="unreviewed")
    with pytest.raises(ValueError, match="authenticated_admin_reviewer_required"):
        decide_station_scope(SimpleNamespace(), station, scope="residual", approved=True,
                             actor="reviewer", reason="checked")


def test_dwd_sensor_metadata_does_not_assume_ten_metres():
    station = ObservationStation(provider="dwd", station_id="00042", name="Fixture",
                                 latitude=54, longitude=10)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("Metadaten_Geraete_Windgeschwindigkeit_Mittel_00042.txt",
                             "Von_Datum;Bis_Datum;Geberhoehe ueber Grund [m];Geraetetyp Name;Messverfahren;\n"
                             "20200101;20210101;10;old;electric;\n"
                             "20210102;99991231;13;new;electric;\n")
    parsed = dwd.parse_station_metadata_zip(stream.getvalue(), station)
    assert parsed.measurement_height_m == 13
    assert parsed.sensor_metadata["effective_from"] == "20210102"
    assert station.measurement_height_m is None


def test_dwd_expired_sensor_metadata_does_not_claim_current_height():
    station = ObservationStation(provider="dwd", station_id="00042", name="Fixture",
                                 latitude=54, longitude=10)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("Metadaten_Geraete_Windgeschwindigkeit_Mittel_00042.txt",
                         "Von_Datum;Bis_Datum;Geberhoehe ueber Grund [m];Geraetetyp Name;\n"
                         "20200101;20260917;13;old;\n")
    parsed = dwd.parse_station_metadata_zip(stream.getvalue(), station)
    assert parsed.measurement_height_m is None
    assert parsed.sensor_metadata["height_status"] == "metadata_interval_not_current"


def test_dwd_now_archive_name_and_times_parse_without_network():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("produkt_zehn_now_ff_20260917_20260917_00042.txt",
                             "STATIONS_ID;MESS_DATUM;QN;FF_10;DD_10;eor\n"
                             "42;202609171200;2;7.0;270;eor\n")
    rows = dwd.parse_now_zip(stream.getvalue(), station_id="00042", fetched_at=NOW)
    assert len(rows) == 1
    assert rows[0].provider_station_id == "00042"
    assert rows[0].import_status == "accepted"
    assert rows[0].averaging_period_seconds == 600


def test_dwd_conditional_request_reuses_persisted_etag(db, monkeypatch):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("produkt_zehn_now_ff_20260917_20260917_99999.txt",
                             "STATIONS_ID;MESS_DATUM;QN;FF_10;DD_10;eor\n"
                             "99999;202609171200;2;7.0;270;eor\n")
    seen = []
    def fake_get(url, *, headers, timeout, follow_redirects):
        seen.append(headers)
        request = httpx.Request("GET", url)
        if len(seen) == 1:
            return httpx.Response(200, request=request, content=stream.getvalue(),
                                  headers={"ETag": '"test-v1"'})
        return httpx.Response(304, request=request)
    monkeypatch.setattr(dwd.httpx, "get", fake_get)
    assert len(dwd.fetch_now("99999", db=db)) == 1
    db.commit()
    db.expire_all()
    assert dwd.fetch_now("99999", db=db) == []
    db.commit()
    assert seen == [{}, {"If-None-Match": '"test-v1"'}]


def test_rate_limit_does_not_immediately_retry():
    calls = []
    def throttled(_):
        calls.append(1)
        response = httpx.Response(429, request=httpx.Request("GET", "https://example.test"))
        response.raise_for_status()
    result = import_station(SimpleNamespace(provider_station_id="42"), throttled,
                            SimpleNamespace(), dry_run=True, attempts=3)
    assert result["error_class"] == "HTTPStatusError"
    assert len(calls) == 1


def test_dmi_catalog_uses_provider_country_and_keeps_sensor_height_unknown(monkeypatch):
    payload = {"features": [{"geometry": {"coordinates": [-53.5, 69.2]},
                            "properties": {"stationId": "04219", "status": "Active", "country": "GRL",
                                           "name": "Fixture GL", "parameterId": ["wind_speed", "wind_dir"],
                                           "stationHeight": 11}},
                           {"geometry": {"coordinates": [9.1, 54.9]},
                            "properties": {"stationId": "06116", "status": "Active", "country": "DNK",
                                           "name": "Fixture DK", "parameterId": ["wind_speed", "wind_dir"],
                                           "stationHeight": 15}},
                           {"geometry": {"coordinates": [8.6, 55.2]},
                            "properties": {"stationId": "06093", "status": "Active", "country": "DNK",
                                           "name": "Historical Active", "parameterId": ["wind_speed", "wind_dir"],
                                           "stationHeight": 3, "operationTo": "2024-06-27T00:00:00Z"}}]}
    monkeypatch.setattr(dmi, "_get", lambda *args, **kwargs: payload)
    stations = dmi.fetch_stations()
    assert {item.country_code for item in stations} == {"DK", "GL"}
    assert all(item.measurement_height_m is None for item in stations)
    assert next(item for item in stations if item.station_id == "06093").active is False


def test_catalog_metadata_revision_is_idempotent_and_drift_blocks_station(db):
    from geoalchemy2 import WKTElement
    from sqlalchemy import select
    from app.models import Region, Spot, WeatherStation, WeatherStationMetadataRevision

    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"meta-{suffix}", name="Metadata Fixture", country="DE", status="published")
    db.add(region)
    db.flush()
    spot = Spot(slug=f"meta-{suffix}", name="Metadata Fixture", region_id=region.id,
                location=WKTElement("POINT(10 54)", srid=4326), status="published",
                sports=["wind"], water_type=["sea"])
    db.add(spot)
    db.commit()
    target = SimpleNamespace(id=spot.id, latitude=54.0, longitude=10.0, elevation_m=None)
    candidate = ObservationStation(provider="dwd", station_id="00042", name="Fixture",
                                   latitude=54.01, longitude=10.0, elevation_m=6,
                                   measurement_height_m=13, license="CC BY 4.0",
                                   country_code="DE", raw_payload={"sensor": "first"},
                                   received_at=NOW)
    try:
        values = catalog_candidates([target], [candidate])
        first = sync_catalog_candidates(db, values, dry_run=False)
        replay = sync_catalog_candidates(db, values, dry_run=False)
        assert first["metadata_revisions_persisted"] == 1
        assert replay["metadata_revisions_persisted"] == 0
        station = db.scalar(select(WeatherStation).where(WeatherStation.spot_id == spot.id))
        assert not station.approved and not station.residual_approved
        changed = ObservationStation(**{**candidate.__dict__, "latitude": 54.03,
                                        "raw_payload": {"sensor": "relocated"}})
        drift = sync_catalog_candidates(db, catalog_candidates([target], [changed]), dry_run=False)
        db.refresh(station)
        assert drift["metadata_drift"] == 1
        assert drift["metadata_revisions_persisted"] == 1
        assert station.blocked and station.latitude == 54.01
        assert len(db.scalars(select(WeatherStationMetadataRevision).where(
            WeatherStationMetadataRevision.station_id == station.id)).all()) == 2
    finally:
        for item in db.scalars(select(WeatherStation).where(WeatherStation.spot_id == spot.id)).all():
            db.delete(item)
        db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()


def test_parallel_replay_and_cross_spot_revision_identity(db):
    from geoalchemy2 import WKTElement
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models import Region, Spot, WeatherObservation, WeatherObservationRevision, WeatherStation

    suffix = uuid.uuid4().hex[:8]
    region = Region(slug=f"parallel-{suffix}", name="Parallel Fixture", country="DE", status="published")
    db.add(region)
    db.flush()
    spots = [Spot(slug=f"parallel-{suffix}-{index}", name=f"Parallel {index}", region_id=region.id,
                  location=WKTElement(f"POINT({10+index/10} 54)", srid=4326), status="published",
                  sports=["wind"], water_type=["sea"]) for index in range(2)]
    db.add_all(spots)
    db.flush()
    stations = [WeatherStation(spot_id=spot.id, provider="dwd", provider_station_id="00042",
                               latitude=54, longitude=10, active=True) for spot in spots]
    db.add_all(stations)
    db.commit()
    row = source()
    try:
        def replay(_):
            with SessionLocal() as session:
                station = session.get(WeatherStation, stations[0].id)
                return persist_batch(session, station, [row], dry_run=False)["persisted"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(replay, range(2)))
        assert sorted(results) == [0, 1]
        assert persist_batch(db, stations[1], [row], dry_run=False)["persisted"] == 1
        station_ids = [item.id for item in stations]
        assert len(db.scalars(select(WeatherObservation).where(
            WeatherObservation.station_id.in_(station_ids))).all()) == 2
        revisions = db.scalars(select(WeatherObservationRevision).where(
            WeatherObservationRevision.station_id.in_(station_ids))).all()
        assert len(revisions) == 2
        assert {item.station_id for item in revisions} == {item.id for item in stations}
    finally:
        for station in stations:
            db.delete(station)
        for spot in spots:
            db.delete(spot)
        db.flush()
        db.delete(region)
        db.commit()
