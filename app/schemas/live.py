"""Read schemas for the live + forecast endpoints (Sprint 3; consensus band Sprint 18)."""

from __future__ import annotations

import uuid
import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def _finite(value, *, minimum=None, maximum=None):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return None
    number = float(value)
    if minimum is not None and number < minimum or maximum is not None and number > maximum:
        return None
    return number


def _sanitize_conditions(data):
    if not isinstance(data, dict):
        return data
    result = dict(data)
    issues = list(result.get("data_issues") or [])
    constraints = {
        "wind": (0, None), "gust": (0, None), "wind_ms": (0, None), "gust_ms": (0, None),
        "dir": (0, 359.999), "swell": (0, None), "period": (0, None),
        "swell_dir": (0, 359.999), "precip": (0, None), "cloud_cover_pct": (0, 100),
        "pressure_msl_hpa": (0, None), "uv_index": (0, None),
    }
    for field, (minimum, maximum) in constraints.items():
        if field not in result or result[field] is None:
            continue
        clean = _finite(result[field], minimum=minimum, maximum=maximum)
        if clean is None:
            issues.append(f"{field}:invalid")
        result[field] = clean
    for field in ("air", "sst", "apparent_temperature_c"):
        if field in result and result[field] is not None:
            clean = _finite(result[field])
            if clean is None:
                issues.append(f"{field}:invalid")
            result[field] = clean
    if result.get("wind") is not None and result.get("gust") is not None and result["gust"] < result["wind"]:
        result["gust"] = None
        issues.append("gust:below_wind")
    if result.get("wind_ms") is not None and result.get("gust_ms") is not None and result["gust_ms"] < result["wind_ms"]:
        result["gust_ms"] = None
        issues.append("gust_ms:below_wind_ms")
    spread = result.get("wind_spread")
    if spread is not None:
        low = _finite(spread.get("low"), minimum=0) if isinstance(spread, dict) else None
        median = _finite(spread.get("median"), minimum=0) if isinstance(spread, dict) else None
        high = _finite(spread.get("high"), minimum=0) if isinstance(spread, dict) else None
        n = spread.get("n") if isinstance(spread, dict) else None
        if not isinstance(n, int) or isinstance(n, bool) or n < 2 or None in (low, median, high) or not low <= median <= high:
            result["wind_spread"] = None
            issues.append("wind_spread:invalid")
        else:
            result["wind_spread"] = {"low": low, "median": median, "high": high, "n": n}
    result["data_issues"] = issues
    return result


def _sanitize_summary(data):
    if not isinstance(data, dict):
        return data
    result = dict(data)
    for field in ("wind_avg", "wind_max", "gust_max", "swell_max", "wind_low", "wind_high", "precipitation_sum_mm", "uv_index_max"):
        if field in result and result[field] is not None:
            result[field] = _finite(result[field], minimum=0)
    if result.get("sunshine_duration_hours") is not None:
        result["sunshine_duration_hours"] = _finite(
            result["sunshine_duration_hours"], minimum=0, maximum=24
        )
    for field in ("precipitation_probability_max_pct", "cloud_cover_mean_pct"):
        if field in result and result[field] is not None:
            result[field] = _finite(result[field], minimum=0, maximum=100)
    for field in ("air_min", "air_max", "temperature_min_c", "temperature_max_c", "apparent_temperature_min_c", "apparent_temperature_max_c"):
        if field in result and result[field] is not None:
            result[field] = _finite(result[field])
    if result.get("gust_max") is not None and result.get("wind_max") is not None and result["gust_max"] < result["wind_max"]:
        result["gust_max"] = None
    if result.get("air_min") is not None and result.get("air_max") is not None and result["air_min"] > result["air_max"]:
        result["air_min"] = result["air_max"] = None
    if result.get("wind_low") is not None and result.get("wind_high") is not None and result["wind_low"] > result["wind_high"]:
        result["wind_low"] = result["wind_high"] = None
    return result


class SpreadBand(BaseModel):
    """Multi-model consensus band for one variable (Sprint 18, Phase 1).

    ``median`` is the consensus; ``low``/``high`` are the min/max across models;
    ``n`` is how many models reported (1 => no real spread, graceful fallback).
    """

    low: float | None = None
    high: float | None = None
    median: float | None = None
    n: int = 0

    @model_validator(mode="after")
    def valid_relationship(self):
        if self.n < 2 or None in (self.low, self.median, self.high) or not self.low <= self.median <= self.high:
            raise ValueError("spread requires n >= 2 and low <= median <= high")
        return self


ObservationType = Literal["measurement", "nowcast", "forecast"]
AvailabilityStatus = Literal[
    "available", "available_stale", "not_applicable_inland",
    "unavailable_out_of_range", "unavailable_provider", "unknown_location_type",
]


class CoordinateRead(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ValueProvenance(BaseModel):
    """Canonical provenance shared by point weather values (weather-v4)."""

    contract_version: Literal["weather-v6"] = "weather-v6"
    source_type: Literal["measurement", "model_nowcast", "forecast"]
    observation_type: ObservationType  # temporary compatibility alias
    source: str
    provider: str
    model: str | None = None
    model_family: str | None = None
    observation_at: datetime | None = None
    valid_at: datetime | None = None
    captured_at: datetime
    calculated_at: datetime | None = None
    model_run_at: datetime | None = None
    model_run_quality: Literal["exact", "provider-reported", "capture-time-only", "unknown"] = "unknown"
    model_run: datetime | None = None  # deprecated alias
    issued_at: datetime | None = None  # deprecated; never synthesized as model run
    spot_timezone: str = "UTC"
    requested_coordinate: CoordinateRead
    used_coordinate: CoordinateRead | None = None
    grid_distance_km: float | None = Field(default=None, ge=0)
    spatial_resolution_km: float | None = Field(default=None, gt=0)
    temporal_resolution_minutes: int | None = Field(default=None, gt=0)
    age_seconds: int | None = Field(default=None, ge=0)
    stale: bool = False
    availability: AvailabilityStatus = "available"
    quality_tier: str
    attribution: list[dict] = Field(default_factory=list)
    uncertainty: Literal["determined", "limited", "not_determined"] = "not_determined"
    data_issues: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def timezone_aware(self):
        for value in (
            self.observation_at, self.valid_at, self.captured_at,
            self.calculated_at, self.model_run_at, self.model_run, self.issued_at,
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("canonical weather timestamps must be timezone-aware")
        return self


class CurrentSourceMap(BaseModel):
    wind: ValueProvenance
    air: ValueProvenance
    marine: ValueProvenance


class WaveComponentRead(BaseModel):
    """One physical wave component. Directions are meteorological FROM bearings."""

    significant_height_m: float | None = Field(default=None, ge=0)
    mean_period_s: float | None = Field(default=None, ge=0)
    peak_period_s: float | None = Field(default=None, ge=0)
    mean_direction_from_deg: float | None = Field(default=None, ge=0, lt=360)
    peak_direction_from_deg: float | None = Field(default=None, ge=0, lt=360)
    source: str | None = None
    quality_tier: str | None = None


class WaveComponentsRead(BaseModel):
    total_wave: WaveComponentRead | None = None
    wind_sea: WaveComponentRead | None = None
    primary_swell: WaveComponentRead | None = None
    secondary_swell: WaveComponentRead | None = None
    phase_speed_ms: float | None = None
    group_speed_ms: float | None = None


class MeasurementRead(BaseModel):
    observation_type: Literal["measurement"] = "measurement"
    station_id: uuid.UUID
    provider: str
    provider_station_id: str
    observed_at: datetime
    age_seconds: int = Field(ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    wind_speed_ms: float | None = Field(default=None, ge=0)
    wind_gust_ms: float | None = Field(default=None, ge=0)
    wind_direction_from_deg: float | None = Field(default=None, ge=0, lt=360)
    quality: int | None = None
    station_name: str | None = None
    stale: bool = False
    provenance: ValueProvenance | None = None

    @model_validator(mode="after")
    def aware_observation(self):
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("measurement observed_at must be timezone-aware")
        return self


class CurrentConditions(BaseModel):
    wind: float | None = None       # knots (consensus median)
    gust: float | None = None       # knots (consensus median)
    wind_ms: float | None = None    # canonical m/s value
    gust_ms: float | None = None    # canonical m/s value
    dir: float | None = None        # degrees, wind direction (primary model)
    air: float | None = None        # deg C (primary model)
    sst: float | None = None        # deg C
    swell: float | None = None      # m
    period: float | None = None     # s
    swell_dir: float | None = None  # degrees
    wind_spread: SpreadBand | None = None
    gust_spread: SpreadBand | None = None
    waves: WaveComponentsRead | None = None
    coastal_normal_deg: float | None = Field(default=None, ge=0, lt=360)
    coastal_classification: str | None = None
    wave_coastal_classification: str | None = None

    @model_validator(mode="before")
    @classmethod
    def sanitize_values(cls, data):
        return _sanitize_conditions(data)


class LiveConditionsRead(BaseModel):
    spot_id: uuid.UUID
    model: str                       # primary/home model (back-compat label)
    models: list[str] = []           # full consensus set that was fetched
    time: str | None = None
    observation_type: ObservationType = "nowcast"
    calculated: bool = True
    resolution: str | None = None
    trend: Literal["steigend", "fallend", "stabil"] | None = None
    quality_tier: str = "coordinates"
    coastal_classification: str | None = None
    coastal_normal_deg: float | None = Field(default=None, ge=0, lt=360)
    availability: dict[str, str] = Field(default_factory=dict)
    provenance: ValueProvenance | None = None
    measurement: MeasurementRead | None = None
    current: CurrentConditions


class ForecastHour(BaseModel):
    time: str
    wind: float | None = None        # consensus median
    gust: float | None = None        # consensus median
    wind_ms: float | None = None     # canonical m/s value
    gust_ms: float | None = None     # canonical m/s value
    dir: float | None = None
    air: float | None = None
    swell: float | None = None
    period: float | None = None
    swell_dir: float | None = None
    precip: float | None = None      # mm/h
    sst: float | None = None         # deg C
    apparent_temperature_c: float | None = None
    cloud_cover_pct: float | None = None
    pressure_msl_hpa: float | None = None
    uv_index: float | None = None
    weather_code: int | None = None
    weather_condition: str = "unknown"
    is_day: bool | None = None
    wind_spread: SpreadBand | None = None
    data_issues: list[str] = Field(default_factory=list)
    observation_type: Literal["forecast"] = "forecast"
    waves: WaveComponentsRead | None = None
    provenance: ValueProvenance | None = None
    sources: CurrentSourceMap | None = None
    coastal_normal_deg: float | None = Field(default=None, ge=0, lt=360)
    coastal_classification: str | None = None
    wave_coastal_classification: str | None = None
    quality_tier: str | None = None
    stale: bool = False

    @model_validator(mode="before")
    @classmethod
    def sanitize_values(cls, data):
        return _sanitize_conditions(data)


class ForecastDaySummary(BaseModel):
    wind_avg: float | None = None
    wind_max: float | None = None
    gust_max: float | None = None
    air_min: float | None = None
    air_max: float | None = None
    swell_max: float | None = None
    total_wave_max: float | None = None
    primary_swell_max: float | None = None
    wind_low: float | None = None    # model-spread band around the day's peak wind
    wind_high: float | None = None
    local_date: str | None = None
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None
    apparent_temperature_min_c: float | None = None
    apparent_temperature_max_c: float | None = None
    precipitation_sum_mm: float | None = None
    precipitation_probability_max_pct: float | None = None
    cloud_cover_mean_pct: float | None = None
    uv_index_max: float | None = None
    sunshine_duration_hours: float | None = None
    weather_code: int | None = None
    weather_condition: str = "unknown"
    sunrise_at: str | None = None
    sunset_at: str | None = None
    solar_state: str = "unavailable"

    @model_validator(mode="before")
    @classmethod
    def sanitize_values(cls, data):
        return _sanitize_summary(data)


class ForecastDay(BaseModel):
    date: str
    local_date: str | None = None
    confidence: Literal["hoch", "mittel", "niedrig"]
    summary: ForecastDaySummary
    hours: list[ForecastHour]
    detail: Literal["hourly", "trend"]
    confidence_source: Literal["spread", "calendar"] | None = None


class ForecastSeriesRead(BaseModel):
    spot_id: uuid.UUID
    model: str
    models: list[str] = []
    generated_at: str
    days: list[ForecastDay]
    product: str = "Surfwinddata Forecast"
    updated_at: str | None = None
    confidence_note: str | None = None
    attributions: list[dict] = []
    stale: bool = False
    contract_version: str | None = None
    timezone: str = "UTC"
    availability: dict[str, str] = {}
    calibrated: bool = False
    observation_type: Literal["forecast"] = "forecast"
