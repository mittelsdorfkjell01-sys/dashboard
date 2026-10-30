"""Manual trip planner service.

The planner deliberately stores user choices, not forecast recommendations.
Forecast-driven automation remains gated by the verification campaign.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AppUser, Spot, Trip, TripStop


def _normalise_days(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {**row, "date": row["date"].isoformat() if isinstance(row.get("date"), date) else row.get("date")}
        for row in rows
    ]


def _trip_days(trip: Trip) -> list[dict[str, Any]]:
    if trip.days:
        return list(trip.days)
    return [
        {"date": (trip.start_date + timedelta(days=offset)).isoformat(), "notes": None, "accommodation": None, "travel": None}
        for offset in range((trip.end_date - trip.start_date).days + 1)
    ]


def _owned(db: Session, user: AppUser, trip_id: uuid.UUID) -> Trip:
    trip = db.scalar(
        select(Trip)
        .options(selectinload(Trip.stops).selectinload(TripStop.spot))
        .where(Trip.id == trip_id, Trip.app_user_id == user.id)
    )
    if trip is None:
        raise LookupError("Reise nicht gefunden.")
    return trip


def _stop_dict(stop: TripStop) -> dict[str, Any]:
    spot = stop.spot
    return {
        "id": str(stop.id),
        "spotId": str(stop.spot_id) if stop.spot_id else None,
        "spotName": stop.spot_name,
        "position": stop.position,
        "plannedDate": stop.planned_date.isoformat() if stop.planned_date else None,
        "notes": stop.notes,
        "role": stop.role,
        "contentChanged": bool(
            spot is not None and stop.spot_updated_at is not None
            and spot.updated_at > stop.spot_updated_at
        ),
        "spotAvailable": bool(spot is not None and spot.status == "published"),
    }


def as_dict(trip: Trip, *, shared: bool = False) -> dict[str, Any]:
    include_notes = not shared or trip.share_notes
    days = _trip_days(trip)
    result = {
        "id": str(trip.id),
        "title": trip.title,
        "startDate": trip.start_date.isoformat(),
        "endDate": trip.end_date.isoformat(),
        "notes": trip.notes if include_notes else None,
        "checklist": list(trip.checklist or []) if include_notes else [],
        "days": days if include_notes else [
            {"date": item.get("date"), "notes": None, "accommodation": None, "travel": None}
            for item in days if isinstance(item, dict) and item.get("date")
        ],
        "status": trip.status,
        "stops": [_stop_dict(stop) for stop in sorted(trip.stops, key=lambda item: item.position)],
        "createdAt": trip.created_at.isoformat(),
        "updatedAt": trip.updated_at.isoformat(),
    }
    if shared and not include_notes:
        for stop in result["stops"]:
            stop["notes"] = None
    if not shared:
        result["shareUrl"] = f"/reise/{trip.share_token}" if trip.share_token else None
        result["shareNotes"] = bool(trip.share_notes)
    return result


def list_trips(db: Session, user: AppUser) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Trip)
        .options(selectinload(Trip.stops).selectinload(TripStop.spot))
        .where(Trip.app_user_id == user.id)
        .order_by(Trip.start_date.desc(), Trip.created_at.desc())
    ).all()
    return [as_dict(row) for row in rows]


def _replace_stops(db: Session, trip: Trip, rows: list[dict[str, Any]]) -> None:
    spot_ids = {row["spot_id"] for row in rows}
    spots = db.scalars(
        select(Spot).where(Spot.id.in_(spot_ids), Spot.status == "published")
    ).all() if spot_ids else []
    by_id = {spot.id: spot for spot in spots}
    missing = spot_ids - set(by_id)
    if missing:
        raise ValueError("Mindestens ein Spot ist nicht öffentlich verfügbar.")

    main_dates = set()
    spot_days = set()
    for row in rows:
        planned_date = row.get("planned_date")
        if planned_date is None:
            raise ValueError("Jeder Spot benötigt einen geplanten Reisetag.")
        if row.get("role", "main") == "main":
            if planned_date in main_dates:
                raise ValueError("Pro Reisetag ist nur ein Hauptspot möglich.")
            main_dates.add(planned_date)
        key = (planned_date, row["spot_id"])
        if key in spot_days:
            raise ValueError("Ein Spot darf pro Reisetag nur einmal vorkommen.")
        spot_days.add(key)

    trip.stops.clear()
    db.flush()
    for position, row in enumerate(rows):
        spot = by_id[row["spot_id"]]
        planned_date = row.get("planned_date")
        if planned_date is not None and not trip.start_date <= planned_date <= trip.end_date:
            raise ValueError("Ein geplanter Spot-Tag liegt außerhalb des Reisezeitraums.")
        trip.stops.append(TripStop(
            spot_id=spot.id,
            spot_name=spot.name,
            position=position,
            planned_date=planned_date,
            notes=row.get("notes"),
            role=row.get("role") or "alternative",
            spot_updated_at=spot.updated_at,
        ))


def create_trip(db: Session, user: AppUser, data: dict[str, Any]) -> dict[str, Any]:
    trip = Trip(
        app_user_id=user.id,
        title=data["title"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        notes=data.get("notes"),
        checklist=data.get("checklist") or [],
        days=_normalise_days(data.get("days") or []),
        status=data.get("status") or "draft",
    )
    db.add(trip)
    db.flush()
    _replace_stops(db, trip, data.get("stops") or [])
    db.commit()
    return as_dict(_owned(db, user, trip.id))


def update_trip(db: Session, user: AppUser, trip_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    trip = _owned(db, user, trip_id)
    if "days" in data:
        data["days"] = _normalise_days(data["days"])
    for field in ("title", "start_date", "end_date", "notes", "checklist", "days", "status"):
        if field in data:
            setattr(trip, field, data[field])
    if trip.end_date < trip.start_date:
        raise ValueError("Das Enddatum darf nicht vor dem Startdatum liegen.")
    if (trip.end_date - trip.start_date).days > 30:
        raise ValueError("Eine Reise darf höchstens 31 Tage umfassen.")
    if any(
        not trip.start_date <= date.fromisoformat(item["date"]) <= trip.end_date
        for item in (trip.days or []) if isinstance(item, dict) and item.get("date")
    ):
        raise ValueError("Ein Reisetag liegt außerhalb des neuen Reisezeitraums.")
    if any(
        stop.planned_date is not None
        and not trip.start_date <= stop.planned_date <= trip.end_date
        for stop in trip.stops
    ) and "stops" not in data:
        raise ValueError("Ein bestehender Spot-Tag liegt außerhalb des neuen Reisezeitraums.")
    if "stops" in data:
        _replace_stops(db, trip, data["stops"])
    db.commit()
    return as_dict(_owned(db, user, trip.id))


def delete_trip(db: Session, user: AppUser, trip_id: uuid.UUID) -> None:
    trip = _owned(db, user, trip_id)
    db.delete(trip)
    db.commit()


def copy_trip(db: Session, user: AppUser, trip_id: uuid.UUID) -> dict[str, Any]:
    source = _owned(db, user, trip_id)
    copied = Trip(
        app_user_id=user.id, title=f"{source.title[:150]} – Kopie",
        start_date=source.start_date, end_date=source.end_date,
        notes=source.notes, checklist=[dict(item) for item in (source.checklist or [])],
        days=[dict(item) for item in (source.days or [])], status="draft",
    )
    db.add(copied)
    db.flush()
    for stop in sorted(source.stops, key=lambda item: item.position):
        copied.stops.append(TripStop(
            spot_id=stop.spot_id, spot_name=stop.spot_name,
            position=stop.position, planned_date=stop.planned_date,
            notes=stop.notes, role=stop.role,
            spot_updated_at=stop.spot.updated_at if stop.spot else stop.spot_updated_at,
        ))
    db.commit()
    return as_dict(_owned(db, user, copied.id))


def set_sharing(
    db: Session, user: AppUser, trip_id: uuid.UUID, *, enabled: bool,
    share_notes: bool = False,
) -> dict[str, Any]:
    trip = _owned(db, user, trip_id)
    trip.share_token = (trip.share_token or uuid.uuid4()) if enabled else None
    trip.share_notes = bool(enabled and share_notes)
    db.commit()
    return as_dict(_owned(db, user, trip.id))


def shared_trip(db: Session, token: uuid.UUID) -> dict[str, Any]:
    trip = db.scalar(
        select(Trip)
        .options(selectinload(Trip.stops).selectinload(TripStop.spot))
        .where(Trip.share_token == token)
    )
    if trip is None:
        raise LookupError("Geteilte Reise nicht gefunden.")
    return as_dict(trip, shared=True)
