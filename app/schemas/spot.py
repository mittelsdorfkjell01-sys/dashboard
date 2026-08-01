import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.common import GeoPoint


class SpotSummary(BaseModel):
    """Lightweight spot view for list/collection endpoints.

    Deliberately omits the heavy JSONB blobs (``climatology``, ``overrides``,
    ``editorial``) so a ``GET /spots?limit=500`` stays small. Use :class:`SpotRead`
    on the single-spot detail endpoint when the full record is needed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    region_id: uuid.UUID | None = None
    location: GeoPoint | None = None
    sports: list[str]
    water_type: str | None = None
    bottom_type: str | None = None
    level: str | None = None
    water_character: str | None = None
    style: list[str] = []
    facilities: dict[str, Any] | None = None
    status: str
    confidence: float | None = None
    facing: int | None = None
    image: dict[str, Any] | None = None

    @classmethod
    def from_orm_spot(cls, spot: Any) -> "SpotSummary":
        return cls(
            id=spot.id,
            slug=spot.slug,
            name=spot.name,
            region_id=spot.region_id,
            location=GeoPoint.from_geo(spot.location),
            sports=list(spot.sports or []),
            water_type=spot.water_type,
            bottom_type=spot.bottom_type,
            level=spot.level,
            water_character=spot.water_character,
            style=list(spot.style or []),
            facilities=spot.facilities,
            status=spot.status,
            confidence=spot.confidence,
            facing=spot.facing,
            image=spot.image,
        )


class SpotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    region_id: uuid.UUID | None = None
    location: GeoPoint | None = None
    era5_cell: dict[str, Any] | None = None
    model_pref: str | None = None
    sports: list[str]
    water_type: str | None = None
    bottom_type: str | None = None
    level: str | None = None
    water_character: str | None = None
    style: list[str] = []
    facilities: dict[str, Any] | None = None
    status: str
    confidence: float | None = None
    facing: int | None = None
    editorial: dict[str, Any] | None = None
    climatology: dict[str, Any] | None = None
    overrides: dict[str, Any] | None = None
    image: dict[str, Any] | None = None
    finish_rank: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_spot(cls, spot: Any) -> "SpotRead":
        """Build a read schema from an ORM spot, converting the geography column."""
        return cls(
            id=spot.id,
            slug=spot.slug,
            name=spot.name,
            region_id=spot.region_id,
            location=GeoPoint.from_geo(spot.location),
            era5_cell=spot.era5_cell,
            model_pref=spot.model_pref,
            sports=list(spot.sports or []),
            water_type=spot.water_type,
            bottom_type=spot.bottom_type,
            level=spot.level,
            water_character=spot.water_character,
            style=list(spot.style or []),
            facilities=spot.facilities,
            status=spot.status,
            confidence=spot.confidence,
            facing=spot.facing,
            editorial=spot.editorial,
            climatology=spot.climatology,
            overrides=spot.overrides,
            image=spot.image,
            finish_rank=getattr(spot, "finish_rank", None),
            created_at=spot.created_at,
            updated_at=spot.updated_at,
        )
