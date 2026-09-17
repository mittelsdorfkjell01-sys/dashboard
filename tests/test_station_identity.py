from types import SimpleNamespace

from app.weather.station_identity import duplicate_station_groups


def station(identifier, *, provider="dwd", lat=54.0, lon=10.0, elevation=5, **patch):
    values = dict(
        provider=provider,
        provider_station_id=identifier,
        wigos_id=None,
        icao_id=None,
        latitude=lat,
        longitude=lon,
        elevation_m=elevation,
    )
    values.update(patch)
    return SimpleNamespace(**values)


def test_station_duplicates_use_provider_icao_wigos_and_spatial_identity():
    rows = [
        station("same"),
        station("same", lat=55, lon=11),
        station("icao-a", provider="dmi", lat=56, lon=12, icao_id="EKXX"),
        station("icao-b", provider="awc_metar", lat=57, lon=13, icao_id="EKXX"),
        station("wigos-a", lat=58, lon=14, wigos_id="0-20000-0-12345"),
        station("wigos-b", provider="dmi", lat=59, lon=15, wigos_id="0-20000-0-12345"),
        station("spatial-a", lat=60, lon=16, elevation=12),
        station("spatial-b", provider="awc_metar", lat=60.0003, lon=16.0003, elevation=15),
    ]
    groups = {frozenset(group) for group in duplicate_station_groups(rows)}
    assert groups == {
        frozenset({0, 1}),
        frozenset({2, 3}),
        frozenset({4, 5}),
        frozenset({6, 7}),
    }


def test_spatial_proximity_without_elevation_requires_near_identical_coordinates():
    close = station("close", lat=54, lon=10, elevation=None)
    too_uncertain = station(
        "uncertain", provider="awc_metar", lat=54.0015, lon=10, elevation=None
    )
    assert duplicate_station_groups([close, too_uncertain]) == []
