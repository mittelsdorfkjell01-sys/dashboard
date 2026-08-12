from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class GridPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=360)
    distance_km: float = Field(ge=0)


class NormalizedModelValue(BaseModel):
    provider: str
    model: str
    dataset_version: str | None = None
    model_run: datetime
    valid_at: datetime
    fetched_at: datetime
    grid_point: GridPoint
    horizontal_resolution_km: float = Field(gt=0)
    horizon_hours: int = Field(ge=0)
    u_ms: float
    v_ms: float
    speed_ms: float = Field(ge=0, le=100)
    direction_deg: float = Field(ge=0, lt=360)
    gust_ms: float | None = Field(default=None, ge=0, le=150)
    temperature_c: float | None = Field(default=None, ge=-100, le=70)
    precipitation_mm: float | None = Field(default=None, ge=0)
    complete: bool = True
    quality_flags: list[str] = []
    source_key: str

    @model_validator(mode="after")
    def validate_times_and_gust(self):
        for value in (self.model_run, self.valid_at, self.fetched_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("forecast timestamps must be timezone-aware")
        if self.gust_ms is not None and self.gust_ms < self.speed_ms:
            self.gust_ms = self.speed_ms
            self.quality_flags = [*self.quality_flags, "gust_clamped_to_mean"]
        return self


class ProviderRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    model: str
    run_at: datetime
    forecast_hours: tuple[int, ...]

    @model_validator(mode="after")
    def ordered(self):
        if self.run_at.tzinfo is None:
            raise ValueError("run_at must be timezone-aware")
        if tuple(sorted(set(self.forecast_hours))) != self.forecast_hours:
            raise ValueError("forecast_hours must be sorted and unique")
        return self
