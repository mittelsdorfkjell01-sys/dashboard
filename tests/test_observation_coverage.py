from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.weather.coverage import build_coverage_report

NOW = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)


def station(identifier, *, provider="dwd", country="DE", **patch):
    values = dict(
        id=identifier,
        provider=provider,
        provider_station_id=identifier,
        country_code=country,
        active=True,
        latitude=54.0,
        longitude=10.0,
        elevation_m=5,
        measurement_height_m=10,
        wigos_id=None,
        icao_id=None,
        license="CC BY 4.0",
        provenance={"commercial_reuse": True},
    )
    values.update(patch)
    return SimpleNamespace(**values)


def observation(station_id, minutes, delay=2):
    observed = NOW - timedelta(minutes=minutes)
    return SimpleNamespace(
        station_id=station_id,
        observed_at=observed,
        received_at=observed + timedelta(minutes=delay),
    )


def test_coverage_reports_country_timing_missing_metadata_duplicates_and_errors():
    german = station("de-1", icao_id="EDDH")
    duplicate = station(
        "de-alias", provider="awc_metar", icao_id="EDDH", license="WMO Core Data"
    )
    french = station(
        "fr-1", provider="awc_metar", country="FR", latitude=49, longitude=2,
        elevation_m=None, measurement_height_m=None, license="WMO Core Data",
    )
    observations = [
        observation("de-1", 20), observation("de-1", 10),
        observation("fr-1", 65, delay=5), observation("fr-1", 5, delay=5),
    ]
    state = SimpleNamespace(
        station_id="fr-1", provider="awc_metar", status="error",
        error_class="ProviderBackoffError", last_error_at=NOW,
        consecutive_failures=2,
    )
    report = build_coverage_report(
        [german, duplicate, french], observations, [state], now=NOW
    )
    assert report["active_station_records"] == 3
    assert report["active_unique_stations"] == 2
    assert report["active_wind_stations_by_country"] == {"DE": 1, "FR": 1}
    assert report["duplicates"] == [["dwd:DE-1", "awc_metar:DE-ALIAS"]]
    assert report["missing_elevation"] == ["awc_metar:FR-1"]
    assert report["missing_measurement_height"] == ["awc_metar:FR-1"]
    assert report["providers"]["dwd"]["typical_interval_minutes"] == 10
    assert report["providers"]["awc_metar"]["typical_interval_minutes"] == 60
    assert report["providers"]["awc_metar"]["typical_delay_minutes"] == 5
    assert report["current_import_errors"][0]["error_class"] == "ProviderBackoffError"
