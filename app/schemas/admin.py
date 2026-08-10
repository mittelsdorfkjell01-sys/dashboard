"""Request schemas for the admin write endpoints (Sprint 8)."""

from __future__ import annotations

import uuid
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

from app.admin.constants import (
    validate_bottom_types,
    validate_facilities,
    validate_levels,
    validate_styles,
    validate_water_characters,
    validate_water_types,
)


class AdminWriteModel(BaseModel):
    model_config = {"extra": "forbid"}


def _bounded_json(value: Any, *, label: str, max_bytes: int = 64_000) -> Any:
    if value is not None and len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > max_bytes:
        raise ValueError(f"{label} ist zu groß (maximal {max_bytes // 1000} KB)")
    return value


class SpotCreate(AdminWriteModel):
    name: str = Field(min_length=1, max_length=200)
    region_id: uuid.UUID
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    sports: list[str] = Field(default_factory=list, max_length=10)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    water_type: list[str] = Field(default_factory=list, max_length=8)
    bottom_type: list[str] = Field(default_factory=list, max_length=8)
    level: list[str] = Field(default_factory=list, max_length=8)
    water_character: list[str] = Field(default_factory=list, max_length=8)
    style: list[str] = Field(default_factory=list, max_length=8)
    facilities: dict[str, Any] | None = None
    facing: int | None = Field(default=None, ge=0, le=359)
    model_pref: str | None = Field(default=None, max_length=50)
    editorial: dict[str, Any] | None = None
    allow_duplicate: bool = False

    _v_level = field_validator("level")(staticmethod(validate_levels))
    _v_bottom = field_validator("bottom_type")(staticmethod(validate_bottom_types))
    _v_water = field_validator("water_character")(
        staticmethod(validate_water_characters)
    )
    _v_water_type = field_validator("water_type")(staticmethod(validate_water_types))
    _v_style = field_validator("style")(staticmethod(validate_styles))
    _v_fac = field_validator("facilities")(staticmethod(validate_facilities))

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name darf nicht leer sein")
        return value

    @field_validator("facilities", "editorial")
    @classmethod
    def _limit_json(cls, value: Any, info) -> Any:
        return _bounded_json(value, label=info.field_name)

    def to_data(self) -> dict:
        return self.model_dump(exclude_none=False, exclude={"allow_duplicate"})


class SpotUpdate(AdminWriteModel):
    """Partial spot update. Only fields *set* on the request are applied, so a
    caller can clear a value (send ``null``) without touching the others."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    region_id: uuid.UUID | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    sports: list[str] | None = Field(default=None, max_length=10)
    water_type: list[str] | None = Field(default=None, max_length=8)
    bottom_type: list[str] | None = Field(default=None, max_length=8)
    level: list[str] | None = Field(default=None, max_length=8)
    water_character: list[str] | None = Field(default=None, max_length=8)
    style: list[str] | None = Field(default=None, max_length=8)
    facilities: dict[str, Any] | None = None
    facing: int | None = Field(default=None, ge=0, le=359)
    model_pref: str | None = Field(default=None, max_length=50)
    editorial: dict[str, Any] | None = None
    # Optimistic-locking token: the ``updated_at`` the client loaded. When set,
    # the route rejects the write (409) if the row changed meanwhile. Never a
    # data column — excluded from ``to_data()``.
    expected_updated_at: datetime | None = None
    expected_values: dict[str, Any] | None = None
    allow_duplicate: bool = False

    _v_level = field_validator("level")(staticmethod(validate_levels))
    _v_bottom = field_validator("bottom_type")(staticmethod(validate_bottom_types))
    _v_water = field_validator("water_character")(
        staticmethod(validate_water_characters)
    )
    _v_water_type = field_validator("water_type")(staticmethod(validate_water_types))
    _v_style = field_validator("style")(staticmethod(validate_styles))
    _v_fac = field_validator("facilities")(staticmethod(validate_facilities))

    @model_validator(mode="after")
    def _coordinates_are_a_pair(self):
        has_lat = "lat" in self.model_fields_set
        has_lon = "lon" in self.model_fields_set
        if has_lat != has_lon or (has_lat and (self.lat is None or self.lon is None)):
            raise ValueError("Breiten- und Längengrad müssen gemeinsam angegeben werden")
        return self

    @field_validator("name")
    @classmethod
    def _clean_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name darf nicht leer sein")
        return value

    @field_validator("facilities", "editorial", "expected_values")
    @classmethod
    def _limit_json(cls, value: Any, info) -> Any:
        return _bounded_json(value, label=info.field_name)

    def to_data(self) -> dict:
        """Only the fields the client actually sent (so absent ≠ null-clear).
        The locking token is stripped — it is not a persisted field."""
        return self.model_dump(
            exclude_unset=True,
            exclude={"expected_updated_at", "expected_values", "allow_duplicate"},
        )


class MetadataUpdate(AdminWriteModel):
    """Editorial fields to merge. Each value may be a real value or ``"n/a"``."""

    editorial: dict[str, Any]

    @field_validator("editorial")
    @classmethod
    def _limit_editorial(cls, value: Any) -> Any:
        return _bounded_json(value, label="editorial")


class FinishRankRequest(AdminWriteModel):
    """Manual "Fertigstellen" rank override: red|yellow|green, or null for auto."""

    rank: Literal["red", "yellow", "green"] | None = None


class OverrideRequest(AdminWriteModel):
    field: str = Field(min_length=1, max_length=80)
    value: Any


class RevertRequest(AdminWriteModel):
    field: str = Field(min_length=1, max_length=80)


class ImageRequest(AdminWriteModel):
    url: AnyHttpUrl
    source: str = Field(min_length=1, max_length=120)
    license: str = Field(min_length=1, max_length=120)
    credit: str = Field(min_length=1, max_length=200)
    license_url: AnyHttpUrl | None = None
    credit_url: AnyHttpUrl | None = None
    source_page: AnyHttpUrl | None = None

    def to_image(self) -> dict:
        """Payload for ``app.media.image_object.build_image``.

        An operator pasting a URL is provenance ``manual``: whatever they typed
        into source/license is the claim of record — the picker (Sprint 3)
        writes machine-verified provenance through its own route instead.
        The URL is absolute by definition here, so the bytes are served from
        someone else's host: ``delivery="hotlinked"``.
        """
        data = self.model_dump()
        return {
            **data,
            "url": str(self.url),
            "license_url": str(self.license_url) if self.license_url else None,
            "credit_url": str(self.credit_url) if self.credit_url else None,
            "source_page": str(self.source_page) if self.source_page else None,
            "provider": "manual",
            "delivery": "hotlinked",
            "role": "hero",
        }


class ImageAttributionRequest(AdminWriteModel):
    """Edit the current hero's rights fields in place (url + focal untouched)."""

    credit: str = Field(min_length=1, max_length=200)
    license: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=120)


class RegionCreate(AdminWriteModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    country: str | None = Field(default=None, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    description: str | None = Field(default=None, max_length=20_000)
    defaults: dict[str, Any] | None = None
    season: dict[str, Any] | None = None
    allow_duplicate: bool = False

    @model_validator(mode="after")
    def _coordinates_are_a_pair(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("Breiten- und Längengrad müssen gemeinsam angegeben werden")
        return self

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name darf nicht leer sein")
        return value

    @field_validator("country")
    @classmethod
    def _upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("defaults", "season")
    @classmethod
    def _limit_json(cls, value: Any, info) -> Any:
        return _bounded_json(value, label=info.field_name)

    def to_data(self) -> dict:
        return self.model_dump(exclude_none=False, exclude={"allow_duplicate"})


class RegionDefaultsUpdate(AdminWriteModel):
    defaults: dict[str, Any]


class RegionUpdate(AdminWriteModel):
    """Partial region edit: only the fields sent are applied."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    country: str | None = Field(default=None, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    description: str | None = Field(default=None, max_length=20_000)
    defaults: dict[str, Any] | None = None
    season: dict[str, Any] | None = None
    # See SpotUpdate.expected_updated_at.
    expected_updated_at: datetime | None = None
    expected_values: dict[str, Any] | None = None
    allow_duplicate: bool = False

    @field_validator("name")
    @classmethod
    def _clean_optional_name(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None

    @field_validator("country")
    @classmethod
    def _upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("defaults", "season", "expected_values")
    @classmethod
    def _limit_json(cls, value: Any, info) -> Any:
        return _bounded_json(value, label=info.field_name)

    def to_data(self) -> dict:
        return self.model_dump(
            exclude_unset=True,
            exclude={"expected_updated_at", "expected_values", "allow_duplicate"},
        )


class RegionImageRequest(AdminWriteModel):
    url: AnyHttpUrl
    source: str = Field(default="manual", min_length=1, max_length=120)
    license: str = Field(default="own", min_length=1, max_length=120)
    # Non-empty since Sprint 1: attribution is mandatory for every image source,
    # and the server is where that is enforced — not only the form.
    credit: str = Field(min_length=1, max_length=200)
    license_url: AnyHttpUrl | None = None
    credit_url: AnyHttpUrl | None = None
    source_page: AnyHttpUrl | None = None

    def to_image(self) -> dict:
        return {
            **self.model_dump(),
            "url": str(self.url),
            "license_url": str(self.license_url) if self.license_url else None,
            "credit_url": str(self.credit_url) if self.credit_url else None,
            "source_page": str(self.source_page) if self.source_page else None,
            "provider": "manual",
            "delivery": "hotlinked",
            "role": "hero",
        }


class AssignRegionRequest(AdminWriteModel):
    region_id: uuid.UUID
    allow_duplicate: bool = False


class BulkAssignRegionRequest(AdminWriteModel):
    spot_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    region_id: uuid.UUID
    allow_duplicate: bool = False


class BulkUnassignRegionRequest(AdminWriteModel):
    spot_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    allow_duplicate: bool = False
