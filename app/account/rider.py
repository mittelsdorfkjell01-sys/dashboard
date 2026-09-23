"""Persistence and validation for private rider setup data."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.constants import (
    BOTTOM_TYPES,
    LEVELS,
    SPORTS,
    STYLES,
    WATER_CHARACTERS,
)
from app.models import AppUser, GearItem, RiderProfile, RiderSportProfile

TRAVEL_MODES = ("day_trip", "weekend", "trip", "camper")
GEAR_KINDS = ("kite", "board", "foil")
BOARD_TYPES = ("twintip", "surfboard", "foil", "bigair_twintip")


def _profile(db: Session, user: AppUser, *, lock: bool = False) -> RiderProfile | None:
    stmt = select(RiderProfile).where(RiderProfile.app_user_id == user.id)
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def ensure_profile(db: Session, user: AppUser, *, lock: bool = True) -> RiderProfile:
    profile = _profile(db, user, lock=lock)
    if profile is None:
        profile = RiderProfile(app_user_id=user.id, profile_version=1)
        db.add(profile)
        db.flush()
    return profile


def _bump(profile: RiderProfile) -> None:
    profile.profile_version = int(profile.profile_version or 0) + 1


def profile_payload(profile: RiderProfile | None) -> dict[str, Any]:
    location = None
    if profile is not None and profile.home_location is not None:
        point = to_shape(profile.home_location)
        location = {"lat": float(point.y), "lon": float(point.x)}
    return {
        "weightKg": float(profile.weight_kg) if profile and profile.weight_kg is not None else None,
        "homeLocation": location,
        "maxTravelKm": float(profile.max_travel_km) if profile and profile.max_travel_km is not None else None,
        "travelMode": profile.travel_mode if profile else "day_trip",
        "availability": list(profile.availability or []) if profile else [],
        "minWaterTempC": float(profile.min_water_temp_c) if profile and profile.min_water_temp_c is not None else None,
        "excludedBottoms": list(profile.excluded_bottoms or []) if profile else [],
        "profileVersion": int(profile.profile_version) if profile else 0,
    }


def get_profile(db: Session, user: AppUser) -> dict[str, Any]:
    return profile_payload(_profile(db, user))


def put_profile(db: Session, user: AppUser, data: Mapping[str, Any]) -> dict[str, Any]:
    profile = _profile(db, user, lock=True)
    created = profile is None
    if profile is None:
        profile = RiderProfile(app_user_id=user.id, profile_version=1)
        db.add(profile)

    weight = data.get("weight_kg")
    if weight is not None and not 30 <= float(weight) <= 160:
        raise ValueError("weight_kg must be between 30 and 160")
    travel_mode = str(data.get("travel_mode") or "day_trip")
    if travel_mode not in TRAVEL_MODES:
        raise ValueError("invalid travel_mode")
    availability = list(dict.fromkeys(data.get("availability") or []))
    if any(isinstance(day, bool) or not isinstance(day, int) or day not in range(7) for day in availability):
        raise ValueError("availability must contain weekdays 0 through 6")
    excluded = list(dict.fromkeys(data.get("excluded_bottoms") or []))
    if set(excluded) - set(BOTTOM_TYPES):
        raise ValueError("invalid excluded_bottoms")
    location = data.get("home_location")
    if location is not None:
        lat, lon = float(location["lat"]), float(location["lon"])
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("invalid home_location")
        profile.home_location = WKTElement(f"POINT({lon} {lat})", srid=4326)
    else:
        profile.home_location = None

    profile.weight_kg = weight
    profile.max_travel_km = data.get("max_travel_km")
    profile.travel_mode = travel_mode
    profile.availability = availability
    profile.min_water_temp_c = data.get("min_water_temp_c")
    profile.excluded_bottoms = excluded
    if not created:
        _bump(profile)
    db.flush()
    return profile_payload(profile)


def sport_profile_payload(
    row: RiderSportProfile | None, sport: str, profile_version: int
) -> dict[str, Any]:
    return {
        "sport": sport,
        "level": row.level if row else None,
        "styleWeights": dict(row.style_weights or {}) if row else {},
        "preferredWaterCharacter": list(row.preferred_water_character or []) if row else [],
        "profileVersion": profile_version,
    }


def get_sport_profile(db: Session, user: AppUser, sport: str) -> dict[str, Any]:
    if sport not in SPORTS:
        raise ValueError("invalid sport")
    profile = _profile(db, user)
    if profile is None:
        return sport_profile_payload(None, sport, 0)
    row = db.scalar(select(RiderSportProfile).where(
        RiderSportProfile.rider_profile_id == profile.id,
        RiderSportProfile.sport == sport,
    ))
    return sport_profile_payload(row, sport, profile.profile_version)


def put_sport_profile(
    db: Session, user: AppUser, sport: str, data: Mapping[str, Any]
) -> dict[str, Any]:
    if sport not in SPORTS:
        raise ValueError("invalid sport")
    level = str(data.get("level") or "")
    if level not in LEVELS:
        raise ValueError("invalid level")
    styles = dict(data.get("style_weights") or {})
    if set(styles) - set(STYLES) or any(
        isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3
        for value in styles.values()
    ):
        raise ValueError("style_weights must use known styles and values 0 through 3")
    water = list(dict.fromkeys(data.get("preferred_water_character") or []))
    if set(water) - set(WATER_CHARACTERS):
        raise ValueError("invalid preferred_water_character")

    profile = ensure_profile(db, user, lock=True)
    row = db.scalar(select(RiderSportProfile).where(
        RiderSportProfile.rider_profile_id == profile.id,
        RiderSportProfile.sport == sport,
    ))
    if row is None:
        row = RiderSportProfile(rider_profile_id=profile.id, sport=sport, level=level)
        db.add(row)
    row.level = level
    row.style_weights = styles
    row.preferred_water_character = water
    _bump(profile)
    db.flush()
    return sport_profile_payload(row, sport, profile.profile_version)


def gear_payload(item: GearItem, profile_version: int) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "sport": item.sport,
        "kind": item.kind,
        "size": float(item.size) if item.size is not None else None,
        "boardType": item.board_type,
        "active": item.active,
        "sortOrder": item.sort_order,
        "profileVersion": profile_version,
    }


def list_gear(db: Session, user: AppUser, sport: str | None = None) -> list[dict[str, Any]]:
    if sport is not None and sport not in SPORTS:
        raise ValueError("invalid sport")
    profile = _profile(db, user)
    if profile is None:
        return []
    stmt = select(GearItem).where(GearItem.rider_profile_id == profile.id)
    if sport is not None:
        stmt = stmt.where(GearItem.sport == sport)
    rows = db.scalars(stmt.order_by(GearItem.sort_order, GearItem.created_at)).all()
    return [gear_payload(row, profile.profile_version) for row in rows]


def _validated_gear(data: Mapping[str, Any]) -> dict[str, Any]:
    sport, kind = str(data.get("sport") or ""), str(data.get("kind") or "")
    if sport not in SPORTS:
        raise ValueError("invalid sport")
    if kind not in GEAR_KINDS:
        raise ValueError("invalid gear kind")
    size = data.get("size")
    if size is not None and not 0 < float(size) <= 500:
        raise ValueError("gear size must be between 0 and 500")
    if kind == "kite" and size is None:
        raise ValueError("kite size is required")
    board_type = data.get("board_type")
    if board_type is not None and board_type not in BOARD_TYPES:
        raise ValueError("invalid board_type")
    sort_order = int(data.get("sort_order") or 0)
    if sort_order < 0:
        raise ValueError("sort_order must be non-negative")
    return {
        "sport": sport, "kind": kind, "size": size,
        "board_type": board_type, "active": bool(data.get("active", True)),
        "sort_order": sort_order,
    }


def create_gear(db: Session, user: AppUser, data: Mapping[str, Any]) -> dict[str, Any]:
    values = _validated_gear(data)
    profile = ensure_profile(db, user, lock=True)
    item = GearItem(rider_profile_id=profile.id, **values)
    db.add(item)
    _bump(profile)
    db.flush()
    return gear_payload(item, profile.profile_version)


def update_gear(
    db: Session, user: AppUser, item_id: uuid.UUID, data: Mapping[str, Any]
) -> dict[str, Any]:
    values = _validated_gear(data)
    profile = ensure_profile(db, user, lock=True)
    item = db.scalar(select(GearItem).where(
        GearItem.id == item_id, GearItem.rider_profile_id == profile.id
    ))
    if item is None:
        raise LookupError("gear item not found")
    for key, value in values.items():
        setattr(item, key, value)
    _bump(profile)
    db.flush()
    return gear_payload(item, profile.profile_version)


def delete_gear(db: Session, user: AppUser, item_id: uuid.UUID) -> None:
    profile = _profile(db, user, lock=True)
    if profile is None:
        raise LookupError("gear item not found")
    item = db.scalar(select(GearItem).where(
        GearItem.id == item_id, GearItem.rider_profile_id == profile.id
    ))
    if item is None:
        raise LookupError("gear item not found")
    db.delete(item)
    _bump(profile)
    db.flush()
