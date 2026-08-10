"""DWD CDC 10-minute wind observation adapter."""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
import re

import httpx
from app.weather.providers.common import ObservationStation

DWD_NOW = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/now"
DWD_STATIONS = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/recent/zehn_min_ff_Beschreibung_Stationen.txt"


@dataclass(frozen=True)
class DwdObservation:
    observed_at: datetime
    wind_speed_ms: float
    wind_direction_deg: float | None
    quality: int | None


def parse_now_zip(payload: bytes) -> list[DwdObservation]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = next((n for n in archive.namelist() if "produkt_zehn_min_ff" in n.lower()), None)
        if name is None:
            raise ValueError("DWD archive contains no 10-minute wind product")
        text = archive.read(name).decode("latin-1")
    rows = []
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        clean = {key.strip(): (value or "").strip() for key, value in row.items() if key}
        try:
            speed = float(clean["FF_10"])
            if speed < 0:
                continue
            observed = datetime.strptime(clean["MESS_DATUM"], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            direction_raw = float(clean.get("DD_10", "-999"))
            quality_raw = clean.get("QN", clean.get("QN_3", ""))
            rows.append(DwdObservation(observed, speed, direction_raw % 360 if direction_raw >= 0 else None,
                                       int(quality_raw) if quality_raw.lstrip("-").isdigit() else None))
        except (KeyError, ValueError):
            continue
    return rows


def fetch_now(station_id: str, *, timeout: float = 15.0) -> list[DwdObservation]:
    station = str(station_id).strip().zfill(5)
    response = httpx.get(f"{DWD_NOW}/10minutenwerte_wind_{station}_now.zip", timeout=timeout)
    response.raise_for_status()
    return parse_now_zip(response.content)


_STATION_LINE = re.compile(
    r"^(\d{5})\s+\d{8}\s+(\d{8})\s+(-?\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(.+?)\s{2,}"
)


def parse_station_catalog(text: str, *, today: str | None = None) -> list[ObservationStation]:
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
        if age > 7:
            continue
        stations.append(ObservationStation(
            provider="dwd", station_id=station_id, name=name.strip(), latitude=float(latitude),
            longitude=float(longitude), elevation_m=float(elevation), parameters=("wind_speed", "wind_dir"),
        ))
    return stations


def fetch_stations(*, timeout: float = 20.0) -> list[ObservationStation]:
    response = httpx.get(DWD_STATIONS, timeout=timeout)
    response.raise_for_status()
    return parse_station_catalog(response.content.decode("latin-1"))
