import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.admin.constants import offered_variants
from app.schemas.common import GeoPoint
from app.scoring.context import typical_figures


def _public_editorial(value: Any) -> dict[str, Any] | None:
    """Remove internal scoring controls from the public editorial payload."""
    if not isinstance(value, dict):
        return None
    hidden = {"confidence_override"}
    return {key: item for key, item in value.items() if key not in hidden}


class SpotSummary(BaseModel):
    """Lightweight spot view for list/collection endpoints.

    Omits the legacy JSONB blobs (``climatology``, ``overrides``, raw
    ``editorial``) so a ``GET /spots?limit=500`` stays small — but still
    surfaces the few derived tile figures (typical wind/wave-height, region
    name/country and active V2 wind availability) collection views need, so a tile never has to
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
    facing: int | None = None
    image: dict[str, Any] | None = None
    # Variant keys this spot actually offers (suitability geeignet/eingeschraenkt).
    # Derived so tiles/filters can act on variants without the full blob.
    variants: list[str] = []
    # Exactly one of these is set, per the spot's primary sport (see
    # _typical_figures). Never a live reading — use GET /spots/live for that.
    typical_wind_kt: float | None = None
    typical_wave_height_m: float | None = None
    wind_availability: list[float] | None = None

    @classmethod
    def from_orm_spot(cls, spot: Any, wind_availability: list[float] | None = None) -> "SpotSummary":
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
            facing=spot.facing,
            image=spot.image,
            variants=offered_variants(getattr(spot, "variant_conditions", None)),
            typical_wind_kt=typical_wind_kt,
            typical_wave_height_m=typical_wave_height_m,
            wind_availability=wind_availability,
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
    facing: int | None = None
    editorial: dict[str, Any] | None = None
    overrides: dict[str, Any] | None = None
    variant_conditions: dict[str, Any] | None = None
    variants: list[str] = []
    image: dict[str, Any] | None = None
    finish_rank: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_spot(cls, spot: Any, *, public: bool = False) -> "SpotRead":
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
            facing=spot.facing,
            editorial=_public_editorial(spot.editorial) if public else spot.editorial,
            overrides=spot.overrides,
            variant_conditions=getattr(spot, "variant_conditions", None),
            variants=offered_variants(getattr(spot, "variant_conditions", None)),
            image=spot.image,
            finish_rank=getattr(spot, "finish_rank", None),
            created_at=spot.created_at,
            updated_at=spot.updated_at,
        )
