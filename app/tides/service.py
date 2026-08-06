from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Spot,
    TideCalculationRun,
    TideEvent,
    TideEventOverride,
    TideProfile,
    TideProfileRevision,
)
from app.schemas.common import GeoPoint
from app.tides import ALGORITHM_VERSION, MODEL_NAME, MODEL_VERSION
from app.tides.calculation import calibration_suggestion, corrected_time, phase_at


PROFILE_FIELDS = (
    "enabled", "public_enabled", "timezone", "model_name", "model_version",
    "global_offset_minutes", "high_offset_minutes", "low_offset_minutes",
    "constituent_adjustments", "manual_uncertainty_minutes",
    "estimated_uncertainty_minutes", "uncertainty_source", "quality_status",
    "note", "correction_reason", "correction_source", "anchor_distance_m",
    "anchor_kind", "anchor_status", "anchor_warnings",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _point(value) -> dict | None:
    point = GeoPoint.from_geo(value)
    return point.model_dump() if point else None


def _snapshot(profile: TideProfile) -> dict:
    data = {field: getattr(profile, field) for field in PROFILE_FIELDS}
    data["automatic_anchor"] = _point(profile.automatic_anchor)
    data["manual_anchor"] = _point(profile.manual_anchor)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def _add_revision(db: Session, profile: TideProfile, reason: str, actor: str | None) -> None:
    db.add(TideProfileRevision(
        profile_id=profile.id, spot_id=profile.spot_id, version=profile.version,
        snapshot=_snapshot(profile), reason=reason, actor=actor,
    ))


def get_or_create_profile(spot_id: uuid.UUID, *, db: Session, actor: str | None = None) -> TideProfile:
    if db.get(Spot, spot_id) is None:
        raise LookupError("Spot not found")
    profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == spot_id))
    if profile is not None:
        return profile
    profile = TideProfile(spot_id=spot_id, edited_by=actor)
    db.add(profile)
    db.flush()
    _add_revision(db, profile, "Tideprofil angelegt", actor)
    db.commit()
    db.refresh(profile)
    return profile


def queue_calculation(profile: TideProfile, *, db: Session, actor: str | None, action: str = "calculate") -> TideCalculationRun:
    profile.calculation_status = "queued"
    profile.calculation_error = None
    run = TideCalculationRun(
        spot_id=profile.spot_id, requested_by=actor, model_name=profile.model_name,
        model_version=profile.model_version, algorithm_version=ALGORITHM_VERSION,
        profile_version=profile.version, details={"action": action},
    )
    db.add(run)
    return run


def _validate_timezone(value: str | None) -> None:
    if not value:
        return
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unbekannte IANA-Zeitzone") from exc


def update_profile(spot_id: uuid.UUID, changes: dict, *, db: Session, actor: str) -> TideProfile:
    profile = get_or_create_profile(spot_id, db=db, actor=actor)
    settings = get_settings()
    offsets = {
        key: changes.get(key, getattr(profile, key))
        for key in ("global_offset_minutes", "high_offset_minutes", "low_offset_minutes")
    }
    if any(abs(int(value)) > settings.tide_offset_hard_limit_minutes for value in offsets.values()):
        raise ValueError(f"Zeitkorrekturen dürfen maximal ±{settings.tide_offset_hard_limit_minutes} Minuten betragen")
    if any(
        abs(int(offsets["global_offset_minutes"]) + int(offsets[key]))
        > settings.tide_offset_hard_limit_minutes
        for key in ("high_offset_minutes", "low_offset_minutes")
    ):
        raise ValueError("Die Summe aus allgemeiner und ereignisspezifischer Korrektur überschreitet die zulässige Grenze")
    reason = (changes.get("correction_reason") or profile.correction_reason or "").strip()
    if any(abs(int(value)) >= settings.tide_reason_required_minutes for value in offsets.values()) and not reason:
        raise ValueError(f"Ab {settings.tide_reason_required_minutes} Minuten ist eine Begründung erforderlich")
    _validate_timezone(changes.get("timezone", profile.timezone))
    proposed = preview(spot_id, offsets, db=db)
    if any(a["time"] >= b["time"] for a, b in zip(proposed, proposed[1:])):
        raise ValueError("Die Korrekturen würden die Reihenfolge der Tideereignisse widersprüchlich machen")
    review_anchor = bool(changes.pop("review_anchor", False))
    for key, value in changes.items():
        if key in PROFILE_FIELDS and key not in {"model_name", "model_version", "anchor_status"}:
            setattr(profile, key, value)
    if review_anchor:
        if profile.manual_anchor is None and profile.automatic_anchor is None:
            raise ValueError("Ohne Modellanker ist keine Prüfung möglich")
        if profile.anchor_status != "auto_selected" or profile.calculation_status != "ready":
            raise ValueError("Der Modellanker muss zuerst vom Tide-Worker erfolgreich validiert werden")
        profile.anchor_status = "reviewed"
        profile.anchor_reviewed_at = _utcnow()
    calibrated = any(offsets.values()) or db.scalar(
        select(func.count()).select_from(TideEventOverride).where(
            TideEventOverride.spot_id == spot_id, TideEventOverride.active.is_(True)
        )
    )
    if calibrated:
        profile.quality_status = "manual_calibrated"
    elif profile.anchor_status == "reviewed":
        profile.quality_status = "reviewed_anchor"
    elif profile.automatic_anchor is not None:
        profile.quality_status = "model_only"
    else:
        profile.quality_status = "unavailable"
    profile.edited_by = actor
    profile.version += 1
    profile.calculation_status = "queued" if profile.enabled else "not_configured"
    _add_revision(db, profile, reason or "Tideprofil aktualisiert", actor)
    if profile.enabled:
        queue_calculation(profile, db=db, actor=actor)
    db.commit()
    db.refresh(profile)
    return profile


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def set_manual_anchor(spot_id: uuid.UUID, lat: float, lon: float, reason: str, *, db: Session, actor: str) -> TideProfile:
    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError("Spot not found")
    profile = get_or_create_profile(spot_id, db=db, actor=actor)
    spot_point = GeoPoint.from_geo(spot.location)
    distance = _haversine_m(spot_point.lat, spot_point.lon, lat, lon)
    if distance > get_settings().tide_max_anchor_distance_km * 1000:
        raise ValueError("Der manuelle Modellanker liegt außerhalb der zulässigen Suchdistanz")
    profile.manual_anchor = WKTElement(f"POINT({lon} {lat})", srid=4326)
    profile.anchor_distance_m = distance
    profile.anchor_kind = "manual"
    profile.anchor_status = "needs_review"
    profile.anchor_reviewed_at = None
    profile.anchor_warnings = ["Manueller Anker muss vom FES-Worker validiert und anschließend geprüft werden."]
    profile.quality_status = "unavailable"
    profile.edited_by = actor
    profile.version += 1
    _add_revision(db, profile, reason, actor)
    if profile.enabled:
        queue_calculation(profile, db=db, actor=actor, action="validate_anchor_and_calculate")
    db.commit()
    db.refresh(profile)
    return profile


def request_auto_anchor(spot_id: uuid.UUID, *, db: Session, actor: str) -> TideCalculationRun:
    profile = get_or_create_profile(spot_id, db=db, actor=actor)
    profile.automatic_anchor = None
    profile.manual_anchor = None
    profile.anchor_distance_m = None
    profile.anchor_kind = None
    profile.anchor_status = "needs_review"
    profile.anchor_warnings = ["Automatische Modellanker-Bestimmung ist eingeplant."]
    profile.anchor_reviewed_at = None
    profile.public_enabled = False
    profile.quality_status = "unavailable"
    profile.version += 1
    profile.edited_by = actor
    _add_revision(db, profile, "Automatische Modellanker-Bestimmung angefordert", actor)
    run = queue_calculation(profile, db=db, actor=actor, action="anchor_and_calculate")
    db.commit()
    db.refresh(run)
    return run


def invalidate_for_coordinates(spot_id: uuid.UUID, *, db: Session, actor: str | None) -> None:
    """Fail closed when a spot moves; caller owns the transaction."""
    profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == spot_id))
    if profile is None:
        return
    profile.automatic_anchor = None
    profile.manual_anchor = None
    profile.anchor_distance_m = None
    profile.anchor_kind = None
    profile.anchor_status = "needs_review"
    profile.anchor_warnings = ["Spotkoordinaten geändert; Modellanker muss neu bestimmt und geprüft werden."]
    profile.public_enabled = False
    profile.quality_status = "unavailable"
    profile.version += 1
    profile.edited_by = actor
    _add_revision(db, profile, "Spotkoordinaten geändert", actor)
    if profile.enabled:
        queue_calculation(profile, db=db, actor=actor, action="anchor_and_calculate")


def profile_dict(profile: TideProfile, *, db: Session) -> dict:
    events = _latest_events(profile.spot_id, db=db, include_past=True, limit=12)
    overrides = list(db.scalars(select(TideEventOverride).where(
        TideEventOverride.spot_id == profile.spot_id,
    ).order_by(TideEventOverride.created_at.desc()).limit(50)))
    latest_run = db.scalar(select(TideCalculationRun).where(
        TideCalculationRun.spot_id == profile.spot_id,
    ).order_by(TideCalculationRun.created_at.desc()).limit(1))
    return {
        "id": str(profile.id), "spot_id": str(profile.spot_id),
        **{field: getattr(profile, field) for field in PROFILE_FIELDS},
        "automatic_anchor": _point(profile.automatic_anchor),
        "manual_anchor": _point(profile.manual_anchor),
        "effective_anchor": _point(profile.manual_anchor if profile.manual_anchor is not None else profile.automatic_anchor),
        "version": profile.version, "last_calculated_at": profile.last_calculated_at,
        "calculation_status": profile.calculation_status,
        "calculation_error": profile.calculation_error,
        "updated_at": profile.updated_at,
        "events": [_admin_event(event, overrides) for event in events],
        "overrides": [_override_dict(item) for item in overrides],
        "latest_run": _run_dict(latest_run) if latest_run else None,
        "limits": {
            "soft_offset_minutes": get_settings().tide_offset_soft_limit_minutes,
            "hard_offset_minutes": get_settings().tide_offset_hard_limit_minutes,
            "reason_required_minutes": get_settings().tide_reason_required_minutes,
        },
    }


def _run_dict(run: TideCalculationRun) -> dict:
    return {key: getattr(run, key) for key in (
        "id", "status", "model_name", "model_version", "algorithm_version",
        "profile_version", "processed_spots", "failed_spots", "details", "error",
        "started_at", "completed_at", "created_at",
    )}


def _override_dict(item: TideEventOverride) -> dict:
    return {key: getattr(item, key) for key in (
        "id", "event_type", "raw_time", "original_model_time", "manual_time",
        "difference_minutes", "scope", "reason", "source", "actor", "active",
        "created_at", "updated_at",
    )}


def _admin_event(event: TideEvent, overrides: list[TideEventOverride]) -> dict:
    override = next((item for item in overrides if item.active and item.scope == "single" and item.event_type == event.event_type and item.raw_time == event.raw_time), None)
    return {
        "id": event.id, "event_type": event.event_type, "raw_time": event.raw_time,
        "time": override.manual_time if override else event.corrected_time,
        "uncertainty_minutes": event.uncertainty_minutes,
        "profile_version": event.profile_version, "overridden": override is not None,
    }


def _latest_events(spot_id: uuid.UUID, *, db: Session, include_past: bool, limit: int) -> list[TideEvent]:
    latest_version = db.scalar(select(func.max(TideEvent.profile_version)).where(
        TideEvent.spot_id == spot_id, TideEvent.status == "valid"
    ))
    if latest_version is None:
        return []
    stmt = select(TideEvent).where(
        TideEvent.spot_id == spot_id, TideEvent.profile_version == latest_version,
        TideEvent.status == "valid",
    )
    if not include_past:
        stmt = stmt.where(TideEvent.corrected_time >= _utcnow() - timedelta(hours=14))
    return list(db.scalars(stmt.order_by(TideEvent.corrected_time).limit(limit)))


def preview(spot_id: uuid.UUID, offsets: dict, *, db: Session) -> list[dict]:
    events = _latest_events(spot_id, db=db, include_past=False, limit=12)
    overrides = list(db.scalars(select(TideEventOverride).where(
        TideEventOverride.spot_id == spot_id, TideEventOverride.active.is_(True),
        TideEventOverride.scope == "single",
    )))
    result = []
    for event in events:
        override = next((item for item in overrides if item.event_type == event.event_type and item.raw_time == event.raw_time), None)
        time = override.manual_time if override else corrected_time(
            event.raw_time, event.event_type, **offsets
        )
        result.append({
            "id": event.id, "event_type": event.event_type, "raw_time": event.raw_time,
            "time": time, "uncertainty_minutes": event.uncertainty_minutes,
            "profile_version": event.profile_version, "overridden": override is not None,
        })
    return result


def create_override(spot_id: uuid.UUID, event_id: uuid.UUID, manual_time: datetime, scope: str, reason: str, source: str | None, *, db: Session, actor: str) -> TideEventOverride:
    event = db.get(TideEvent, event_id)
    if event is None or event.spot_id != spot_id:
        raise LookupError("Tide event not found")
    if manual_time.tzinfo is None:
        raise ValueError("Der korrigierte Zeitpunkt muss eine Zeitzone enthalten")
    manual_time = manual_time.astimezone(timezone.utc)
    difference = int(round((manual_time - event.raw_time).total_seconds() / 60))
    settings = get_settings()
    if abs(difference) > settings.tide_offset_hard_limit_minutes:
        raise ValueError(f"Die Abweichung darf maximal ±{settings.tide_offset_hard_limit_minutes} Minuten betragen")
    profile = get_or_create_profile(spot_id, db=db, actor=actor)
    item = TideEventOverride(
        spot_id=spot_id, event_type=event.event_type, raw_time=event.raw_time,
        original_model_time=event.raw_time, manual_time=manual_time,
        difference_minutes=difference, scope=scope, reason=reason,
        source=source, actor=actor,
    )
    if scope == "single":
        generation = _latest_events(spot_id, db=db, include_past=True, limit=200)
        ordered = sorted(generation, key=lambda value: value.raw_time)
        position = next((index for index, value in enumerate(ordered) if value.id == event.id), None)
        if position is not None:
            existing = list(db.scalars(select(TideEventOverride).where(
                TideEventOverride.spot_id == spot_id,
                TideEventOverride.active.is_(True), TideEventOverride.scope == "single",
            )))
            def effective(value: TideEvent) -> datetime:
                if value.id == event.id:
                    return manual_time
                override = next((row for row in existing if row.event_type == value.event_type and row.raw_time == value.raw_time), None)
                return override.manual_time if override else value.corrected_time
            if position > 0 and effective(ordered[position - 1]) >= manual_time:
                raise ValueError("Der Zeitpunkt muss nach dem vorherigen Tideereignis liegen")
            if position + 1 < len(ordered) and manual_time >= effective(ordered[position + 1]):
                raise ValueError("Der Zeitpunkt muss vor dem nächsten Tideereignis liegen")
    db.add(item)
    if scope in {"high_profile", "low_profile"}:
        specific = difference - profile.global_offset_minutes
        setattr(profile, f"{event.event_type}_offset_minutes", specific)
        profile.quality_status = "manual_calibrated"
        profile.version += 1
        profile.edited_by = actor
        _add_revision(db, profile, reason, actor)
        queue_calculation(profile, db=db, actor=actor)
    elif scope == "single":
        queue_calculation(profile, db=db, actor=actor)
    db.commit()
    db.refresh(item)
    return item


def revoke_override(spot_id: uuid.UUID, override_id: uuid.UUID, *, db: Session, actor: str) -> None:
    item = db.get(TideEventOverride, override_id)
    if item is None or item.spot_id != spot_id:
        raise LookupError("Tide override not found")
    item.active = False
    profile = get_or_create_profile(spot_id, db=db, actor=actor)
    if profile.enabled:
        queue_calculation(profile, db=db, actor=actor)
    db.commit()


def suggestion(spot_id: uuid.UUID, *, db: Session) -> dict:
    rows = list(db.scalars(select(TideEventOverride).where(
        TideEventOverride.spot_id == spot_id,
        TideEventOverride.active.is_(True),
        TideEventOverride.scope == "calibration_input",
    ).order_by(TideEventOverride.raw_time)))
    result = calibration_suggestion((row.event_type, row.difference_minutes) for row in rows)
    result["from"] = rows[0].raw_time if rows else None
    result["until"] = rows[-1].raw_time if rows else None
    return result


def apply_suggestion(spot_id: uuid.UUID, *, apply_high: bool, apply_low: bool, reason: str, db: Session, actor: str) -> TideProfile:
    proposed = suggestion(spot_id, db=db)
    profile = get_or_create_profile(spot_id, db=db, actor=actor)
    uncertainties = []
    for kind, apply in (("high", apply_high), ("low", apply_low)):
        entry = proposed.get(kind)
        if apply and entry:
            setattr(profile, f"{kind}_offset_minutes", int(entry["offset_minutes"]) - profile.global_offset_minutes)
            uncertainties.append(int(entry["uncertainty_minutes"]))
    if not uncertainties:
        raise ValueError("Für die Auswahl liegen keine Kalibrierungsangaben vor")
    profile.estimated_uncertainty_minutes = max(uncertainties)
    profile.uncertainty_source = "robuste Streuung manueller Ereignisse"
    profile.quality_status = "manual_calibrated"
    profile.version += 1
    profile.edited_by = actor
    _add_revision(db, profile, reason, actor)
    queue_calculation(profile, db=db, actor=actor)
    db.commit()
    db.refresh(profile)
    return profile


def history(spot_id: uuid.UUID, *, db: Session) -> list[dict]:
    rows = list(db.scalars(select(TideProfileRevision).where(
        TideProfileRevision.spot_id == spot_id,
    ).order_by(TideProfileRevision.version.desc())))
    return [{"version": row.version, "reason": row.reason, "actor": row.actor, "created_at": row.created_at, "snapshot": row.snapshot} for row in rows]


def rollback(spot_id: uuid.UUID, version: int, reason: str, *, db: Session, actor: str) -> TideProfile:
    profile = get_or_create_profile(spot_id, db=db, actor=actor)
    revision = db.scalar(select(TideProfileRevision).where(
        TideProfileRevision.profile_id == profile.id,
        TideProfileRevision.version == version,
    ))
    if revision is None:
        raise LookupError("Tide profile version not found")
    snapshot = revision.snapshot
    for field in PROFILE_FIELDS:
        if field in snapshot:
            setattr(profile, field, snapshot[field])
    for field in ("automatic_anchor", "manual_anchor"):
        point = snapshot.get(field)
        setattr(profile, field, WKTElement(f"POINT({point['lon']} {point['lat']})", srid=4326) if point else None)
    profile.version += 1
    profile.edited_by = actor
    _add_revision(db, profile, reason, actor)
    if profile.enabled:
        queue_calculation(profile, db=db, actor=actor)
    db.commit()
    db.refresh(profile)
    return profile


def public_tides(spot_id: uuid.UUID, *, db: Session) -> dict:
    profile = db.scalar(select(TideProfile).where(TideProfile.spot_id == spot_id))
    unavailable = "Für diesen Spot sind derzeit keine verlässlichen Gezeitenangaben verfügbar."
    if (
        profile is None
        or not profile.enabled
        or not profile.public_enabled
        or not profile.timezone
        or profile.anchor_status != "reviewed"
    ):
        return {"available": False, "message": unavailable}
    events = _latest_events(spot_id, db=db, include_past=False, limit=16)
    if not events:
        return {"available": False, "message": unavailable, "timezone": profile.timezone}
    overrides = list(db.scalars(select(TideEventOverride).where(
        TideEventOverride.spot_id == spot_id,
        TideEventOverride.active.is_(True), TideEventOverride.scope == "single",
    )))
    public_events = [_admin_event(event, overrides) for event in events]
    now = _utcnow()
    phase, position = phase_at([(item["event_type"], item["time"]) for item in public_events], now)
    future = [item for item in public_events if item["time"] >= now][:8]
    if not future:
        return {"available": False, "message": unavailable, "timezone": profile.timezone}
    valid_until = max(item["time"] for item in public_events)
    stale = valid_until < now + timedelta(days=get_settings().tide_refresh_before_days)
    return {
        "available": True, "timezone": profile.timezone, "phase": phase,
        "cycle_position": position, "quality": profile.quality_status,
        "approximate": True, "last_calculated_at": profile.last_calculated_at,
        "valid_until": valid_until, "events": future,
        "message": "Die Prognose wird bald aktualisiert." if stale else None,
    }


def monitoring(*, db: Session) -> dict:
    now = _utcnow()
    active = db.scalar(select(func.count()).select_from(TideProfile).where(TideProfile.enabled.is_(True))) or 0
    no_anchor = db.scalar(select(func.count()).select_from(TideProfile).where(
        TideProfile.enabled.is_(True), TideProfile.automatic_anchor.is_(None), TideProfile.manual_anchor.is_(None)
    )) or 0
    stale = db.scalar(select(func.count()).select_from(TideProfile).where(
        TideProfile.enabled.is_(True),
        (TideProfile.last_calculated_at.is_(None)) | (TideProfile.last_calculated_at < now - timedelta(days=get_settings().tide_horizon_days - get_settings().tide_refresh_before_days)),
    )) or 0
    last_run = db.scalar(select(TideCalculationRun).where(
        TideCalculationRun.status == "succeeded"
    ).order_by(TideCalculationRun.completed_at.desc()).limit(1))
    return {"active_spots": active, "spots_without_anchor": no_anchor, "stale_spots": stale, "last_successful_job": last_run.completed_at if last_run else None, "model": MODEL_NAME, "model_version": MODEL_VERSION}
