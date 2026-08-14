"""Read schemas for the live + forecast endpoints (Sprint 3; consensus band Sprint 18)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class SpreadBand(BaseModel):
    """Multi-model consensus band for one variable (Sprint 18, Phase 1).

    ``median`` is the consensus; ``low``/``high`` are the min/max across models;
    ``n`` is how many models reported (1 => no real spread, graceful fallback).
    """

    low: float | None = None
    high: float | None = None
    median: float | None = None
    n: int = 0


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


class LiveConditionsRead(BaseModel):
    spot_id: uuid.UUID
    model: str                       # primary/home model (back-compat label)
    models: list[str] = []           # full consensus set that was fetched
    time: str | None = None
    current: CurrentConditions


class ForecastHour(BaseModel):
    time: str
    wind: float | None = None        # consensus median
    gust: float | None = None        # consensus median
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


class ForecastDaySummary(BaseModel):
    wind_avg: float | None = None
    wind_max: float | None = None
    gust_max: float | None = None
    air_min: float | None = None
    air_max: float | None = None
    swell_max: float | None = None
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
    weather_code: int | None = None
    weather_condition: str = "unknown"
    sunrise_at: str | None = None
    sunset_at: str | None = None
    solar_state: str = "unavailable"


class ForecastDay(BaseModel):
    date: str
    local_date: str | None = None
    confidence: str  # hoch | mittel | niedrig (derived from model spread)
    summary: ForecastDaySummary
    hours: list[ForecastHour]


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
