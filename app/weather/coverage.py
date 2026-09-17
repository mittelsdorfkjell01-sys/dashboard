"""Offline/database coverage reporting for normalized public wind stations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import select

from app.models import (
    Region,
    Spot,
    WeatherObservation,
    WeatherObservationImportState,
    WeatherStation,
)
from app.weather.station_identity import (
    duplicate_station_groups,
    station_display_identity,
)


@dataclass(frozen=True)
class CoverageStation:
    id: object
    provider: str
    provider_station_id: str
    country_code: str | None
    active: bool
    latitude: float
    longitude: float
    elevation_m: float | None
    measurement_height_m: float | None
    wigos_id: str | None
    icao_id: str | None
    license: str | None
    provenance: dict


def _round_median(values: list[float]) -> float | None:
    return round(float(median(values)), 2) if values else None


def build_coverage_report(
    stations: list,
    observations: list,
    import_states: list = (),
    *,
    now: datetime | None = None,
) -> dict:
    """Build a deterministic report; no provider call is made here."""
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    active = [station for station in stations if getattr(station, "active", False)]
    duplicate_groups = duplicate_station_groups(active)
    duplicate_indices = set()
    for group in duplicate_groups:
        canonical = sorted(
            group,
            key=lambda index: (
                -sum(
                    getattr(active[index], attribute, None) is not None
                    for attribute in (
                        "country_code", "elevation_m", "measurement_height_m",
                        "wigos_id", "icao_id", "license",
                    )
                ),
                -{"dwd": 3, "dmi": 3, "awc_metar": 2}.get(
                    active[index].provider, 1
                ),
                station_display_identity(active[index]),
            ),
        )[0]
        duplicate_indices.update(index for index in group if index != canonical)
    unique_active = [
        station for index, station in enumerate(active) if index not in duplicate_indices
    ]

    countries: dict[str, int] = defaultdict(int)
    for station in unique_active:
        country = str(
            getattr(station, "country_code", None)
            or (getattr(station, "provenance", None) or {}).get("country_code")
            or "unknown"
        ).upper()
        countries[country] += 1

    observations_by_station: dict[object, list] = defaultdict(list)
    for observation in observations:
        observations_by_station[getattr(observation, "station_id", None)].append(observation)

    provider_intervals: dict[str, list[float]] = defaultdict(list)
    provider_delays: dict[str, list[float]] = defaultdict(list)
    for station in unique_active:
        values = sorted(
            observations_by_station.get(getattr(station, "id", None), []),
            key=lambda row: row.observed_at,
        )
        for previous, current in zip(values, values[1:]):
            delta = (current.observed_at - previous.observed_at).total_seconds() / 60
            if 0 < delta <= 360:
                provider_intervals[station.provider].append(delta)
        for observation in values:
            received = getattr(observation, "received_at", None)
            if received is not None:
                delay = (received - observation.observed_at).total_seconds() / 60
                if 0 <= delay <= 1440:
                    provider_delays[station.provider].append(delay)

    providers = {}
    for provider in sorted({station.provider for station in unique_active}):
        provider_stations = [station for station in unique_active if station.provider == provider]
        documented_intervals = [
            float(value)
            for station in provider_stations
            if (
                value := (
                    (station.provenance or {}).get("typical_interval_minutes")
                    or getattr(station, "typical_interval_minutes", None)
                )
            ) is not None
        ]
        license_values = sorted({
            str(station.license or "unknown") for station in provider_stations
        })
        commercial_values = {
            (station.provenance or {}).get("commercial_reuse")
            for station in provider_stations
        }
        providers[provider] = {
            "active_unique_stations": len(provider_stations),
            "typical_interval_minutes": _round_median(
                provider_intervals[provider] or documented_intervals
            ),
            "typical_delay_minutes": _round_median(provider_delays[provider]),
            "licenses": license_values,
            "commercial_reuse": (
                True if commercial_values == {True}
                else False if False in commercial_values
                else None
            ),
        }

    errors = []
    for state in import_states:
        if getattr(state, "status", None) != "error":
            continue
        errors.append({
            "station_id": str(getattr(state, "station_id", "")),
            "provider": getattr(state, "provider", None),
            "error_class": getattr(state, "error_class", None),
            "last_error_at": (
                state.last_error_at.astimezone(timezone.utc).isoformat()
                if getattr(state, "last_error_at", None)
                else None
            ),
            "consecutive_failures": getattr(state, "consecutive_failures", 0),
        })

    return {
        "generated_at": generated_at.isoformat(),
        "active_station_records": len(active),
        "active_unique_stations": len(unique_active),
        "active_wind_stations_by_country": dict(sorted(countries.items())),
        "providers": providers,
        "missing_elevation": [
            station_display_identity(station)
            for station in unique_active
            if getattr(station, "elevation_m", None) is None
        ],
        "missing_measurement_height": [
            station_display_identity(station)
            for station in unique_active
            if getattr(station, "measurement_height_m", None) is None
        ],
        "duplicates": [
            [station_display_identity(active[index]) for index in group]
            for group in duplicate_groups
        ],
        "license_status": {
            license_name: sum(
                1 for station in unique_active if str(station.license or "unknown") == license_name
            )
            for license_name in sorted({str(station.license or "unknown") for station in unique_active})
        },
        "current_import_errors": sorted(
            errors, key=lambda value: (value["provider"] or "", value["station_id"])
        ),
    }


def build_database_coverage_report(db, *, now: datetime | None = None) -> dict:
    """Coverage for configured stations and their recent operational history."""
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows = db.execute(
        select(WeatherStation, Region.country)
        .join(Spot, Spot.id == WeatherStation.spot_id)
        .join(Region, Region.id == Spot.region_id, isouter=True)
    ).all()
    stations = [
        CoverageStation(
            id=station.id,
            provider=station.provider,
            provider_station_id=station.provider_station_id,
            country_code=country,
            active=station.active,
            latitude=station.latitude,
            longitude=station.longitude,
            elevation_m=station.elevation_m,
            measurement_height_m=station.measurement_height_m,
            wigos_id=station.wigos_id,
            icao_id=station.icao_id,
            license=station.license,
            provenance=station.provenance or {},
        )
        for station, country in rows
    ]
    station_ids = [station.id for station in stations]
    observations = []
    if station_ids:
        observations = list(db.scalars(
            select(WeatherObservation).where(
                WeatherObservation.station_id.in_(station_ids),
                WeatherObservation.observed_at >= generated_at - timedelta(hours=24),
            )
        ).all())
    states = list(db.scalars(select(WeatherObservationImportState)).all())
    return build_coverage_report(
        stations, observations, states, now=generated_at
    )
