"""Persistent provider HTTP and catalog scheduling regressions."""

from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.models import WeatherProviderHttpResource
from app.weather.provider_http import fetch_validated_resource
from app.weather.station_catalog_job import run_station_catalog_refresh


URL = "https://opendata.dwd.de/test-resource.zip"


def _response(status: int, body: bytes = b"", **headers):
    return httpx.Response(
        status,
        content=body,
        headers=headers,
        request=httpx.Request("GET", URL),
    )


def test_validator_survives_commit_and_304_is_not_new_evidence(db):
    url = f"{URL}?case=restart"
    calls = []

    def first_get(_url, **kwargs):
        calls.append(kwargs["headers"])
        return _response(
            200, b"validated-body", ETag='"v1"',
            **{"Last-Modified": "Sat, 19 Sep 2026 00:00:00 GMT"},
        )

    first = fetch_validated_resource(
        db, provider="dwd", url=url,
        request_variant={"station": "00427"},
        validate=lambda body, _received: body.decode(),
        reuse_cached_on_304=False, http_get=first_get,
    )
    db.commit()
    db.expire_all()
    assert first.value == "validated-body" and calls == [{}]

    def second_get(_url, **kwargs):
        calls.append(kwargs["headers"])
        return _response(304)

    second = fetch_validated_resource(
        db, provider="dwd", url=url,
        request_variant={"station": "00427"},
        validate=lambda body, _received: body.decode(),
        reuse_cached_on_304=False, http_get=second_get,
    )
    db.commit()
    assert second.not_modified and second.value is None
    assert second.received_at == first.received_at
    assert calls[-1] == {
        "If-None-Match": '"v1"',
        "If-Modified-Since": "Sat, 19 Sep 2026 00:00:00 GMT",
    }
    stored = db.scalar(select(WeatherProviderHttpResource).where(
        WeatherProviderHttpResource.resource_url == url
    ))
    assert stored.last_status_code == 304
    assert stored.response_received_at == first.received_at


def test_304_with_corrupt_payload_forces_unconditional_recovery(db):
    url = f"{URL}?case=corrupt"
    state = WeatherProviderHttpResource(
        provider="dwd", resource_url=url,
        request_variant_hash=(
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
        ),
        request_variant={}, etag='"old"', payload=b"corrupt",
        payload_sha256="0" * 64, payload_size_bytes=999,
        response_received_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
        last_checked_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
        last_status_code=200,
    )
    db.add(state)
    db.commit()
    replies = iter([
        _response(304),
        _response(200, b"recovered", ETag='"new"'),
    ])
    headers = []

    def get(_url, **kwargs):
        headers.append(kwargs["headers"])
        return next(replies)

    result = fetch_validated_resource(
        db, provider="dwd", url=url,
        validate=lambda body, _received: body.decode(), http_get=get,
    )
    db.commit()
    assert result.value == "recovered" and not result.not_modified
    assert headers == [{}, {}]
    db.refresh(state)
    assert state.payload == b"recovered" and state.etag == '"new"'


def test_provider_without_validators_uses_safe_unconditional_fallback(db):
    url = f"{URL}?case=no-validators"
    seen = []

    def get(_url, **kwargs):
        seen.append(kwargs["headers"])
        return _response(200, b"same")

    for _ in range(2):
        fetch_validated_resource(
            db, provider="dwd", url=url,
            validate=lambda body, _received: body, http_get=get,
        )
        db.commit()
    assert seen == [{}, {}]
    state = db.scalar(select(WeatherProviderHttpResource).where(
        WeatherProviderHttpResource.resource_url == url
    ))
    assert state.etag is None and state.last_modified is None


def test_catalog_provider_failure_does_not_block_other_provider(db, monkeypatch):
    from app.weather import station_catalog_job

    monkeypatch.setattr(station_catalog_job, "_pilot_spots", lambda *a, **k: [])

    def refresh(_db, provider, _spots, **_kwargs):
        if provider == "dwd":
            raise httpx.ConnectError("offline")
        return {
            "provider": provider, "status": "success", "catalog_records": 2,
            "active_records": 2, "inactive_records": 0,
            "selected_candidates": 0, "retirements": 0,
            "metadata_errors": 0, "persistence": {"dry_run": True},
        }

    monkeypatch.setattr(station_catalog_job, "_refresh_provider", refresh)
    report = run_station_catalog_refresh(
        db, providers=("dwd", "dmi"), dry_run=True, force=True
    )
    assert report["providers"]["dwd"]["status"] == "error"
    assert report["providers"]["dwd"]["error_class"] == "ConnectError"
    assert report["providers"]["dmi"]["status"] == "success"


def test_station_catalog_cron_is_authenticated_and_uses_shared_job(
    anon_client, monkeypatch
):
    from app.config import get_settings
    from app.weather import station_catalog_job

    monkeypatch.setattr(get_settings(), "cron_secret", "catalog-test-secret")
    called = []

    def refresh(db, *, dry_run):
        called.append((db is not None, dry_run))
        return {"status": "success", "providers": {}}

    monkeypatch.setattr(station_catalog_job, "run_station_catalog_refresh", refresh)
    assert anon_client.get("/cron/station-catalog").status_code == 401
    assert anon_client.post("/cron/station-catalog").status_code == 405
    response = anon_client.get(
        "/cron/station-catalog",
        headers={"Authorization": "Bearer catalog-test-secret"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success", "providers": {}}
    assert called == [(True, False)]
