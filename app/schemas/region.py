import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.common import GeoPoint, GeoPolygon


class RegionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    country: str | None = None
    center: GeoPoint | None = None
    bounds: GeoPolygon | None = None
    description: str | None = None
    image: dict[str, Any] | None = None
    season: dict[str, Any] | None = None
    defaults: dict[str, Any] | None = None
    status: str = "published"
    created_at: datetime
    updated_at: datetime
    # Published-spot rollup for the region. Defaults to empty so existing
    # detail/admin call sites that don't pass stats stay unaffected.
    spot_count: int = 0
    sports: list[str] = []

    @classmethod
    def from_orm_region(
        cls,
        region: Any,
        spot_count: int = 0,
        sports: list[str] | None = None,
    ) -> "RegionRead":
        return cls(
            id=region.id,
            slug=region.slug,
            name=region.name,
            country=region.country,
            center=GeoPoint.from_geo(region.center),
            bounds=GeoPolygon.from_geo(region.bounds),
            description=region.description,
            image=region.image,
            # Region wind availability is deliberately unknown until a V2
            # aggregation rule has been product-approved.
            season=None,
            defaults=region.defaults,
            status=getattr(region, "status", "published"),
            created_at=region.created_at,
            updated_at=region.updated_at,
            spot_count=spot_count,
            sports=sorted(sports or []),
        )
