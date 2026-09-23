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
    """An image needs all of url + source + license + credit — and must be a
    real photo.

    Seeded fixtures carry a deliberately unreachable placeholder so the UI shows
    its designed no-image state. Counting those as done would make both the
    "Fertigstellen" traffic light and the "Spots ohne Hero" work list report
    finished work that nobody has done.
    """
    from app.media.image_object import is_placeholder

    if not isinstance(image, dict):
        return False
    if not all(
        isinstance(image.get(k), str) and image[k].strip()
        for k in ("url", "source", "license", "credit")
    ):
        return False
    return not is_placeholder(image)


def climatology_ready(spot: Any, job_status: str | None) -> bool:
    del job_status
    clim = getattr(spot, "climatology", None)
    # The persisted snapshot is the source of truth. A historical "derived" job
    # without stored weeks can occur after an interrupted/legacy write and must
    # be repaired by Go Live instead of being treated as ready.
    return isinstance(clim, dict) and bool(clim.get("weeks"))


def _variant_checklist(spot: Any) -> list[dict]:
    """Recommended per-variant readiness items.

    For each variant a spot actually offers (``geeignet``/``eingeschraenkt``) we
    surface — never as a blocker — what's still missing for a *belastbare*
    recommendation: a usable wind window, and for foil variants a usable depth.
    ``unbekannt``/``ungeeignet`` variants add nothing (they are not offered).
    """
    from app.admin.constants import (
        SPORT_FOIL_VARIANT,
        offered_variants,
    )

    conditions = getattr(spot, "variant_conditions", None)
    if not isinstance(conditions, dict):
        return []
    foil_keys = set(SPORT_FOIL_VARIANT.values())
    items: list[dict] = []
    for key in offered_variants(conditions):
        block = conditions.get(key) or {}
        items.append({
            "field": f"variant.{key}.wind_directions",
            "severity": "recommended",
            "ok": is_fulfilled(block.get("wind_directions")),
            "na": False,
        })
        if key in foil_keys:
            items.append({
                "field": f"variant.{key}.usable_depth_m",
                "severity": "recommended",
                "ok": is_fulfilled(block.get("usable_depth_m")),
                "na": is_na(block.get("usable_depth_m")),
            })
    return items


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

    items.extend(_variant_checklist(spot))

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
    from app.admin.constants import variant_consistency_warnings

    warnings = variant_consistency_warnings(
        spot.sports,
        getattr(spot, "variant_conditions", None),
        water_character=spot.water_character,
        level=spot.level,
    )
    from app.models import WindClimatologyV3Run
    from app.scoring.eligibility import recommendability_gaps

    recommendation_gaps = recommendability_gaps(spot, "kitesurf", db)
    active_v3 = db.scalar(
        select(WindClimatologyV3Run).where(
            WindClimatologyV3Run.spot_id == spot.id,
            WindClimatologyV3Run.is_active.is_(True),
        )
    )
    scoring_gaps = list(recommendation_gaps)
    if active_v3 is None:
        scoring_gaps.append("active_v3_run")
    scoring = {
        "kitesurf": {
            "applicable": "kitesurf" in (spot.sports or []),
            "recommendable": not recommendation_gaps,
            "ready": not scoring_gaps,
            "missing": scoring_gaps,
            "active_v3_run_id": str(active_v3.id) if active_v3 else None,
        }
    }
    return {
        "spot_id": str(spot.id),
        "status": spot.status,
        "warnings": warnings,
        "scoring": scoring,
        **result,
    }
