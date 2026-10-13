from datetime import datetime, timezone

from app.weather.providers import eumetnet_esoh as esoh


NOW = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)


def _feature(identifier: str = "0-20000-0-01001", *, lat=54.0, lon=10.0):
    return {
        "type": "Feature",
        "id": identifier,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "name": "Test station",
            "detail": f"https://oscar.wmo.int/{identifier}",
            "parameter-name": [
                "wind_speed:10.0:point:PT10M",
                "wind_from_direction:10.0:point:PT10M",
                "wind_speed_of_gust:10.0:maximum:PT10M",
            ],
        },
    }


def test_catalog_keeps_only_stations_with_comparable_ten_metre_wind_pair():
    incomplete = _feature("incomplete")
    incomplete["properties"]["parameter-name"] = ["wind_speed:10.0:point:PT10M"]
    rows = esoh.parse_station_catalog(
        {"features": [_feature(), incomplete]}, received_at=NOW
    )
    assert len(rows) == 1
    assert rows[0].wigos_id == "0-20000-0-01001"
    assert rows[0].license == "CC BY 4.0"
    assert rows[0].sensor_metadata["esoh_wind"] == {
        "speed_parameter": "wind_speed:10.0:point:PT10M",
        "direction_parameter": "wind_from_direction:10.0:point:PT10M",
        "gust_parameter": "wind_speed_of_gust:10.0:maximum:PT10M",
        "method": "point",
        "period": "PT10M",
        "period_seconds": 600,
        "measurement_height_m": 10.0,
    }


def test_recent_coverages_are_joined_by_exact_observation_time(monkeypatch):
    parameters = esoh.select_wind_parameters(_feature()["properties"]["parameter-name"])
    speed, direction, gust = (
        parameters["speed_parameter"],
        parameters["direction_parameter"],
        parameters["gust_parameter"],
    )

    def coverage(_station_id, parameter, **_kwargs):
        values = {
            speed: [5.0, 6.0],
            direction: [270.0, 280.0],
            gust: [7.0, 8.0],
        }[parameter]
        return {
            "domain": {"axes": {"t": {"values": [
                "2026-10-12T14:40:00Z", "2026-10-12T14:50:00Z"
            ]}}},
            "ranges": {parameter: {"values": values}},
        }

    monkeypatch.setattr(esoh, "_fetch_coverage", coverage)
    rows = esoh.fetch_recent(
        "0-20000-0-01001", sensor_metadata={"esoh_wind": parameters}, now=NOW
    )
    assert len(rows) == 2
    assert rows[0].provider == "eumetnet_esoh"
    assert rows[0].wind_speed_ms == 5.0
    assert rows[0].wind_direction_deg == 270.0
    assert rows[0].wind_gust_ms == 7.0
    assert rows[0].measurement_period_seconds == 600
    assert rows[0].import_status == "accepted"
