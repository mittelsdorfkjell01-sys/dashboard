from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_actor, require_role
from app.db.session import get_db
from app.tides import service
from app.tides.schemas import (
    ApplySuggestionRequest,
    ManualAnchorRequest,
    TideOverrideRequest,
    TidePreviewRequest,
    TideProfileUpdate,
    TideRollbackRequest,
)

router = APIRouter(
    prefix="/admin/spots",
    tags=["admin", "tides"],
    dependencies=[Depends(require_role("admin", "curator"))],
)


def _not_found(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/{spot_id}/tide")
def get_tide_profile(
    spot_id: uuid.UUID, db: Session = Depends(get_db), actor: str = Depends(get_actor)
) -> dict:
    try:
        profile = service.get_or_create_profile(spot_id, db=db, actor=actor)
        return service.profile_dict(profile, db=db)
    except LookupError as exc:
        raise _not_found(exc)


@router.patch("/{spot_id}/tide")
def update_tide_profile(
    spot_id: uuid.UUID, body: TideProfileUpdate,
    db: Session = Depends(get_db), actor: str = Depends(get_actor),
) -> dict:
    try:
        profile = service.update_profile(
            spot_id, body.model_dump(exclude_unset=True), db=db, actor=actor
        )
        return service.profile_dict(profile, db=db)
    except LookupError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{spot_id}/tide/anchor/auto", status_code=202)
def auto_anchor(
    spot_id: uuid.UUID, db: Session = Depends(get_db), actor: str = Depends(get_actor)
) -> dict:
    try:
        run = service.request_auto_anchor(spot_id, db=db, actor=actor)
        return {"run_id": str(run.id), "status": run.status}
    except LookupError as exc:
        raise _not_found(exc)


@router.put("/{spot_id}/tide/anchor")
def manual_anchor(
    spot_id: uuid.UUID, body: ManualAnchorRequest,
    db: Session = Depends(get_db), actor: str = Depends(get_actor),
) -> dict:
    try:
        profile = service.set_manual_anchor(
            spot_id, body.lat, body.lon, body.reason, db=db, actor=actor
        )
        return service.profile_dict(profile, db=db)
    except LookupError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{spot_id}/tide/preview")
def preview(spot_id: uuid.UUID, body: TidePreviewRequest, db: Session = Depends(get_db)) -> dict:
    return {"events": service.preview(spot_id, body.model_dump(), db=db)}


@router.post("/{spot_id}/tide/recalculate", status_code=202)
def recalculate(
    spot_id: uuid.UUID, db: Session = Depends(get_db), actor: str = Depends(get_actor)
) -> dict:
    try:
        profile = service.get_or_create_profile(spot_id, db=db, actor=actor)
        if not profile.enabled:
            raise ValueError("Gezeiten müssen vor der Berechnung aktiviert werden")
        run = service.queue_calculation(profile, db=db, actor=actor)
        db.commit()
        return {"run_id": str(run.id), "status": run.status}
    except LookupError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{spot_id}/tide/overrides")
def create_override(
    spot_id: uuid.UUID, body: TideOverrideRequest,
    db: Session = Depends(get_db), actor: str = Depends(get_actor),
) -> dict:
    try:
        item = service.create_override(
            spot_id, body.event_id, body.manual_time, body.scope, body.reason,
            body.source, db=db, actor=actor,
        )
        return {"id": item.id, "difference_minutes": item.difference_minutes, "scope": item.scope}
    except LookupError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{spot_id}/tide/overrides/{override_id}", status_code=204)
def revoke_override(
    spot_id: uuid.UUID, override_id: uuid.UUID,
    db: Session = Depends(get_db), actor: str = Depends(get_actor),
):
    try:
        service.revoke_override(spot_id, override_id, db=db, actor=actor)
    except LookupError as exc:
        raise _not_found(exc)


@router.get("/{spot_id}/tide/suggestion")
def get_suggestion(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return service.suggestion(spot_id, db=db)


@router.post("/{spot_id}/tide/suggestion/apply")
def apply_suggestion(
    spot_id: uuid.UUID, body: ApplySuggestionRequest,
    db: Session = Depends(get_db), actor: str = Depends(get_actor),
) -> dict:
    try:
        profile = service.apply_suggestion(
            spot_id, apply_high=body.apply_high, apply_low=body.apply_low,
            reason=body.reason, db=db, actor=actor,
        )
        return service.profile_dict(profile, db=db)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{spot_id}/tide/history")
def get_history(spot_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    return service.history(spot_id, db=db)


@router.post("/{spot_id}/tide/rollback")
def rollback(
    spot_id: uuid.UUID, body: TideRollbackRequest,
    db: Session = Depends(get_db), actor: str = Depends(get_actor),
) -> dict:
    try:
        profile = service.rollback(
            spot_id, body.version, body.reason, db=db, actor=actor
        )
        return service.profile_dict(profile, db=db)
    except LookupError as exc:
        raise _not_found(exc)


@router.get("/tide/monitoring")
def tide_monitoring(db: Session = Depends(get_db)) -> dict:
    return service.monitoring(db=db)
