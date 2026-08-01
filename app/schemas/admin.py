"""Request schemas for the admin write endpoints (Sprint 8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.admin.constants import (
    validate_facilities,
    validate_level,
    validate_styles,
    validate_water_character,
)


class SpotCreate(BaseModel):
    name: str
    region_id: uuid.UUID
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    sports: list[str] = Field(default_factory=list)
    slug: str | None = None
    water_type: str | None = None
    bottom_type: str | None = None
    level: str | None = None
    water_character: str | None = None
    style: list[str] = Field(default_factory=list)
    facilities: dict[str, Any] | None = None
    facing: int | None = Field(default=None, ge=0, le=359)
    model_pref: str | None = None
    editorial: dict[str, Any] | None = None

    _v_level = field_validator("level")(staticmethod(validate_level))
    _v_water = field_validator("water_character")(
        staticmethod(validate_water_character)
    )
    _v_style = field_validator("style")(staticmethod(validate_styles))
    _v_fac = field_validator("facilities")(staticmethod(validate_facilities))

    def to_data(self) -> dict:
        return self.model_dump(exclude_none=False)


class SpotUpdate(BaseModel):
    """Partial spot update. Only fields *set* on the request are applied, so a
    caller can clear a value (send ``null``) without touching the others."""

    name: str | None = None
    slug: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    sports: list[str] | None = None
    water_type: str | None = None
    bottom_type: str | None = None
    level: str | None = None
    water_character: str | None = None
    style: list[str] | None = None
    facilities: dict[str, Any] | None = None
    facing: int | None = Field(default=None, ge=0, le=359)
    model_pref: str | None = None
    editorial: dict[str, Any] | None = None
    # Optimistic-locking token: the ``updated_at`` the client loaded. When set,
    # the route rejects the write (409) if the row changed meanwhile. Never a
    # data column — excluded from ``to_data()``.
    expected_updated_at: datetime | None = None

    _v_level = field_validator("level")(staticmethod(validate_level))
    _v_water = field_validator("water_character")(
        staticmethod(validate_water_character)
    )
    _v_style = field_validator("style")(staticmethod(validate_styles))
    _v_fac = field_validator("facilities")(staticmethod(validate_facilities))

    def to_data(self) -> dict:
        """Only the fields the client actually sent (so absent ≠ null-clear).
        The locking token is stripped — it is not a persisted field."""
        return self.model_dump(exclude_unset=True, exclude={"expected_updated_at"})


class MetadataUpdate(BaseModel):
    """Editorial fields to merge. Each value may be a real value or ``"n/a"``."""

    editorial: dict[str, Any]


class FinishRankRequest(BaseModel):
    """Manual "Fertigstellen" rank override: red|yellow|green, or null for auto."""

    rank: str | None = None


class OverrideRequest(BaseModel):
    field: str
    value: Any


class RevertRequest(BaseModel):
    field: str


class ImageRequest(BaseModel):
    url: str
    source: str
    license: str
    credit: str

    def to_image(self) -> dict:
        return self.model_dump()


class ImageAttributionRequest(BaseModel):
    """Edit the current hero's rights fields in place (url + focal untouched)."""

    credit: str
    license: str
    source: str


class RegionCreate(BaseModel):
    name: str
    slug: str | None = None
    country: str | None = None
    lat: float | None = None
    lon: float | None = None
    description: str | None = None
    defaults: dict[str, Any] | None = None
    season: dict[str, Any] | None = None

    def to_data(self) -> dict:
        return self.model_dump(exclude_none=False)


class RegionDefaultsUpdate(BaseModel):
    defaults: dict[str, Any]


class RegionUpdate(BaseModel):
    """Partial region edit: only the fields sent are applied."""

    name: str | None = None
    country: str | None = None
    description: str | None = None
    defaults: dict[str, Any] | None = None
    season: dict[str, Any] | None = None
    # See SpotUpdate.expected_updated_at.
    expected_updated_at: datetime | None = None

    def to_data(self) -> dict:
        return self.model_dump(exclude_unset=True, exclude={"expected_updated_at"})


class RegionImageRequest(BaseModel):
    url: str
    source: str = "manual"
    license: str = "own"
    credit: str

    def to_image(self) -> dict:
        return self.model_dump()


class AssignRegionRequest(BaseModel):
    region_id: uuid.UUID


class BulkAssignRegionRequest(BaseModel):
    spot_ids: list[uuid.UUID]
    region_id: uuid.UUID


class BulkUnassignRegionRequest(BaseModel):
    spot_ids: list[uuid.UUID]
