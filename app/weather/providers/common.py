"""Shared observation-provider contracts and station matching."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Literal

from app.weather.vectors import wind_to_uv


MAX_WIND_SPEED_MS = 75.0
MAX_WIND_GUST_MS = 100.0
MAX_FUTURE_SKEW = timedelta(minutes=5)
LATE_OBSERVATION_AFTER = timedelta(hours=1)
ObservationImportStatus = Literal["raw", "accepted", "rejected", "quarantined"]


@dataclass(frozen=True)
class ObservationStation:
    provider: str
    station_id: str
    name: str
    latitude: float
    longitude: float
    elevation_m: float | None = None
    parameters: tuple[str, ...] = ()
    wigos_id: str | None = None
    icao_id: str | None = None
    measurement_height_m: float | None = None
    license: str | None = None
    provenance: dict = field(default_factory=dict)
    country_code: str | None = None
    active: bool = True
    typical_interval_minutes: int | None = None
    commercial_reuse: bool | None = None
    attribution_required: bool = False
    operator: str | None = None
    station_type: str | None = None
    sensor_metadata: dict = field(default_factory=dict)
    active_from: datetime | None = None
    active_to: datetime | None = None
    metadata_updated_at: datetime | None = None
    source_url: str | None = None
    raw_payload: dict = field(default_factory=dict)
    received_at: datetime | None = None


@dataclass(frozen=True)
class NormalizedObservation:
    station_identity: str
    provider: str
    provider_station_id: str
    wigos_id: str | None
    icao_id: str | None
    latitude: float | None
    longitude: float | None
    elevation_m: float | None
    measurement_height_m: float | None
    observed_at: datetime | None
    received_at: datetime
    imported_at: datetime
    wind_speed_ms: float | None
    wind_direction_deg: float | None
    wind_u_ms: float | None
    wind_v_ms: float | None
    wind_gust_ms: float | None
    gust_period_seconds: int | None
    provider_quality: str | None
    license: str | None
    provenance: dict
    import_status: ObservationImportStatus
    rejection_reason: str | None
    data_issues: tuple[str, ...] = ()
    raw_payload: dict = field(default_factory=dict)
    fingerprint: str = ""
    published_at: datetime | None = None
    measurement_period_seconds: int | None = None
    averaging_period_seconds: int | None = None
    original_speed: float | None = None
    original_direction: float | None = None
    original_gust: float | None = None
    original_speed_unit: str | None = None
    parser_version: str = "observation-normalizer-v2"

    @property
    def station_id(self) -> str:
        """Compatibility alias for the original provider station id."""
        return self.provider_station_id

    @property
    def fetched_at(self) -> datetime:
        """Compatibility alias; new code must use the precise received_at name."""
        return self.received_at


def station_identity(provider: object, provider_station_id: object) -> str:
    provider_name = str(provider or "").strip().lower()
    original_id = str(provider_station_id or "").strip()
    return f"{provider_name}:{original_id}"


def _json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _utc(value, field_name: str, issues: list[str], *, default=None) -> datetime | None:
    if value is None:
        return default
    if not isinstance(value, datetime):
        issues.append(f"{field_name}:invalid")
        return default
    if value.tzinfo is None or value.utcoffset() is None:
        issues.append(f"{field_name}:naive")
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(
        _json_safe(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_observation(
    *,
    provider,
    station_id,
    observed_at,
    wind_speed_ms,
    wind_direction_deg=None,
    wind_gust_ms=None,
    gust_period_seconds=None,
    provider_quality=None,
    received_at=None,
    imported_at=None,
    fetched_at=None,
    wigos_id=None,
    icao_id=None,
    latitude=None,
    longitude=None,
    elevation_m=None,
    measurement_height_m=None,
    license=None,
    provenance=None,
    raw_payload=None,
    extra_issues=(),
    published_at=None,
    measurement_period_seconds=None,
    averaging_period_seconds=None,
    original_speed_unit="m/s",
) -> NormalizedObservation:
    """Normalize one public wind observation without discarding bad input.

    Invalid values are removed from the normalized value fields but remain in
    ``raw_payload`` and produce an explicit rejected/quarantined status. Naive
    provider times are interpreted as UTC only to retain an inspectable instant;
    the row is quarantined and never accepted on that assumption.
    """
    issues = [str(issue) for issue in extra_issues]
    now = datetime.now(timezone.utc)
    imported = _utc(imported_at, "imported_at", issues, default=now)
    if imported > now + MAX_FUTURE_SKEW:
        issues.append("imported_at:future")
    received_input = received_at if received_at is not None else fetched_at
    received = _utc(received_input, "received_at", issues, default=imported)
    if received_input is None:
        issues.append("received_at:unproven")
    published = _utc(published_at, "published_at", issues)
    observed = _utc(observed_at, "observed_at", issues)
    if observed is None:
        issues.append("observed_at:missing")
    elif observed > received + MAX_FUTURE_SKEW:
        issues.append("observed_at:future")
    elif received - observed > LATE_OBSERVATION_AFTER:
        issues.append("observed_at:late")
    if received > imported + MAX_FUTURE_SKEW:
        issues.append("received_at:future")

    provider_name = str(provider or "").strip().lower()
    original_station_id = str(station_id or "").strip()
    if provider_name not in {"dwd", "dmi", "awc_metar", "knmi"}:
        issues.append("provider:not_observation_source")
    if (
        not provider_name
        or len(provider_name) > 20
        or not original_station_id
        or len(original_station_id) > 80
    ):
        issues.append("station_identity:invalid")

    quality_text = None if provider_quality is None else str(provider_quality)
    if quality_text is not None and len(quality_text) > 80:
        quality_text = None
        issues.append("provider_quality:invalid")
    wigos_text = None if wigos_id is None else str(wigos_id).strip() or None
    if wigos_text is not None and len(wigos_text) > 80:
        wigos_text = None
        issues.append("wigos_id:invalid")
    icao_text = None if icao_id is None else str(icao_id).strip() or None
    if icao_text is not None and len(icao_text) > 16:
        icao_text = None
        issues.append("icao_id:invalid")
    license_text = None if license is None else str(license).strip() or None
    if license_text is not None and len(license_text) > 160:
        license_text = None
        issues.append("license:invalid")

    unit = str(original_speed_unit or "").strip().lower()
    factor = {"m/s": 1.0, "km/h": 1 / 3.6, "kt": 0.5144444444444445, "knots": 0.5144444444444445}.get(unit)
    if factor is None:
        issues.append("wind_unit:invalid")
    original_speed = _number(wind_speed_ms)
    original_gust = _number(wind_gust_ms)
    speed = original_speed * factor if original_speed is not None and factor is not None else None
    if speed is None or not 0 <= speed <= MAX_WIND_SPEED_MS:
        speed = None
        issues.append("wind_speed:invalid")
    direction = _number(wind_direction_deg)
    if wind_direction_deg is not None and (
        direction is None or not 0 <= direction < 360
    ):
        direction = None
        issues.append("wind_direction:invalid")
    gust = original_gust * factor if original_gust is not None and factor is not None else None
    if wind_gust_ms is not None and (
        gust is None
        or not 0 <= gust <= MAX_WIND_GUST_MS
        or speed is not None and gust < speed
    ):
        gust = None
        issues.append("wind_gust:invalid")
    gust_period = None
    if gust_period_seconds is not None:
        value = _number(gust_period_seconds)
        if value is None or not value.is_integer() or not 1 <= value <= 86_400:
            issues.append("gust_period:invalid")
        elif gust is None:
            issues.append("gust_period:without_gust")
        else:
            gust_period = int(value)
    for name, period in (("measurement_period", measurement_period_seconds), ("averaging_period", averaging_period_seconds)):
        if period is not None and (not isinstance(period, int) or isinstance(period, bool) or not 1 <= period <= 86400):
            issues.append(f"{name}:invalid")

    lat = _number(latitude)
    lon = _number(longitude)
    if latitude is not None and (lat is None or not -90 <= lat <= 90):
        lat = None
        issues.append("station_latitude:invalid")
    if longitude is not None and (lon is None or not -180 <= lon <= 180):
        lon = None
        issues.append("station_longitude:invalid")
    elevation = _number(elevation_m)
    if elevation_m is not None and (
        elevation is None or not -500 <= elevation <= 9_000
    ):
        elevation = None
        issues.append("station_elevation:invalid")
    measurement_height = _number(measurement_height_m)
    if measurement_height_m is not None and (
        measurement_height is None or not 0 <= measurement_height <= 300
    ):
        measurement_height = None
        issues.append("measurement_height:invalid")

    u_ms = v_ms = None
    if speed == 0 and direction is None and wind_direction_deg is None:
        u_ms = v_ms = 0.0
    elif speed is not None and direction is None and wind_direction_deg is None:
        issues.append("wind_direction:missing")
    elif speed is not None and direction is not None:
        u_ms, v_ms = wind_to_uv(speed, direction)

    raw_value = _json_safe(raw_payload if raw_payload is not None else {})
    if not isinstance(raw_value, dict):
        raw = {"value": raw_value}
        issues.append("raw_payload:invalid")
    else:
        raw = raw_value
    provenance_value = _json_safe(provenance if provenance is not None else {})
    if not isinstance(provenance_value, dict):
        source_provenance = {"value": provenance_value}
        issues.append("provenance:invalid")
    else:
        source_provenance = provenance_value

    quarantine_issues = {
        "observed_at:invalid", "observed_at:missing", "observed_at:naive",
        "observed_at:future", "received_at:invalid", "received_at:naive",
        "received_at:future", "imported_at:invalid", "imported_at:naive",
        "imported_at:future",
        "received_at:unproven", "published_at:invalid", "published_at:naive",
        "station_identity:invalid", "station_identity:mismatch",
        "provider:not_observation_source",
        "duplicate:conflict", "provider_parse:invalid",
    }
    warning_issues = {"observed_at:late"}
    if any(issue in quarantine_issues for issue in issues):
        status: ObservationImportStatus = "quarantined"
    elif any(issue not in warning_issues for issue in issues):
        status = "rejected"
    else:
        status = "accepted"
    blocking = [issue for issue in issues if issue not in warning_issues]
    rejection_reason = ";".join(dict.fromkeys(blocking)) or None

    stable = {
        "provider": provider_name,
        "provider_station_id": original_station_id,
        "observed_at": observed,
        "wind_speed_ms": speed,
        "wind_direction_deg": direction,
        "wind_gust_ms": gust,
        "gust_period_seconds": gust_period,
        "provider_quality": quality_text,
        "raw_payload": raw,
    }
    return NormalizedObservation(
        station_identity=station_identity(provider_name, original_station_id),
        provider=provider_name,
        provider_station_id=original_station_id,
        wigos_id=wigos_text,
        icao_id=icao_text,
        latitude=lat,
        longitude=lon,
        elevation_m=elevation,
        measurement_height_m=measurement_height,
        observed_at=observed,
        received_at=received,
        imported_at=imported,
        wind_speed_ms=speed,
        wind_direction_deg=direction,
        wind_u_ms=u_ms,
        wind_v_ms=v_ms,
        wind_gust_ms=gust,
        gust_period_seconds=gust_period,
        provider_quality=quality_text,
        license=license_text,
        provenance=source_provenance,
        import_status=status,
        rejection_reason=rejection_reason,
        data_issues=tuple(dict.fromkeys(issues)),
        raw_payload=raw,
        fingerprint=_fingerprint(stable),
        published_at=published,
        measurement_period_seconds=measurement_period_seconds,
        averaging_period_seconds=averaging_period_seconds,
        original_speed=original_speed,
        original_direction=_number(wind_direction_deg),
        original_gust=original_gust,
        original_speed_unit=original_speed_unit,
    )


def with_station_metadata(row: NormalizedObservation, station) -> NormalizedObservation:
    """Attach authoritative configured-station metadata before persistence."""
    expected_provider = str(getattr(station, "provider", "")).strip().lower()
    expected_id = str(getattr(station, "provider_station_id", "")).strip()
    if row.provider != expected_provider or row.provider_station_id != expected_id:
        issues = tuple(dict.fromkeys((*row.data_issues, "station_identity:mismatch")))
        return replace(
            row,
            import_status="quarantined",
            rejection_reason=";".join(
                dict.fromkeys(filter(None, (row.rejection_reason, "station_identity:mismatch")))
            ),
            data_issues=issues,
        )
    station_provenance = dict(getattr(station, "provenance", None) or {})
    station_provenance.update(row.provenance)
    return replace(
        row,
        station_identity=station_identity(expected_provider, expected_id),
        wigos_id=row.wigos_id or getattr(station, "wigos_id", None),
        icao_id=row.icao_id or getattr(station, "icao_id", None),
        latitude=row.latitude if row.latitude is not None else getattr(station, "latitude", None),
        longitude=row.longitude if row.longitude is not None else getattr(station, "longitude", None),
        elevation_m=row.elevation_m if row.elevation_m is not None else getattr(station, "elevation_m", None),
        measurement_height_m=(
            row.measurement_height_m
            if row.measurement_height_m is not None
            else getattr(station, "measurement_height_m", None)
        ),
        license=row.license or getattr(station, "license", None),
        provenance=_json_safe(station_provenance),
    )


def deduplicate_observations(
    rows: list[NormalizedObservation],
) -> list[NormalizedObservation]:
    """Collapse identical repeats and quarantine conflicting same-time values."""
    groups: dict[tuple, list[NormalizedObservation]] = {}
    for row in rows:
        key = (
            row.station_identity,
            row.observed_at.isoformat() if row.observed_at else row.fingerprint,
        )
        groups.setdefault(key, []).append(row)
    output = []
    for group in groups.values():
        ordered = sorted(group, key=lambda row: row.fingerprint)
        signatures = {
            (
                row.wind_speed_ms,
                row.wind_direction_deg,
                row.wind_gust_ms,
                row.gust_period_seconds,
                row.provider_quality,
                row.import_status,
                row.rejection_reason,
            )
            for row in ordered
        }
        if len(signatures) == 1:
            output.append(ordered[0])
            continue
        for row in ordered:
            issues = tuple(dict.fromkeys((*row.data_issues, "duplicate:conflict")))
            output.append(replace(
                row,
                import_status="quarantined",
                rejection_reason=";".join(
                    dict.fromkeys(filter(None, (row.rejection_reason, "duplicate:conflict")))
                ),
                data_issues=issues,
            ))
    minimum = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(output, key=lambda row: (row.observed_at or minimum, row.fingerprint))


def normalized_observation_payload(row: NormalizedObservation) -> dict:
    """JSON-safe normalized audit payload for the quarantine table."""
    payload = asdict(row)
    payload.pop("raw_payload", None)
    return _json_safe(payload)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_stations(
    latitude: float, longitude: float, stations: list[ObservationStation], *, limit: int = 3, max_km: float = 100
) -> list[tuple[ObservationStation, float]]:
    """Return deterministic nearest wind-capable stations inside a safe radius."""
    ranked = []
    for station in stations:
        if station.parameters and "wind_speed" not in station.parameters:
            continue
        distance = haversine_km(latitude, longitude, station.latitude, station.longitude)
        if distance <= max_km:
            ranked.append((station, distance))
    return sorted(ranked, key=lambda item: (item[1], item[0].station_id))[:max(1, limit)]
