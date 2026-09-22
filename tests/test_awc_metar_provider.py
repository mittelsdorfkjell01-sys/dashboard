import json
import gzip
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.weather.providers.awc_metar import (
    AWC_LICENSE,
    AWC_USER_AGENT,
    AwcMetarClient,
    ProviderBackoffError,
    parse_metars,
    parse_station_catalog,
)
from app.weather.vectors import uv_to_wind

FIXTURES = Path(__file__).parent / "fixtures" / "weather"


def _fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_awc_fixture_normalizes_knots_identity_times_and_vector():
    received = datetime(2026, 8, 26, 12, 23, tzinfo=timezone.utc)
    row = parse_metars(
        _fixture("awc_metar.json"), station_id="EDDH", received_at=received
    )[0]
    assert row.provider == "awc_metar"
    assert row.provider_station_id == "EDDH"
    assert row.icao_id == "EDDH"
    assert row.observed_at == datetime(2026, 8, 26, 12, 20, tzinfo=timezone.utc)
    assert row.received_at == received
    assert row.wind_speed_ms == pytest.approx(6 * 0.514444)
    assert row.wind_gust_ms == pytest.approx(11 * 0.514444)
    speed, direction = uv_to_wind(row.wind_u_ms, row.wind_v_ms)
    assert speed == pytest.approx(row.wind_speed_ms)
    assert direction == pytest.approx(290)
    assert row.provider_quality == "awc_qc:2"
    assert row.gust_period_seconds is None
    assert row.measurement_height_m is None
    assert row.license == AWC_LICENSE
    assert row.import_status == "accepted"


def test_awc_station_fixture_is_europe_only_and_reports_missing_sensor_height():
    stations = parse_station_catalog(_fixture("awc_stations.json"))
    assert [station.station_id for station in stations] == ["EDDH", "LFPG"]
    assert {station.country_code for station in stations} == {"DE", "FR"}
    assert all(station.commercial_reuse is False for station in stations)
    assert all(station.attribution_required is True for station in stations)
    assert all(station.measurement_height_m is None for station in stations)
    assert all(station.license == AWC_LICENSE for station in stations)


def test_awc_client_sends_identity_and_reuses_etag_payload():
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json=[{"icaoId": "EDDH"}], headers={"ETag": '"v1"'})
        assert request.headers["If-None-Match"] == '"v1"'
        return httpx.Response(304)

    client = AwcMetarClient(transport=httpx.MockTransport(handler))
    try:
        first = client.get_json("https://example.test/metar", params={"ids": "EDDH"})
        second = client.get_json("https://example.test/metar", params={"ids": "EDDH"})
    finally:
        client.close()
    assert first == second == [{"icaoId": "EDDH"}]
    assert requests[0].headers["User-Agent"] == AWC_USER_AGENT


def test_awc_client_enters_non_blocking_backoff_after_rate_limit():
    current = datetime(2026, 8, 26, 12, tzinfo=timezone.utc)
    calls = 0

    def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "120"})

    client = AwcMetarClient(
        transport=httpx.MockTransport(handler), now=lambda: current
    )
    try:
        with pytest.raises(ProviderBackoffError, match="awc_http_429"):
            client.get_json("https://example.test/metar")
        with pytest.raises(ProviderBackoffError, match="awc_backoff_active"):
            client.get_json("https://example.test/metar")
    finally:
        client.close()
    assert calls == 1


def test_awc_client_decodes_official_gzip_cache_shape():
    payload = _fixture("awc_stations.json")

    def handler(_request: httpx.Request):
        return httpx.Response(200, content=gzip.compress(json.dumps(payload).encode()))

    client = AwcMetarClient(transport=httpx.MockTransport(handler))
    try:
        result = client.get_json("https://example.test/stations.json.gz", gzip_payload=True)
    finally:
        client.close()
    assert result == payload
