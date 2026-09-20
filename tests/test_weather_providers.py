from datetime import datetime, timedelta, timezone
import io
import zipfile

import pytest

from app.weather.providers.common import ObservationStation, haversine_km, nearest_stations
from app.weather.providers.dmi import fetch_recent, fetch_stations
from app.weather.providers.dwd import parse_now_zip, parse_station_catalog
from app.weather.providers.knmi import KnmiOpenDataClient


def test_station_matching_filters_non_wind_and_radius():
    stations = [
        ObservationStation("x", "near", "Near", 54.01, 10.0, parameters=("wind_speed",)),
        ObservationStation("x", "temp", "Temperature", 54.0, 10.0, parameters=("temp_dry",)),
        ObservationStation("x", "far", "Far", 60.0, 10.0, parameters=("wind_speed",)),
    ]
    result = nearest_stations(54.0, 10.0, stations, max_km=50)
    assert [item.station_id for item, _ in result] == ["near"]
    assert haversine_km(54.0, 10.0, 54.01, 10.0) == pytest.approx(1.11, rel=0.02)


def test_dmi_station_parser(monkeypatch):
    monkeypatch.setattr("app.weather.providers.dmi._get", lambda *a, **k: {"features": [{
        "geometry": {"coordinates": [10.1, 55.2]},
        "properties": {"stationId": "06123", "name": "Coast", "status": "Active",
                       "stationHeight": 4, "measurementHeight": 10,
                       "wigosId": "0-20000-0-06123", "icaoId": "EKXX",
                       "parameterId": ["wind_speed", "wind_dir"]},
    }]})
    station = fetch_stations()[0]
    assert station.station_id == "06123" and station.elevation_m == 4
    assert station.wigos_id == "0-20000-0-06123" and station.icao_id == "EKXX"
    assert station.measurement_height_m == 10
    assert station.license == "CC BY 4.0"
    assert station.country_code is None  # source fixture has no country field
    assert station.commercial_reuse is True
    assert station.attribution_required is True


def test_dmi_observations_are_joined_by_timestamp(monkeypatch):
    features = []
    for parameter, value in (("wind_speed", 7.2), ("wind_dir", 245), ("wind_max", 10.4)):
        features.append({"properties": {
            "parameterId": parameter,
            "observed": "2026-08-10T14:00:00+02:00",
            "value": value,
            "quality": "good",
        }})
    monkeypatch.setattr("app.weather.providers.dmi._get", lambda *a, **k: {"features": features})
    row = fetch_recent("06123")[0]
    assert row.observed_at.tzinfo == timezone.utc
    assert row.observed_at.hour == 12
    assert (row.wind_speed_ms, row.wind_direction_deg, row.wind_gust_ms) == (7.2, 245, 10.4)
    assert row.station_identity == "dmi:06123"
    assert row.wind_u_ms is not None and row.wind_v_ms is not None
    assert row.gust_period_seconds == 600
    assert row.measurement_height_m is None  # no per-sensor height in response
    assert row.provider_quality == "good"
    assert row.received_at.tzinfo == timezone.utc
    assert row.imported_at.tzinfo == timezone.utc
    assert len(row.raw_payload["features"]) == 3


def test_dmi_malformed_relevant_observation_is_quarantined(monkeypatch):
    feature = {"properties": {
        "parameterId": "wind_speed",
        "observed": "not-a-date",
        "value": "broken",
        "quality": "suspect",
    }}
    monkeypatch.setattr(
        "app.weather.providers.dmi._get", lambda *a, **k: {"features": [feature]}
    )
    rows = fetch_recent("06123")
    assert len(rows) == 1
    assert rows[0].import_status == "quarantined"
    assert "provider_parse:invalid" in rows[0].data_issues
    assert rows[0].raw_payload == feature


def _dwd_zip(csv_text: str) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("produkt_zehn_min_ff_test.txt", csv_text)
    return payload.getvalue()


def test_dwd_preserves_rejected_and_quarantined_rows_and_deduplicates():
    header = "STATIONS_ID;MESS_DATUM;QN;FF_10;DD_10;eor\n"
    valid = "00042;202608261200;1;7.5;360;eor\n"
    rejected = "00042;202608261210;2;-1;240;eor\n"
    malformed = "00042;bad-time;3;8.0;250;eor\n"
    rows = parse_now_zip(
        _dwd_zip(header + valid + valid + rejected + malformed),
        fetched_at=datetime(2026, 8, 26, 12, 20, tzinfo=timezone.utc),
    )
    assert len(rows) == 3
    assert [row.import_status for row in rows].count("accepted") == 1
    assert [row.import_status for row in rows].count("rejected") == 1
    assert [row.import_status for row in rows].count("quarantined") == 1
    assert all(row.license == "CC BY 4.0" for row in rows)
    assert any(row.raw_payload["MESS_DATUM"] == "bad-time" for row in rows)
    accepted = next(row for row in rows if row.import_status == "accepted")
    assert accepted.wind_direction_deg == 0


def test_dwd_delayed_publication_preserves_real_receipt_latency():
    rows = parse_now_zip(
        _dwd_zip(
            "STATIONS_ID;MESS_DATUM;QN;FF_10;DD_10;eor\n"
            "00042;202609201200;1;7.5;270;eor\n"
        ),
        station_id="00042",
        fetched_at=datetime(2026, 9, 20, 12, 34, tzinfo=timezone.utc),
    )

    assert len(rows) == 1
    assert rows[0].received_at - rows[0].observed_at == timedelta(minutes=34)
    assert rows[0].import_status == "accepted"


def test_knmi_key_is_required():
    with pytest.raises(ValueError):
        KnmiOpenDataClient(" ")


def test_dwd_station_catalog_keeps_current_wind_stations():
    text = (
        "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\n"
        "00011 19920917 20260810            680     47.9736    8.5205 Donaueschingen (Landeplatz)              Baden-Wuerttemberg Frei\n"
        "00012 19920917 20200101             10     50.0000   10.0000 Old Station                              Hessen Frei\n"
    )
    rows = parse_station_catalog(text, today="20260810")
    assert len(rows) == 1
    assert rows[0].station_id == "00011" and rows[0].elevation_m == 680
    assert rows[0].country_code == "DE"
    assert rows[0].commercial_reuse is True
