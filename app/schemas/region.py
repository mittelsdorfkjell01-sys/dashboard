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

    @classmethod
    def from_orm_region(cls, region: Any) -> "RegionRead":
        return cls(
            id=region.id,
            slug=region.slug,
            name=region.name,
            country=region.country,
            center=GeoPoint.from_geo(region.center),
            bounds=GeoPolygon.from_geo(region.bounds),
            description=region.description,
            image=region.image,
            season=region.season,
            defaults=region.defaults,
            status=getattr(region, "status", "published"),
            created_at=region.created_at,
            updated_at=region.updated_at,
        )
