from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator


class DatasetReference(BaseModel):
    key: str
    version: str
    source: str
    licence: str
    acquired_at: datetime | None = None
    horizontal_resolution_m: float = Field(gt=0)
    vertical_resolution_m: float | None = Field(default=None, gt=0)
    vertical_datum: str | None = None
    quality_index: float | None = Field(default=None, ge=0, le=1)
    coverage: dict
    raw_measurement_provenance: str | None = None


class NearshoreInput(BaseModel):
    spot_id: str
    valid_at: datetime
    offshore_waves: dict
    bathymetry: DatasetReference
    coastline: DatasetReference
    tide_or_sea_level_m: float | None = None
    surface_current: dict | None = None
    wind: dict | None = None
    seabed: dict | None = None
    model_configuration: dict

    @model_validator(mode="after")
    def complete_physics(self):
        if self.valid_at.tzinfo is None or self.valid_at.utcoffset() is None:
            raise ValueError("nearshore valid_at must be timezone-aware")
        if not self.offshore_waves.get("total_wave"):
            raise ValueError("nearshore input requires an offshore total-wave component")
        return self


class NearshoreOutput(BaseModel):
    status: Literal["computed", "unavailable", "failed"]
    transformed_significant_height_m: float | None = Field(default=None, ge=0)
    period_s: float | None = Field(default=None, ge=0)
    direction_from_deg: float | None = Field(default=None, ge=0, lt=360)
    phase_speed_ms: float | None = Field(default=None, ge=0)
    group_speed_ms: float | None = Field(default=None, ge=0)
    breaker_fraction: float | None = Field(default=None, ge=0, le=1)
    breaking_probability: float | None = Field(default=None, ge=0, le=1)
    likely_breaking_zone: dict | None = None
    incidence_angle_to_coast_normal_deg: float | None = Field(default=None, ge=-180, le=180)
    quality: dict
    bathymetry_version: str
    model_version: str


class NearshoreEngine(Protocol):
    def run(self, request: NearshoreInput) -> NearshoreOutput: ...

