from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

FIELD_CONTRACT_VERSION = "weather-field-v1"


class BoundingBox(BaseModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def ordered(self):
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("field bounds must be ordered")
        return self


class FieldLayer(BaseModel):
    variable: Literal[
        "wind_u", "wind_v", "wind_speed", "wind_gust",
        "total_wave_height", "total_wave_direction_from",
        "wind_sea_height", "primary_swell_height", "primary_swell_direction_from",
        "secondary_swell_height", "secondary_swell_direction_from",
    ]
    unit: str
    encoding: str
    scale_min: float | None = None
    scale_max: float | None = None
    direction_convention: Literal["from", "to"] | None = None


class FieldManifest(BaseModel):
    contract_version: Literal["weather-field-v1"] = FIELD_CONTRACT_VERSION
    snapshot_id: str
    provider: str
    model: str
    model_run: datetime
    issued_at: datetime
    valid_times: list[datetime]
    coverage: BoundingBox
    zoom_min: int = Field(ge=0, le=22)
    zoom_max: int = Field(ge=0, le=22)
    tile_format: Literal["webp", "png", "mvt", "lerc", "geotiff"]
    tile_url_template: str
    layers: list[FieldLayer]
    quality_status: Literal["experimental", "provisional", "validated", "stale"]
    processing_version: str
    attribution: list[dict]
    stale: bool = False

    @model_validator(mode="after")
    def valid_manifest(self):
        if self.zoom_min > self.zoom_max:
            raise ValueError("zoom_min must not exceed zoom_max")
        for instant in [self.model_run, self.issued_at, *self.valid_times]:
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise ValueError("field times must be timezone-aware")
        variables = {layer.variable for layer in self.layers}
        if ("wind_u" in variables) != ("wind_v" in variables):
            raise ValueError("wind field products require both u and v components")
        return self


class FieldAvailability(BaseModel):
    enabled: bool = False
    public: bool = False
    status: Literal["disabled", "blocked_credentials", "blocked_license", "building", "ready", "stale", "failed"] = "disabled"
    reason: str
    active_manifest: FieldManifest | None = None
    previous_snapshot_id: str | None = None

