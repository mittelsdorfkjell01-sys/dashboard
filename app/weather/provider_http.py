"""Transactional RFC 9110 conditional retrieval for provider resources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Callable, Generic, TypeVar

import httpx
from sqlalchemy import select, text

from app.models import WeatherProviderHttpResource


T = TypeVar("T")


@dataclass(frozen=True)
class ValidatedResource(Generic[T]):
    value: T | None
    not_modified: bool
    received_at: datetime
    validator_supported: bool
    payload_sha256: str


def _variant(values: dict | None) -> tuple[dict, str]:
    payload = values or {}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return payload, hashlib.sha256(encoded).hexdigest()


def _payload_valid(state: WeatherProviderHttpResource) -> bool:
    payload = bytes(state.payload)
    return (
        len(payload) == state.payload_size_bytes
        and hashlib.sha256(payload).hexdigest() == state.payload_sha256
    )


def fetch_validated_resource(
    db,
    *,
    provider: str,
    url: str,
    validate: Callable[[bytes, datetime], T],
    request_variant: dict | None = None,
    timeout: float = 20.0,
    reuse_cached_on_304: bool = True,
    http_get: Callable | None = None,
) -> ValidatedResource[T]:
    """Fetch and stage a validated representation in the caller transaction."""
    http_get = http_get or httpx.get
    variant, variant_hash = _variant(request_variant)
    lock_key = f"provider-http:{provider}:{url}:{variant_hash}"
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": lock_key},
    )
    state = db.scalar(
        select(WeatherProviderHttpResource).where(
            WeatherProviderHttpResource.provider == provider,
            WeatherProviderHttpResource.resource_url == url,
            WeatherProviderHttpResource.request_variant_hash == variant_hash,
        )
    )
    headers = {}
    if state is not None and _payload_valid(state):
        if state.etag:
            headers["If-None-Match"] = state.etag
        if state.last_modified:
            headers["If-Modified-Since"] = state.last_modified

    checked_at = datetime.now(timezone.utc)
    response = http_get(url, timeout=timeout, headers=headers, follow_redirects=True)
    if response.status_code == 304:
        if state is None or not _payload_valid(state) or not headers:
            response = http_get(
                url, timeout=timeout, headers={}, follow_redirects=True
            )
            if response.status_code == 304:
                raise ValueError("provider_304_without_valid_local_payload")
        else:
            value = validate(bytes(state.payload), state.response_received_at)
            state.last_checked_at = checked_at
            state.last_not_modified_at = checked_at
            state.last_status_code = 304
            state.etag = response.headers.get("ETag") or state.etag
            state.last_modified = (
                response.headers.get("Last-Modified") or state.last_modified
            )
            state.updated_at = checked_at
            return ValidatedResource(
                value=value if reuse_cached_on_304 else None,
                not_modified=True,
                received_at=state.response_received_at,
                validator_supported=bool(state.etag or state.last_modified),
                payload_sha256=state.payload_sha256,
            )

    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError(f"provider_unexpected_http_status:{response.status_code}")
    body = bytes(response.content)
    received_at = datetime.now(timezone.utc)
    value = validate(body, received_at)
    digest = hashlib.sha256(body).hexdigest()
    if state is None:
        state = WeatherProviderHttpResource(
            provider=provider,
            resource_url=url,
            request_variant_hash=variant_hash,
            request_variant=variant,
            payload=body,
            payload_sha256=digest,
            payload_size_bytes=len(body),
            response_received_at=received_at,
            last_checked_at=checked_at,
            last_status_code=200,
        )
        db.add(state)
    else:
        state.request_variant = variant
        state.payload = body
        state.payload_sha256 = digest
        state.payload_size_bytes = len(body)
        state.response_received_at = received_at
        state.last_checked_at = checked_at
        state.last_status_code = 200
    state.etag = response.headers.get("ETag")
    state.last_modified = response.headers.get("Last-Modified")
    state.content_type = response.headers.get("Content-Type")
    state.last_not_modified_at = None
    state.updated_at = checked_at
    db.flush()
    return ValidatedResource(
        value=value,
        not_modified=False,
        received_at=received_at,
        validator_supported=bool(state.etag or state.last_modified),
        payload_sha256=digest,
    )
