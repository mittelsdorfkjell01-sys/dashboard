"""Provider-neutral internal contracts for wind forecast ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ModelFamily(StrEnum):
    REGIONAL = "regional"
    IFS = "ifs"
    GFS = "gfs"
    AIFS = "aifs"
    ICON_GLOBAL = "icon_global"
    ENSEMBLE = "ensemble"
    OTHER = "other"


class ForecastRequest(BaseModel):
    """Canonical request passed to any weather provider adapter."""

    model_config = ConfigDict(frozen=True)

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    start: datetime
    end: datetime
    model_ids: tuple[str, ...]

    @field_validator("start", "end")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("weather timestamps must be timezone-aware UTC")
        if value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("weather timestamps must use UTC")
        return value

    @field_validator("model_ids")
    @classmethod
    def require_models(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not model.strip() for model in value):
            raise ValueError("at least one non-empty model id is required")
        if len(set(value)) != len(value):
            raise ValueError("model ids must be unique")
        return value

    @model_validator(mode="after")
    def require_ordered_window(self) -> "ForecastRequest":
        if self.end <= self.start:
            raise ValueError("forecast end must be after start")
        return self


class ForecastPoint(BaseModel):
    """One normalized model value. Speeds are m/s and time is UTC."""

    model_config = ConfigDict(frozen=True)

    valid_at: datetime
    model_id: str = Field(min_length=1)
    family: ModelFamily
    wind_speed_ms: float = Field(ge=0.0)
    wind_direction_deg: float = Field(ge=0.0, lt=360.0)
    gust_speed_ms: float | None = Field(default=None, ge=0.0)
    air_temperature_c: float | None = None
    pressure_msl_hpa: float | None = Field(default=None, gt=0.0)
    cloud_cover_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    low_cloud_cover_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    shortwave_radiation_wm2: float | None = Field(default=None, ge=0.0)
    precipitation_mm: float | None = Field(default=None, ge=0.0)

    @field_validator("valid_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        return ForecastRequest.require_utc(value)

    @model_validator(mode="after")
    def require_gust_not_below_mean(self) -> "ForecastPoint":
        if self.gust_speed_ms is not None and self.gust_speed_ms < self.wind_speed_ms:
            raise ValueError("gust speed must not be below mean wind speed")
        return self


class ProviderForecast(BaseModel):
    """Normalized response plus freshness metadata needed for quality flags."""

    model_config = ConfigDict(frozen=True)

    provider: str = Field(min_length=1)
    fetched_at: datetime
    model_runs: dict[str, datetime]
    points: tuple[ForecastPoint, ...]

    @field_validator("fetched_at")
    @classmethod
    def require_fetched_at_utc(cls, value: datetime) -> datetime:
        return ForecastRequest.require_utc(value)

    @field_validator("model_runs")
    @classmethod
    def require_run_times_utc(cls, value: dict[str, datetime]) -> dict[str, datetime]:
        for run_time in value.values():
            ForecastRequest.require_utc(run_time)
        return value
