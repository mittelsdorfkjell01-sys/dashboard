"""NOAA Aviation Weather Center METAR adapter for European ICAO stations.

The provider is the documented AWC Data API, not a scraper.  Its station cache
is worldwide; callers explicitly opt into the European subset.  HTTP state is
process-local and only an efficiency aid: observation idempotency remains a
database concern in :mod:`app.weather.observation_worker`.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import email.utils
import gzip
import json
import math
from typing import Callable

import httpx

from app.weather.providers.common import (
    NormalizedObservation,
    ObservationStation,
    deduplicate_observations,
    normalize_observation,
)

AWC_BASE = "https://aviationweather.gov/api/data"
AWC_STATION_CACHE = (
    "https://aviationweather.gov/data/cache/stations.cache.json.gz"
)
AWC_LICENSE = "Originating METAR licence not verified for commercial reuse"
AWC_USER_AGENT = "Surfwinddata/1.0 (+https://surfwinddata.com)"
KNOT_TO_MS = 0.514444

AWC_PROVENANCE = {
    "source": "NOAA Aviation Weather Center Data API",
    "product": "official METAR/SPECI observations",
    "source_url": f"{AWC_BASE}/metar",
    "station_catalog_url": AWC_STATION_CACHE,
    "api_documentation_url": "https://aviationweather.gov/data/api/",
    "terms_url": "https://www.weather.gov/disclaimer",
    "wmo_policy_url": "https://wmo.int/wmo-unified-data-policy-resolution-res1",
    "license_status": "unverified_redistribution",
    "commercial_reuse": False,
    "attribution": "NOAA Aviation Weather Center and originating METAR station",
    "provider_rate_limit_per_minute": 100,
    "local_rate_limit_per_minute": 90,
    "typical_interval_minutes": 60,
    "measurement_height_status": "not supplied by AWC",
}

# ICAO location-prefix coverage used only to keep the worldwide AWC catalogue
# bounded to WMO Region VI plus adjacent European territories.  Country codes
# remain the authoritative report dimension when AWC supplies one.
EUROPE_ICAO_PREFIXES = frozenset("BELU")
EUROPE_COUNTRY_CODES = frozenset({
    "AD", "AL", "AT", "BA", "BE", "BG", "BY", "CH", "CY", "CZ", "DE",
    "DK", "EE", "ES", "FI", "FO", "FR", "GB", "GI", "GR", "HR", "HU",
    "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK",
    "MT", "NL", "NO", "PL", "PT", "RO", "RS", "SE", "SI", "SJ", "SK",
    "SM", "TR", "UA", "VA", "XK",
})


class ProviderBackoffError(RuntimeError):
    """The provider asked us to stop; callers should retry in a later job."""


@dataclass
class _CachedResponse:
    payload: object
    etag: str | None
    last_modified: str | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _retry_after_seconds(value: str | None, *, now: datetime) -> int | None:
    if not value:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        try:
            instant = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        return max(0, math.ceil((instant.astimezone(timezone.utc) - now).total_seconds()))


class AwcMetarClient:
    """Small conditional-GET client with bounded rate and non-blocking backoff."""

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        user_agent: str = AWC_USER_AGENT,
        now: Callable[[], datetime] = _utc_now,
        local_limit_per_minute: int = 90,
    ) -> None:
        self._client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(20.0, connect=5.0),
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )
        self._now = now
        self._local_limit = max(1, min(local_limit_per_minute, 90))
        self._requests: deque[datetime] = deque()
        self._cache: dict[str, _CachedResponse] = {}
        self._retry_not_before: datetime | None = None
        self._failure_count = 0

    def close(self) -> None:
        self._client.close()

    def _request_key(self, url: str, params: dict | None) -> str:
        request = self._client.build_request("GET", url, params=params)
        return str(request.url)

    def get_json(
        self, url: str, *, params: dict | None = None, gzip_payload: bool = False
    ):
        now = self._now().astimezone(timezone.utc)
        if self._retry_not_before is not None and now < self._retry_not_before:
            raise ProviderBackoffError("awc_backoff_active")

        cutoff = now - timedelta(minutes=1)
        while self._requests and self._requests[0] <= cutoff:
            self._requests.popleft()
        if len(self._requests) >= self._local_limit:
            self._retry_not_before = self._requests[0] + timedelta(minutes=1)
            raise ProviderBackoffError("awc_local_rate_limit")

        key = self._request_key(url, params)
        cached = self._cache.get(key)
        headers = {}
        if cached and cached.etag:
            headers["If-None-Match"] = cached.etag
        if cached and cached.last_modified:
            headers["If-Modified-Since"] = cached.last_modified
        self._requests.append(now)
        response = self._client.get(url, params=params, headers=headers)

        if response.status_code == 304:
            if cached is None:
                raise RuntimeError("awc_304_without_cached_payload")
            self._failure_count = 0
            return cached.payload
        if response.status_code == 204:
            self._failure_count = 0
            return []
        if response.status_code == 429 or response.status_code in {500, 502, 503, 504}:
            self._failure_count += 1
            retry_after = _retry_after_seconds(
                response.headers.get("Retry-After"), now=now
            )
            # AWC/NWS asks clients not to hammer an unavailable service.  Keep
            # the wait out of the worker thread and let a later cron run retry.
            delay = max(retry_after or 0, min(900, 60 * 2 ** (self._failure_count - 1)))
            self._retry_not_before = now + timedelta(seconds=delay)
            raise ProviderBackoffError(f"awc_http_{response.status_code}")

        response.raise_for_status()
        if gzip_payload:
            content = response.content
            if content[:2] == b"\x1f\x8b":
                content = gzip.decompress(content)
            payload = json.loads(content)
        else:
            payload = response.json()
        self._failure_count = 0
        self._retry_not_before = None
        self._cache[key] = _CachedResponse(
            payload=payload,
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )
        return payload


def _number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _instant(value) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_european(record: dict) -> bool:
    country = str(record.get("country") or "").upper()
    icao = str(record.get("icaoId") or record.get("id") or "").upper()
    if country:
        return country in EUROPE_COUNTRY_CODES
    return bool(icao and icao[0] in EUROPE_ICAO_PREFIXES)


def parse_station_catalog(payload: object, *, europe_only: bool = True) -> list[ObservationStation]:
    """Parse the official daily station cache and retain METAR-capable sites."""
    records = payload if isinstance(payload, list) else []
    stations: dict[str, ObservationStation] = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        station_id = str(item.get("icaoId") or item.get("id") or "").strip().upper()
        site_types = tuple(str(value).upper() for value in (item.get("siteType") or []))
        latitude, longitude = _number(item.get("lat")), _number(item.get("lon"))
        if (
            not station_id
            or len(station_id) > 16
            or "METAR" not in site_types
            or latitude is None
            or longitude is None
            or europe_only and not _is_european(item)
        ):
            continue
        country = str(item.get("country") or "").upper() or None
        provenance = {
            **AWC_PROVENANCE,
            "country_code": country,
            "wmo_id": item.get("wmoId"),
            "site_types": list(site_types),
        }
        stations[station_id] = ObservationStation(
            provider="awc_metar",
            station_id=station_id,
            name=str(item.get("site") or station_id),
            latitude=latitude,
            longitude=longitude,
            elevation_m=_number(item.get("elev")),
            parameters=("wind_speed", "wind_dir", "wind_gust"),
            icao_id=station_id,
            # AWC does not publish sensor height.  Do not invent 10 m here.
            measurement_height_m=None,
            license=AWC_LICENSE,
            provenance=provenance,
            country_code=country,
            active=True,
            typical_interval_minutes=60,
            commercial_reuse=False,
            attribution_required=True,
        )
    return sorted(stations.values(), key=lambda station: station.station_id)


def parse_metars(
    payload: object,
    *,
    station_id: str,
    received_at: datetime | None = None,
) -> list[NormalizedObservation]:
    """Normalize AWC JSON; knots are converted once at the provider boundary."""
    received = received_at or _utc_now()
    rows = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        actual_id = str(item.get("icaoId") or station_id).strip().upper()
        issues = []
        observed = _instant(item.get("obsTime"))
        if observed is None:
            issues.append("provider_parse:invalid")
        if actual_id != str(station_id).strip().upper():
            issues.append("station_identity:mismatch")
        direction = item.get("wdir")
        if isinstance(direction, str) and direction.upper() == "VRB":
            direction = None
            issues.append("wind_direction:variable")
        speed_knots, gust_knots = _number(item.get("wspd")), _number(item.get("wgst"))
        quality = item.get("qcField")
        provider_quality = f"awc_qc:{quality}" if quality is not None else "awc_qc:unknown"
        provenance = {
            **AWC_PROVENANCE,
            "upstream_receipt_time": item.get("receiptTime"),
            "report_time": item.get("reportTime"),
            "metar_type": item.get("metarType"),
            "qc_field": quality,
        }
        rows.append(normalize_observation(
            provider="awc_metar",
            station_id=actual_id,
            observed_at=observed,
            received_at=received,
            imported_at=_utc_now(),
            wind_speed_ms=None if speed_knots is None else speed_knots * KNOT_TO_MS,
            wind_direction_deg=direction,
            wind_gust_ms=None if gust_knots is None else gust_knots * KNOT_TO_MS,
            # METAR gust periods vary by national implementation and AWC does
            # not expose the period, so it deliberately remains unknown.
            gust_period_seconds=None,
            provider_quality=provider_quality,
            icao_id=actual_id,
            latitude=item.get("lat"),
            longitude=item.get("lon"),
            elevation_m=item.get("elev"),
            measurement_height_m=None,
            license=AWC_LICENSE,
            provenance=provenance,
            raw_payload=item,
            extra_issues=issues,
        ))
    return deduplicate_observations(rows)


_DEFAULT_CLIENT: AwcMetarClient | None = None


def default_client() -> AwcMetarClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = AwcMetarClient()
    return _DEFAULT_CLIENT


def fetch_recent(
    station_id: str,
    *,
    hours: int = 3,
    client: AwcMetarClient | None = None,
) -> list[NormalizedObservation]:
    station = str(station_id).strip().upper()
    payload = (client or default_client()).get_json(
        f"{AWC_BASE}/metar",
        params={"ids": station, "format": "json", "hours": max(1, min(hours, 24))},
    )
    return parse_metars(payload, station_id=station, received_at=_utc_now())


def fetch_stations(
    *,
    client: AwcMetarClient | None = None,
    europe_only: bool = True,
) -> list[ObservationStation]:
    payload = (client or default_client()).get_json(
        AWC_STATION_CACHE, gzip_payload=True
    )
    return parse_station_catalog(payload, europe_only=europe_only)
