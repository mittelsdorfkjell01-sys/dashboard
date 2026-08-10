from datetime import timezone

import pytest

from app.weather.providers.common import ObservationStation, haversine_km, nearest_stations
from app.weather.providers.dmi import fetch_recent, fetch_stations
from app.weather.providers.dwd import parse_station_catalog
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
                       "stationHeight": 4, "parameterId": ["wind_speed", "wind_dir"]},
    }]})
    station = fetch_stations()[0]
    assert station.station_id == "06123" and station.elevation_m == 4


def test_dmi_observations_are_joined_by_timestamp(monkeypatch):
    features = []
    for parameter, value in (("wind_speed", 7.2), ("wind_dir", 245), ("wind_max", 10.4)):
        features.append({"properties": {"parameterId": parameter, "observed": "2026-08-10T12:00:00Z", "value": value}})
    monkeypatch.setattr("app.weather.providers.dmi._get", lambda *a, **k: {"features": features})
    row = fetch_recent("06123")[0]
    assert row.observed_at.tzinfo == timezone.utc
    assert (row.wind_speed_ms, row.wind_direction_deg, row.wind_gust_ms) == (7.2, 245, 10.4)


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
