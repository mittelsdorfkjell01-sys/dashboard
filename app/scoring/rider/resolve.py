"""Resolve a persisted or default rider into an internal scoring context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.models import AppUser, GearItem, RiderProfile, RiderSportProfile
from app.scoring.params import get_params
from app.scoring.rider.band import PersonalBand, personal_band


@dataclass(frozen=True, slots=True)
class RiderContext:
    sport: str
    source: str
    profile: dict[str, Any]
    band: PersonalBand
    profile_version: int | None


def resolve_rider(db: Any, app_user: AppUser | None, sport: str) -> RiderContext:
    params = get_params(sport, db=db)
    default = dict(params["default_rider"][sport])
    if app_user is None:
        return RiderContext(sport, "default", default, personal_band(default, sport, params), None)

    base = db.scalar(select(RiderProfile).where(RiderProfile.app_user_id == app_user.id))
    if base is None or base.weight_kg is None:
        return RiderContext(sport, "default", default, personal_band(default, sport, params), None)
    sport_profile = db.scalar(
        select(RiderSportProfile).where(
            RiderSportProfile.rider_profile_id == base.id,
            RiderSportProfile.sport == sport,
        )
    )
    if sport_profile is None:
        return RiderContext(sport, "default", default, personal_band(default, sport, params), None)

    gear = db.scalars(
        select(GearItem)
        .where(GearItem.rider_profile_id == base.id, GearItem.sport == sport)
        .order_by(GearItem.sort_order, GearItem.created_at)
    ).all()
    home_location = None
    if base.home_location is not None:
        from geoalchemy2.shape import to_shape

        point = to_shape(base.home_location)
        home_location = {"lat": float(point.y), "lon": float(point.x)}
    profile = {
        "weight_kg": float(base.weight_kg),
        "level": sport_profile.level,
        "style_weights": dict(sport_profile.style_weights or {}),
        "preferred_water_character": list(
            sport_profile.preferred_water_character or []
        ),
        "travel_mode": base.travel_mode,
        "home_location": home_location,
        "max_travel_km": (
            float(base.max_travel_km) if base.max_travel_km is not None else None
        ),
        "availability": list(base.availability or []),
        "min_water_temp_c": (
            float(base.min_water_temp_c)
            if base.min_water_temp_c is not None
            else None
        ),
        "excluded_bottoms": list(base.excluded_bottoms or []),
        "quiver": [
            {
                "kind": item.kind,
                "size": float(item.size) if item.size is not None else None,
                "board_type": item.board_type,
                "active": item.active,
            }
            for item in gear
        ],
    }
    return RiderContext(
        sport, "user", profile, personal_band(profile, sport, params), base.profile_version
    )
