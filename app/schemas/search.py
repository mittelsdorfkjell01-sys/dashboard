"""Request schemas for the search endpoints (Sprint 5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Bounds(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class GeometryRequest(BaseModel):
    """A drawn circle or rectangle to search within."""

    type: Literal["circle", "rectangle"]
    # circle
    center_lat: float | None = None
    center_lon: float | None = None
    radius_km: float | None = Field(default=None, gt=0)
    # rectangle
    bounds: Bounds | None = None
    # filters / context
    sport: str | None = None
    variant: str | None = None
    week: int | None = Field(default=None, ge=1, le=52)

    def to_shape(self) -> dict:
        if self.type == "circle":
            if self.center_lat is None or self.center_lon is None or self.radius_km is None:
                raise ValueError("circle requires center_lat, center_lon, radius_km")
            return {
                "type": "circle",
                "center": {"lat": self.center_lat, "lon": self.center_lon},
                "radius_km": self.radius_km,
            }
        if self.bounds is None:
            raise ValueError("rectangle requires bounds")
        return {"type": "rectangle", "bounds": self.bounds.model_dump()}
