"""Provider-neutral scalar field contract for tide-map publications."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.spatial_fields.contracts import BoundingBox


MARINE_FIELD_CONTRACT = "marine-field-v1"
MarineVariable = Literal[
    "tide_elevation_model_m",
    "tide_level_normalized",
    "tide_phase_rate",
    "tide_range_model_m",
    "total_water_level_model_m",
    "non_tidal_residual_m",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MarineVariableDefinition(StrictModel):
    name: MarineVariable
    unit: Literal["m", "1", "1/s"]
    datum: str | None = None
    navigational: bool = False

    @model_validator(mode="after")
    def datum_and_navigation_are_safe(self):
        if self.name.endswith("_model_m") and not self.datum:
            raise ValueError("metric water levels require an explicit model datum")
        if self.navigational:
            raise ValueError("marine-field-v1 does not publish navigational water levels")
        return self


class MarineAttribution(StrictModel):
    provider: str = Field(min_length=1)
    text: str = Field(min_length=1)
    url: str = Field(min_length=1)
    licence: str = Field(min_length=1)


class MarineFieldManifest(StrictModel):
    contract_version: Literal["marine-field-v1"] = MARINE_FIELD_CONTRACT
    publication_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_run: datetime
    published_at: datetime
    valid_times: list[datetime]
    coverage: BoundingBox
    variables: list[MarineVariableDefinition]
    wet_mask_version: str = Field(min_length=1)
    spatial_interpolation: Literal["bilinear_connected_wet"] = "bilinear_connected_wet"
    temporal_interpolation: Literal["linear"] = "linear"
    quality_status: Literal["experimental", "candidate", "validated", "rejected"]
    field_template: str = Field(min_length=1)
    series_template: str = Field(min_length=1)
    processing_version: str = Field(min_length=1)
    attribution: list[MarineAttribution]

    @field_validator("model_run", "published_at")
    @classmethod
    def utc_only(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("marine field timestamps must be timezone-aware UTC")
        return value

    @field_validator("valid_times")
    @classmethod
    def ordered_times(cls, values: list[datetime]) -> list[datetime]:
        if not values or values != sorted(values) or len(values) != len(set(values)):
            raise ValueError("valid_times must be non-empty, sorted and unique")
        for value in values:
            cls.utc_only(value)
        return values

    @model_validator(mode="after")
    def complete_publication(self):
        names = [item.name for item in self.variables]
        if len(names) != len(set(names)):
            raise ValueError("marine variables must be unique")
        if "tide_level_normalized" not in names:
            raise ValueError("every tide map requires tide_level_normalized")
        if not all(token in self.field_template for token in ("{valid_time}", "{z}", "{x}", "{y}")):
            raise ValueError("field_template must contain valid_time/z/x/y tokens")
        if not all(token in self.series_template for token in ("{z}", "{x}", "{y}")):
            raise ValueError("series_template must contain z/x/y tokens")
        if not self.attribution:
            raise ValueError("marine field attribution must not be empty")
        return self
