"""DWD CDC 10-minute wind observation adapter."""

from __future__ import annotations

import csv
from dataclasses import replace
import io
import zipfile
from datetime import datetime, timezone
import re

import httpx
from app.weather.providers.common import (
    NormalizedObservation,
    ObservationStation,
    deduplicate_observations,
    normalize_observation,
)

DWD_NOW = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/now"
DWD_STATIONS = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/recent/zehn_min_ff_Beschreibung_Stationen.txt"
DWD_METADATA = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/meta_data"
DWD_LICENSE = "CC BY 4.0"
DWD_PROVENANCE = {
    "source": "DWD Climate Data Center",
    "product": "10-minute station wind observations",
    "source_url": DWD_NOW,
    "terms_url": "https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.txt",
    "country_code": "DE",
    "commercial_reuse": True,
    "attribution_required": True,
    "typical_interval_minutes": 10,
}
def _provider_value(value):
    cleaned = str(value or "").strip()
    return None if cleaned in {"", "-999", "-999.0"} else cleaned


def _direction_value(value):
    cleaned = _provider_value(value)
    try:
        return 0.0 if float(cleaned) == 360 else cleaned
    except (TypeError, ValueError):
        return cleaned


def parse_now_zip(payload: bytes, *, station_id: str | None = None, fetched_at=None) -> list[NormalizedObservation]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = next((n for n in archive.namelist()
                     if n.lower().endswith(".txt") and
                     ("produkt_zehn_min_ff" in n.lower() or "produkt_zehn_now_ff" in n.lower())), None)
        if name is None:
            raise ValueError("DWD archive contains no 10-minute wind product")
        text = archive.read(name).decode("latin-1")
    received_at = fetched_at or datetime.now(timezone.utc)
    imported_at = datetime.now(timezone.utc)
    rows = []
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        clean = {key.strip(): (value or "").strip() for key, value in row.items() if key}
        issues = []
        try:
            observed = datetime.strptime(clean["MESS_DATUM"], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            observed = None
            issues.append("provider_parse:invalid")
        quality_raw = clean.get("QN", clean.get("QN_3", ""))
        payload_station_id = clean.get("STATIONS_ID") or clean.get("STATION_ID")
        sid = (station_id if station_id and payload_station_id
               and str(payload_station_id).zfill(5) == str(station_id).zfill(5)
               else payload_station_id or station_id)
        if (
            station_id
            and payload_station_id
            and str(payload_station_id).zfill(5) != str(station_id).zfill(5)
        ):
            issues.append("station_identity:mismatch")
        rows.append(normalize_observation(
            provider="dwd",
            station_id=sid,
            observed_at=observed,
            wind_speed_ms=_provider_value(clean.get("FF_10")),
            wind_direction_deg=_direction_value(clean.get("DD_10")),
            provider_quality=quality_raw or None,
            received_at=received_at,
            imported_at=imported_at,
            license=DWD_LICENSE,
            provenance=DWD_PROVENANCE,
            raw_payload=row,
            extra_issues=issues,
            measurement_period_seconds=600,
            averaging_period_seconds=600,
        ))
    return deduplicate_observations(rows)


def fetch_now(station_id: str, *, timeout: float = 15.0, db=None) -> list[NormalizedObservation]:
    station = str(station_id).strip().zfill(5)
    url = f"{DWD_NOW}/10minutenwerte_wind_{station}_now.zip"
    if db is not None:
        from app.weather.provider_http import fetch_validated_resource

        result = fetch_validated_resource(
            db,
            provider="dwd",
            url=url,
            request_variant={"product": "10-minute-wind-now", "station": station},
            timeout=timeout,
            reuse_cached_on_304=False,
            validate=lambda payload, received_at: parse_now_zip(
                payload, station_id=station, fetched_at=received_at
            ),
        )
        return list(result.value or ())
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return parse_now_zip(
        response.content, station_id=station, fetched_at=datetime.now(timezone.utc)
    )


_STATION_LINE = re.compile(
    r"^(\d{5})\s+\d{8}\s+(\d{8})\s+(-?\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(.+?)\s{2,}"
)


def parse_station_catalog(text: str, *, today: str | None = None,
                          include_inactive: bool = False) -> list[ObservationStation]:
    today = today or datetime.now(timezone.utc).strftime("%Y%m%d")
    stations = []
    for line in text.splitlines():
        match = _STATION_LINE.match(line.strip())
        if not match:
            continue
        station_id, end_date, elevation, latitude, longitude, name = match.groups()
        # The recent catalogue may lag by a day; retain stations seen within 7 days.
        try:
            age = (datetime.strptime(today, "%Y%m%d") - datetime.strptime(end_date, "%Y%m%d")).days
        except ValueError:
            continue
        active = age <= 7
        if not active and not include_inactive:
            continue
        stations.append(ObservationStation(
            provider="dwd", station_id=station_id, name=name.strip(), latitude=float(latitude),
            longitude=float(longitude), elevation_m=float(elevation), parameters=("wind_speed", "wind_dir"),
            license=DWD_LICENSE, provenance=DWD_PROVENANCE,
            country_code="DE", typical_interval_minutes=10,
            commercial_reuse=True, attribution_required=True,
            source_url=DWD_STATIONS,
            measurement_height_m=None,
            active=active,
            raw_payload={"catalog_line": line},
        ))
    return stations


def fetch_stations(*, timeout: float = 20.0, db=None,
                   include_inactive: bool = False) -> list[ObservationStation]:
    def parse(payload: bytes, received_at: datetime):
        return [replace(item, received_at=received_at)
                for item in parse_station_catalog(
                    payload.decode("latin-1"), include_inactive=include_inactive
                )]

    if db is not None:
        from app.weather.provider_http import fetch_validated_resource

        result = fetch_validated_resource(
            db,
            provider="dwd",
            url=DWD_STATIONS,
            request_variant={"include_inactive": include_inactive},
            timeout=timeout,
            validate=parse,
        )
        return list(result.value or ())
    response = httpx.get(DWD_STATIONS, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return parse(response.content, datetime.now(timezone.utc))


def parse_station_metadata_zip(payload: bytes, station: ObservationStation) -> ObservationStation:
    """Use only the newest documented sensor row, never assume 10 m."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = next((name for name in archive.namelist()
                     if "Geraete_Windgeschwindigkeit_Mittel" in name and name.endswith(".txt")), None)
        if name is None:
            raise ValueError("DWD wind-speed sensor metadata missing")
        lines = archive.read(name).decode("latin-1").splitlines()
    records = list(csv.DictReader(lines, delimiter=";"))
    records = [row for row in records if (row.get("Von_Datum") or "").isdigit()]
    if not records:
        raise ValueError("DWD sensor metadata has no dated rows")
    latest = max(records, key=lambda row: row["Von_Datum"])
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    interval_current = ((latest.get("Von_Datum") or "") <= today
                        and (latest.get("Bis_Datum") or "") >= today)
    height_text = latest.get("Geberhoehe ueber Grund [m]")
    try:
        height = float(height_text.replace(",", "."))
    except (AttributeError, ValueError):
        height = None
    if height is not None and not 0 < height <= 300:
        height = None
    if not interval_current:
        height = None
    return replace(
        station, measurement_height_m=height,
        received_at=datetime.now(timezone.utc),
        sensor_metadata={"equipment": latest.get("Geraetetyp Name"),
                         "measurement_method": latest.get("Messverfahren"),
                         "effective_from": latest.get("Von_Datum"),
                         "effective_to": latest.get("Bis_Datum"),
                         "height_status": "documented_current" if interval_current else "metadata_interval_not_current"},
        source_url=f"{DWD_METADATA}/Meta_Daten_zehn_min_ff_{station.station_id}.zip",
        raw_payload={"catalog": station.raw_payload, "sensor_row": latest},
    )


def fetch_station_metadata(station: ObservationStation, *, timeout: float = 15.0,
                           db=None) -> ObservationStation:
    url = f"{DWD_METADATA}/Meta_Daten_zehn_min_ff_{station.station_id}.zip"

    def parse(payload: bytes, received_at: datetime):
        parsed = parse_station_metadata_zip(payload, station)
        return replace(parsed, received_at=received_at)

    if db is not None:
        from app.weather.provider_http import fetch_validated_resource

        result = fetch_validated_resource(
            db,
            provider="dwd",
            url=url,
            request_variant={"product": "10-minute-wind-metadata"},
            timeout=timeout,
            validate=parse,
        )
        return result.value
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return parse(response.content, datetime.now(timezone.utc))
