"""Strict, provider-neutral contract for immutable weather-field publications.

Version 1 remains the public disabled-gate contract.  Version 2 is additive and
is first exercised by the isolated phase-0 spike before any production
publication endpoint is switched over.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.spatial_fields.contracts import BoundingBox


FIELD_CONTRACT_V2 = "weather-field-v2"
FIELD_TILE_SCHEMA_V2 = "swd-field-tile-v2"
FIELD_TILE_SIZE_V2 = 128
FIELD_TILE_OVERLAP_V2 = 1
WIND_COMPONENT_SCALE_MS_V2 = 0.05
WIND_COMPONENT_OFFSET_MS_V2 = 0.0
WIND_COMPONENT_NODATA_V2 = -32768
TEMPERATURE_SCALE_C_V2 = 0.05
# 0.02 mm retains display-grade precision while covering 655.34 mm in int16.
PRECIPITATION_SCALE_MM_V2 = 0.02
PRESSURE_SCALE_HPA_V2 = 0.1
CLOUD_COVER_SCALE_PERCENT_V2 = 0.1
WAVE_HEIGHT_SCALE_M_V2 = 0.01
WAVE_DIRECTION_SCALE_DEG_V2 = 0.1
WAVE_PERIOD_SCALE_S_V2 = 0.1
FRESH_MAX_AGE_SECONDS = 9 * 60 * 60
DELAYED_MAX_AGE_SECONDS = 15 * 60 * 60
STALE_MAX_AGE_SECONDS = 30 * 60 * 60

FieldVariable = Literal[
    "wind_u",
    "wind_v",
    "wind_gust",
    "temperature_2m",
    "precipitation",
    "pressure_msl",
    "cloud_cover",
    "wave_u",
    "wave_v",
    "total_wave_height",
    "total_wave_direction",
    "total_wave_period",
    "wind_sea_height",
    "wind_sea_direction",
    "wind_sea_period",
    "primary_swell_height",
    "primary_swell_direction",
    "primary_swell_period",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NativeGridDefinition(StrictModel):
    """Reproducible native model-grid identity, not a marketing resolution."""

    projection: str = Field(min_length=1)
    grid_type: str = Field(min_length=1)
    rows: int = Field(gt=1)
    columns: int = Field(gt=1)
    longitude_convention: Literal["-180_180", "0_360"]
    scanning_mode: dict[str, bool | int | str]
    definition: dict[str, bool | int | float | str]
    coordinates_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResolutionDefinition(StrictModel):
    approximate_km: float = Field(gt=0)
    description: str = Field(min_length=1)


class VariableDefinition(StrictModel):
    name: FieldVariable
    unit: Literal["m/s", "°C", "mm", "hPa", "%", "m", "°", "s"] = "m/s"
    semantic: Literal[
        "eastward",
        "northward",
        "magnitude",
        "air_temperature",
        "accumulation",
        "mean_sea_level_pressure",
        "fraction",
        "wave_eastward",
        "wave_northward",
        "wave_height",
        "direction_from",
        "wave_period",
    ]
    height_m: float | None = Field(default=None, gt=0)


class QuantizedVariable(StrictModel):
    variable: FieldVariable
    stored_dtype: Literal["int16"] = "int16"
    scale: float = Field(gt=0)
    offset: float = 0.0
    nodata: int = Field(default=-32768, ge=-32768, le=32767)


class QuantizationDefinition(StrictModel):
    policy: Literal["contract_global"] = "contract_global"
    variables: list[QuantizedVariable]

    @model_validator(mode="after")
    def unique_and_vector_consistent(self):
        by_name = {item.variable: item for item in self.variables}
        if len(by_name) != len(self.variables):
            raise ValueError("quantization variables must be unique")
        vector_pair = next(
            (pair for pair in (("wind_u", "wind_v"), ("wave_u", "wave_v")) if set(pair).issubset(by_name)),
            None,
        )
        if vector_pair is None:
            raise ValueError("a paired wind or wave vector quantization is required")
        u, v = by_name[vector_pair[0]], by_name[vector_pair[1]]
        if (u.scale, u.offset, u.nodata) != (v.scale, v.offset, v.nodata):
            raise ValueError("paired vector components must share scale, offset and nodata")
        return self


class TileLod(StrictModel):
    source_zoom: int = Field(ge=0, le=22)
    consumer_zoom_min: int = Field(ge=0, le=22)
    consumer_zoom_max: int = Field(ge=0, le=22)
    source_decimation: int = Field(ge=1)

    @model_validator(mode="after")
    def ordered(self):
        if self.consumer_zoom_min > self.consumer_zoom_max:
            raise ValueError("LOD consumer_zoom_min must not exceed consumer_zoom_max")
        return self


class TileSchemeDefinition(StrictModel):
    schema_version: Literal["swd-field-tile-v2"] = FIELD_TILE_SCHEMA_V2
    coordinates: Literal["xyz"] = "xyz"
    projection: Literal["EPSG:3857"] = "EPSG:3857"
    tile_size: int = Field(ge=32, le=512)
    overlap: int = Field(ge=1, le=8)
    layout: Literal["planar"] = "planar"
    byte_order: Literal["little"] = "little"
    spatial_interpolation: Literal["bilinear_uv"] = "bilinear_uv"
    temporal_interpolation: Literal["linear_uv"] = "linear_uv"
    lod: list[TileLod]

    @model_validator(mode="after")
    def valid_lod(self):
        ordered = sorted(self.lod, key=lambda item: item.consumer_zoom_min)
        if not ordered:
            raise ValueError("at least one LOD range is required")
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.consumer_zoom_min <= previous.consumer_zoom_max:
                raise ValueError("LOD ranges must not overlap")
        return self


def classify_freshness(age_seconds: int) -> Literal["fresh", "delayed", "stale", "expired"]:
    if age_seconds < 0:
        raise ValueError("freshness age must not be negative")
    if age_seconds <= FRESH_MAX_AGE_SECONDS:
        return "fresh"
    if age_seconds <= DELAYED_MAX_AGE_SECONDS:
        return "delayed"
    if age_seconds <= STALE_MAX_AGE_SECONDS:
        return "stale"
    return "expired"


class FreshnessDefinition(StrictModel):
    status: Literal["fresh", "delayed", "stale", "expired"]
    model_run_at: datetime
    source_discovered_at: datetime
    processing_started_at: datetime
    published_at: datetime
    expected_next_run_at: datetime
    age_seconds: int = Field(ge=0)

    @field_validator(
        "model_run_at",
        "source_discovered_at",
        "processing_started_at",
        "published_at",
        "expected_next_run_at",
    )
    @classmethod
    def utc_only(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("field timestamps must be timezone-aware UTC")
        return value

    @model_validator(mode="after")
    def ordered_and_consistent(self):
        if not (
            self.model_run_at <= self.source_discovered_at
            <= self.processing_started_at
            <= self.published_at
        ):
            raise ValueError("freshness timestamps must follow publication order")
        if self.expected_next_run_at <= self.model_run_at:
            raise ValueError("expected_next_run_at must be after model_run_at")
        actual_age = int((self.published_at - self.model_run_at).total_seconds())
        if abs(actual_age - self.age_seconds) > 1:
            raise ValueError("freshness age_seconds must match published_at - model_run_at")
        if self.status != classify_freshness(self.age_seconds):
            raise ValueError("freshness status does not match the v2 age thresholds")
        return self


class AttributionDefinition(StrictModel):
    provider: str = Field(min_length=1)
    text: str = Field(min_length=1)
    url: str = Field(min_length=1)
    licence: str = Field(min_length=1)


class ChecksumDefinition(StrictModel):
    algorithm: Literal["sha256"] = "sha256"
    asset_index: str = Field(pattern=r"^[0-9a-f]{64}$")


class FieldManifestV2(StrictModel):
    contract_version: Literal["weather-field-v2"] = FIELD_CONTRACT_V2
    publication_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_run: datetime
    published_at: datetime
    valid_times: list[datetime]
    coverage: BoundingBox
    grid: NativeGridDefinition
    native_resolution: ResolutionDefinition
    display_resolution: ResolutionDefinition
    variables: list[VariableDefinition]
    quantization: QuantizationDefinition
    compression: Literal["none", "gzip", "brotli"]
    tile_scheme: TileSchemeDefinition
    processing_version: str = Field(min_length=1)
    quality_status: Literal["experimental", "candidate", "validated", "rejected"]
    freshness: FreshnessDefinition
    attribution: list[AttributionDefinition]
    field_template: str = Field(min_length=1)
    series_template: str | None = Field(default=None, min_length=1)
    checksums: ChecksumDefinition

    @field_validator("model_run", "published_at")
    @classmethod
    def utc_only(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("field timestamps must be timezone-aware UTC")
        return value

    @field_validator("valid_times")
    @classmethod
    def valid_times_are_utc_unique_and_ordered(
        cls, values: list[datetime]
    ) -> list[datetime]:
        if not values:
            raise ValueError("at least one valid time is required")
        for value in values:
            cls.utc_only(value)
        if values != sorted(values) or len(values) != len(set(values)):
            raise ValueError("valid_times must be sorted and unique")
        return values

    @model_validator(mode="after")
    def complete_vector_publication(self):
        names = [item.name for item in self.variables]
        if len(names) != len(set(names)):
            raise ValueError("field variables must be unique")
        vector_pair = next(
            (pair for pair in (("wind_u", "wind_v"), ("wave_u", "wave_v")) if set(pair).issubset(names)),
            None,
        )
        if vector_pair is None:
            raise ValueError("field publications require a paired wind or wave vector")
        if not self.attribution:
            raise ValueError("field attribution must not be empty")
        required_tokens = {"{valid_time}", "{z}", "{x}", "{y}"}
        if not required_tokens.issubset(
            {token for token in required_tokens if token in self.field_template}
        ):
            raise ValueError("field_template must contain valid_time/z/x/y tokens")
        if self.series_template and not all(
            token in self.series_template for token in ("{z}", "{x}", "{y}")
        ):
            raise ValueError("series_template must contain z/x/y tokens")
        if self.freshness.model_run_at != self.model_run:
            raise ValueError("freshness model_run_at must match model_run")
        if self.freshness.published_at != self.published_at:
            raise ValueError("freshness published_at must match published_at")
        if self.quality_status != "experimental":
            quantization = {item.variable: item for item in self.quantization.variables}
            for variable in vector_pair:
                item = quantization[variable]
                expected_scale = (
                    WIND_COMPONENT_SCALE_MS_V2
                    if variable.startswith("wind_")
                    else WAVE_HEIGHT_SCALE_M_V2
                )
                if (item.scale, item.offset, item.nodata) != (expected_scale, 0.0, -32768):
                    raise ValueError("non-experimental publications must use the frozen v2 quantization")
            if self.compression != "gzip":
                raise ValueError("non-experimental publications must use gzip")
            if (
                self.tile_scheme.tile_size != FIELD_TILE_SIZE_V2
                or self.tile_scheme.overlap != FIELD_TILE_OVERLAP_V2
            ):
                raise ValueError("non-experimental publications must use the frozen v2 tile geometry")
            lod = [
                (
                    item.source_zoom,
                    item.consumer_zoom_min,
                    item.consumer_zoom_max,
                    item.source_decimation,
                )
                for item in self.tile_scheme.lod
            ]
            if lod != [(4, 0, 5, 1), (5, 6, 8, 1)]:
                raise ValueError("non-experimental publications must use the frozen v2 LOD profile")
        return self
