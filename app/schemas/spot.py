import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.common import GeoPoint
from app.scoring.context import typical_figures


class SpotSummary(BaseModel):
    """Lightweight spot view for list/collection endpoints.

    Omits the heavy JSONB blobs (``climatology``, ``overrides``, raw
    ``editorial``) so a ``GET /spots?limit=500`` stays small — but still
    surfaces the few derived tile figures (typical wind/wave-height, region
    name/country, best_months) collection views need, so a tile never has to
    fall back to the single-spot detail endpoint just to render. Use
    :class:`SpotRead` when the full record is needed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    region_id: uuid.UUID | None = None
    region_name: str | None = None
    region_country: str | None = None
    location: GeoPoint | None = None
    sports: list[str]
    water_type: list[str] = []
    bottom_type: list[str] = []
    level: list[str] = []
    water_character: list[str] = []
    style: list[str] = []
    facilities: dict[str, Any] | None = None
    status: str
    confidence: float | None = None
    facing: int | None = None
    image: dict[str, Any] | None = None
    # Exactly one of these is set, per the spot's primary sport (see
    # _typical_figures). Never a live reading — use GET /spots/live for that.
    typical_wind_kt: float | None = None
    typical_wave_height_m: float | None = None
    # Persisted cache (Spot.best_months); None until computed (see
    # app.scoring.region.aggregate_spot_best_months).
    best_months: list[int] | None = None

    @classmethod
    def from_orm_spot(cls, spot: Any) -> "SpotSummary":
        region = getattr(spot, "region", None)
        typical_wind_kt, typical_wave_height_m = typical_figures(spot)
        return cls(
            id=spot.id,
            slug=spot.slug,
            name=spot.name,
            region_id=spot.region_id,
            region_name=getattr(region, "name", None),
            region_country=getattr(region, "country", None),
            location=GeoPoint.from_geo(spot.location),
            sports=list(spot.sports or []),
            water_type=list(spot.water_type or []),
            bottom_type=list(spot.bottom_type or []),
            level=list(spot.level or []),
            water_character=list(spot.water_character or []),
            style=list(spot.style or []),
            facilities=spot.facilities,
            status=spot.status,
            confidence=spot.confidence,
            facing=spot.facing,
            image=spot.image,
            typical_wind_kt=typical_wind_kt,
            typical_wave_height_m=typical_wave_height_m,
            best_months=list(getattr(spot, "best_months", None) or []) or None,
        )


class SpotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    region_id: uuid.UUID | None = None
    region_name: str | None = None
    region_country: str | None = None
    location: GeoPoint | None = None
    era5_cell: dict[str, Any] | None = None
    model_pref: str | None = None
    sports: list[str]
    water_type: list[str] = []
    bottom_type: list[str] = []
    level: list[str] = []
    water_character: list[str] = []
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
        region = getattr(spot, "region", None)
        return cls(
            id=spot.id,
            slug=spot.slug,
            name=spot.name,
            region_id=spot.region_id,
            region_name=getattr(region, "name", None),
            region_country=getattr(region, "country", None),
            location=GeoPoint.from_geo(spot.location),
            era5_cell=spot.era5_cell,
            model_pref=spot.model_pref,
            sports=list(spot.sports or []),
            water_type=list(spot.water_type or []),
            bottom_type=list(spot.bottom_type or []),
            level=list(spot.level or []),
            water_character=list(spot.water_character or []),
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
