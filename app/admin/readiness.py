"""Readiness validation: a spot may go live only when complete.

Completeness is declarative — driven by the ``required_fields`` table (per sport
via ``applies_when``). A field is satisfied by a real value **or** the explicit
``n/a`` sentinel. On top of the field rules, a spot must have a derived
climatology and a fully-credited image.
"""

from __future__ import annotations

from typing import Any

from app.admin.constants import is_na

# Version-1 completeness rules seeded into ``required_fields``.
REQUIRED_FIELDS_V1: list[dict] = [
    {"entity": "spot", "field": "water_type", "applies_when": None, "severity": "required"},
    {"entity": "spot", "field": "bottom_type", "applies_when": None, "severity": "required"},
    {"entity": "spot", "field": "level", "applies_when": None, "severity": "required"},
    {"entity": "spot", "field": "water_character", "applies_when": None, "severity": "required"},
    # Category/facility hints — surfaced in the checklist but never block "live"
    # (a spot with unknown facilities must still be publishable).
    {"entity": "spot", "field": "style", "applies_when": None, "severity": "recommended"},
    {"entity": "spot", "field": "facilities", "applies_when": None, "severity": "recommended"},
    {"entity": "spot", "field": "editorial.description", "applies_when": None, "severity": "required"},
    # Gezeiten (editorial.tide) is intentionally NOT a requirement — it is hidden
    # in the editor and must not affect the "Fertigstellen" rank. The row is
    # removed from the DB by migration 0020.
]


def applies(applies_when: dict | None, sports: list[str]) -> bool:
    """Whether a rule applies given the spot's sports."""
    if not applies_when:
        return True
    sports = set(sports or [])
    if "sport" in applies_when:
        return applies_when["sport"] in sports
    if "sports_any" in applies_when:
        return bool(sports & set(applies_when["sports_any"]))
    if "sports_all" in applies_when:
        return set(applies_when["sports_all"]).issubset(sports)
    return True


def resolve_field(spot: Any, field: str) -> Any:
    """Resolve a column (``water_type``) or editorial path (``editorial.description``)."""
    if "." in field:
        head, sub = field.split(".", 1)
        blob = getattr(spot, head, None) or {}
        return blob.get(sub) if isinstance(blob, dict) else None
    return getattr(spot, field, None)


def is_fulfilled(value: Any) -> bool:
    """A value counts when it is non-empty, or the explicit ``n/a`` sentinel."""
    if is_na(value):
        return True
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def image_ready(image: Any) -> bool:
    """An image needs all of url + source + license + credit."""
    if not isinstance(image, dict):
        return False
    return all(
        isinstance(image.get(k), str) and image[k].strip()
        for k in ("url", "source", "license", "credit")
    )


def climatology_ready(spot: Any, job_status: str | None) -> bool:
    clim = getattr(spot, "climatology", None)
    if isinstance(clim, dict) and clim.get("weeks"):
        return True
    return job_status == "derived"


def build_checklist(
    spot: Any, required_fields: list[dict], *, job_status: str | None = None
) -> dict:
    """Pure readiness check → ``{ready, checklist, gaps}``."""
    sports = list(getattr(spot, "sports", None) or [])
    items: list[dict] = []

    for rf in required_fields:
        if rf.get("entity", "spot") != "spot":
            continue
        if not applies(rf.get("applies_when"), sports):
            continue
        value = resolve_field(spot, rf["field"])
        items.append({
            "field": rf["field"],
            "severity": rf.get("severity", "required"),
            "ok": is_fulfilled(value),
            "na": is_na(value),
        })

    items.append({
        "field": "climatology", "severity": "required",
        "ok": climatology_ready(spot, job_status), "na": False,
    })
    items.append({
        "field": "image", "severity": "required",
        "ok": image_ready(getattr(spot, "image", None)), "na": False,
    })

    gaps = [i["field"] for i in items if i["severity"] == "required" and not i["ok"]]
    return {"ready": len(gaps) == 0, "checklist": items, "gaps": gaps}


# --- DB wrappers -----------------------------------------------------------

def seed_required_fields(db) -> int:
    """Upsert the v1 required-field rules. Idempotent. Returns rows inserted."""
    from sqlalchemy import select

    from app.models import RequiredField

    inserted = 0
    for rf in REQUIRED_FIELDS_V1:
        existing = db.scalar(
            select(RequiredField)
            .where(RequiredField.entity == rf["entity"])
            .where(RequiredField.field == rf["field"])
        )
        if existing is not None:
            existing.applies_when = rf["applies_when"]
            existing.severity = rf["severity"]
            continue
        db.add(RequiredField(**rf))
        inserted += 1
    db.commit()
    return inserted


def _latest_job_status(db, spot_id) -> str | None:
    from sqlalchemy import select

    from app.models import Era5Job

    return db.scalar(
        select(Era5Job.status)
        .where(Era5Job.spot_id == spot_id)
        .order_by(Era5Job.created_at.desc())
    )


def validate_spot_readiness(spot_id, *, db) -> dict:
    """Readiness for a stored spot, using ``required_fields`` + latest ERA5 job."""
    from sqlalchemy import select

    from app.models import RequiredField, Spot

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    rules = [
        {"entity": r.entity, "field": r.field, "applies_when": r.applies_when,
         "severity": r.severity}
        for r in db.scalars(
            select(RequiredField).where(RequiredField.entity == "spot")
        ).all()
    ]
    result = build_checklist(spot, rules, job_status=_latest_job_status(db, spot_id))
    return {"spot_id": str(spot.id), "status": spot.status, **result}
