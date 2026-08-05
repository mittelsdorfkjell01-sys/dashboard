"""Spot write workflow: create, curate, override, publish."""

from __future__ import annotations

import uuid
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin.audit import record_audit
from app.admin.constants import (
    STATUS_ARCHIVED,
    STATUS_DRAFT,
    STATUS_LIVE,
    validate_facilities,
    validate_levels,
    validate_styles,
    validate_water_characters,
    validate_water_types,
)
from app.names import available_slug, clean_display_name, normalize_name
from app.admin.readiness import validate_spot_readiness
from app.services.overrides import (
    OVERRIDABLE_FIELDS,
    apply_overrides_with_provenance,
)


class NotReadyError(Exception):
    """Raised when set_spot_live is called on an incomplete spot."""

    def __init__(self, gaps: list[str], checklist: list[dict]):
        super().__init__(f"spot not ready; missing: {gaps}")
        self.gaps = gaps
        self.checklist = checklist


class DuplicateSpotError(ValueError):
    """A likely duplicate was found close to the requested coordinates."""

    def __init__(self, candidates: list[dict[str, str]]):
        super().__init__("Ein sehr ähnlicher Spot existiert bereits in der Nähe.")
        self.candidates = candidates


def _point(lat: float, lon: float):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    return from_shape(Point(lon, lat), srid=4326)


def _load(db: Session, spot_id):
    from app.models import Spot

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError(f"unknown spot {spot_id}")
    return spot


def create_spot(
    data: dict,
    *,
    db: Session,
    client=None,
    actor: str | None = "admin",
    commit: bool = True,
) -> Any:
    """Create a draft spot, inherit region defaults, and kick off the ERA5 job.

    ``data`` carries ``name``, ``region_id``, ``lat``, ``lon``, ``sports`` and the
    optional structural columns. Region ``defaults`` act as a template: ``model_pref``
    and an optional ``spot_template`` editorial blob are pre-filled when not given.
    """
    from app.era5.grid import resolve_grid_cell
    from app.models import Region, Spot

    region = db.get(Region, data["region_id"])
    if region is None:
        raise LookupError(f"unknown region {data['region_id']}")
    defaults = region.defaults or {}

    lat, lon = float(data["lat"]), float(data["lon"])
    normalized = normalize_name(data["name"])
    nearby = db.scalars(
        select(Spot).where(
            Spot.region_id == region.id,
            func.ST_DWithin(Spot.location, _point(lat, lon), 5_000),
        )
    ).all()
    duplicates = [
        {"id": str(candidate.id), "name": candidate.name}
        for candidate in nearby
        if SequenceMatcher(None, normalized, candidate.normalized_name).ratio() >= 0.9
    ]
    if duplicates:
        raise DuplicateSpotError(duplicates)
    editorial = dict(defaults.get("spot_template") or {})
    editorial.update(data.get("editorial") or {})

    # Enforce the controlled category vocabularies (ValueError -> 422 at the API).
    level = validate_levels(data.get("level"))
    water_character = validate_water_characters(data.get("water_character"))
    water_type = validate_water_types(data.get("water_type"))
    style = validate_styles(data.get("style"))
    facilities = validate_facilities(data.get("facilities"))

    spot = Spot(
        slug=available_slug(db, Spot, data.get("slug") or data["name"]),
        name=clean_display_name(data["name"]),
        region_id=region.id,
        location=_point(lat, lon),
        sports=data.get("sports") or [],
        water_type=water_type,
        bottom_type=data.get("bottom_type"),
        level=level,
        water_character=water_character,
        style=style,
        facilities=facilities,
        facing=data.get("facing"),
        model_pref=data.get("model_pref") or defaults.get("model_pref"),
        editorial=editorial or None,
        era5_cell=resolve_grid_cell(lat, lon),
        status=STATUS_DRAFT,
    )
    db.add(spot)
    db.flush()  # assign spot.id
    record_audit(db, spot.id, "create", {"name": spot.name}, actor)
    if commit:
        db.commit()
        db.refresh(spot)

    # Best-effort ERA5 trigger (idempotent); never blocks spot creation.
    if commit and client is not None:
        from app.admin.jobs import trigger_era5_job

        try:
            trigger_era5_job(spot.id, db=db, client=client)
        except Exception:
            db.rollback()
    return spot


def update_spot(
    spot_id, data: dict, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Patch a spot's editorial/structural columns. Only keys present in ``data``
    are touched (so ``None`` means "clear", absent means "leave as is").

    Category axes are validated against the controlled vocabularies; an invalid
    value raises ``ValueError`` (→ 422 at the API). ``editorial`` is *merged*, so
    a partial editorial patch keeps untouched keys.
    """
    spot = _load(db, spot_id)

    if "name" in data and data["name"]:
        spot.name = data["name"]
    if "slug" in data and data["slug"]:
        spot.slug = data["slug"]
    # Reassigning the spot's region from the edit form. Without this the PATCH
    # silently dropped region_id, so a region-less spot stayed region-less and
    # kept showing under "Spots ohne Region" on the overview. None = clear.
    if "region_id" in data:
        if data["region_id"] is None:
            spot.region_id = None
        else:
            from app.models import Region

            region = db.get(Region, data["region_id"])
            if region is None:
                raise ValueError(f"Unbekannte Region: {data['region_id']}")
            spot.region_id = region.id
    # Moving the pin: persist the new coordinates and re-resolve the ERA5 grid
    # cell so future climatology matches the corrected location. Without this the
    # PATCH silently dropped lat/lon and the pin snapped back on the next open.
    if data.get("lat") is not None and data.get("lon") is not None:
        from app.era5.grid import resolve_grid_cell

        lat, lon = float(data["lat"]), float(data["lon"])
        spot.location = _point(lat, lon)
        spot.era5_cell = resolve_grid_cell(lat, lon)
    if "sports" in data and data["sports"] is not None:
        spot.sports = list(data["sports"])
    for col in ("bottom_type", "model_pref"):
        if col in data:
            setattr(spot, col, data[col])
    if "facing" in data:
        spot.facing = data["facing"]
    if "water_type" in data:
        spot.water_type = validate_water_types(data["water_type"])
    if "level" in data:
        spot.level = validate_levels(data["level"])
    if "water_character" in data:
        spot.water_character = validate_water_characters(data["water_character"])
    if "style" in data:
        spot.style = validate_styles(data["style"])
    if "facilities" in data:
        spot.facilities = validate_facilities(data["facilities"])
    if "editorial" in data and data["editorial"] is not None:
        merged = dict(spot.editorial or {})
        for key, value in data["editorial"].items():
            if key in ("wind_danger", "hazards"):
                continue
            merged[key] = value
        spot.editorial = merged or None

    record_audit(db, spot.id, "update", {"fields": sorted(data)}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def update_spot_metadata(
    spot_id, editorial: dict, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Merge editorial fields (incl. free text). Each field takes a value or ``n/a``.

    There is intentionally no ``wind_danger``/``hazards`` field.
    """
    spot = _load(db, spot_id)
    merged = dict(spot.editorial or {})
    for key, value in (editorial or {}).items():
        if key in ("wind_danger", "hazards"):
            continue  # explicitly dropped
        merged[key] = value
    spot.editorial = merged
    record_audit(db, spot.id, "update", {"editorial_keys": sorted(editorial or {})}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def override_auto_field(
    spot_id, field: str, value: Any, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Pin ``field`` to ``value`` in ``spots.overrides`` (auto value preserved)."""
    if field not in OVERRIDABLE_FIELDS:
        raise ValueError(f"field not overridable: {field!r}")
    spot = _load(db, spot_id)
    overrides = dict(spot.overrides or {})
    auto_value = getattr(spot, field, None)
    previous = overrides.get(field)
    overrides[field] = value
    spot.overrides = overrides
    record_audit(
        db, spot.id, "override",
        {"field": field, "auto": auto_value, "from": previous, "to": value}, actor,
    )
    db.commit()
    db.refresh(spot)
    return spot


def revert_override(
    spot_id, field: str, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Drop an override so the auto value is active again."""
    spot = _load(db, spot_id)
    overrides = dict(spot.overrides or {})
    if field not in overrides:
        raise ValueError(f"no override for field: {field!r}")
    previous = overrides.pop(field)
    spot.overrides = overrides or None
    record_audit(db, spot.id, "revert", {"field": field, "from": previous}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def manage_spot_image(
    spot_id, image: dict, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Set the spot image; the rights fields url/source/license/credit are mandatory."""
    missing = [k for k in ("url", "source", "license", "credit")
               if not (isinstance(image.get(k), str) and image[k].strip())]
    if missing:
        raise ValueError(f"image missing rights fields: {missing}")
    spot = _load(db, spot_id)
    spot.image = {k: image[k] for k in ("url", "source", "license", "credit")}
    record_audit(db, spot.id, "image", {"url": image["url"]}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def update_image_attribution(
    spot_id, *, credit: str, license: str, source: str, db: Session, actor="admin"
) -> Any:
    """Edit the current hero's rights fields (credit/license/source) in place,
    preserving the url and the chosen focal point (unlike manage_spot_image,
    which resets the image). Used by the spot form's attribution editor."""
    spot = _load(db, spot_id)
    if not (spot.image and isinstance(spot.image.get("url"), str)):
        raise ValueError("no image set")
    fields = {"credit": credit, "license": license, "source": source}
    for k, v in fields.items():
        if not (isinstance(v, str) and v.strip()):
            raise ValueError(f"attribution field required: {k}")
    spot.image = {**spot.image, **{k: v.strip() for k, v in fields.items()}}
    record_audit(db, spot.id, "image", {"attribution": True}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def fetch_commons_images(spot_id, *, db: Session, client: Any) -> list[Any]:
    """Geosearch Wikimedia Commons around the spot's own coordinates and store
    any newly-licensed hits as gallery images. Returns the newly created rows
    (empty if everything found was already stored)."""
    from geoalchemy2.shape import to_shape

    from app.community.service import create_commons_image_records

    spot = _load(db, spot_id)
    point = to_shape(spot.location)
    results = client.search(point.y, point.x)
    return create_commons_image_records(db, spot_id, results)


def set_spot_live(spot_id, *, db: Session, actor: str | None = "admin") -> dict:
    """Publish a spot. Publishing is always allowed — readiness is advisory:
    the remaining gaps are returned so the UI can show a disclaimer, but they
    never block go-live."""
    readiness = validate_spot_readiness(spot_id, db=db)
    spot = _load(db, spot_id)
    spot.status = STATUS_LIVE
    record_audit(db, spot.id, "publish", {"status": STATUS_LIVE}, actor)
    db.commit()
    db.refresh(spot)
    return {
        "spot_id": str(spot.id),
        "status": spot.status,
        "ready": readiness["ready"],
        "gaps": readiness["gaps"],
    }


def set_image_focal(
    spot_id, x: float, y: float, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Store the hero image's focal point (object-position %, 0..100) so the crop
    can be nudged without re-uploading."""
    spot = _load(db, spot_id)
    if not (isinstance(spot.image, dict) and spot.image.get("url")):
        raise ValueError("Kein Bild zum Positionieren.")
    focal = {"x": max(0.0, min(100.0, float(x))), "y": max(0.0, min(100.0, float(y)))}
    spot.image = {**spot.image, "focal": focal}
    record_audit(db, spot.id, "image", {"focal": focal}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def set_spot_status(
    spot_id, status: str, *, db: Session, actor: str | None = "admin"
) -> dict:
    """Take a spot offline (``draft``) or archive it (``archived``).

    Going *live* stays in :func:`set_spot_live` (readiness-gated); this covers the
    reverse moves, which have no gate. ``published`` is rejected here so a spot can
    never skip the readiness check.
    """
    if status not in (STATUS_DRAFT, STATUS_ARCHIVED):
        raise ValueError(
            f"invalid target status {status!r}; use 'draft' (offline) or 'archived'"
        )
    spot = _load(db, spot_id)
    spot.status = status
    action = "unpublish" if status == STATUS_DRAFT else "archive"
    record_audit(db, spot.id, action, {"status": status}, actor)
    db.commit()
    db.refresh(spot)
    return {"spot_id": str(spot.id), "status": spot.status}


def reactivate_spot(spot_id, *, db: Session, actor: str | None = "admin") -> dict:
    """Bring an archived spot back into the draft workflow. Reuses the same
    "offline" move (→ draft); the caller drives it from the archived tab."""
    spot = _load(db, spot_id)
    spot.status = STATUS_DRAFT
    record_audit(db, spot.id, "reactivate", {"status": STATUS_DRAFT}, actor)
    db.commit()
    db.refresh(spot)
    return {"spot_id": str(spot.id), "status": spot.status}


def delete_spot(spot_id, *, db: Session, actor: str | None = "admin") -> None:
    """Permanently delete a spot. Dependent rows (ratings, tips, images, ERA5
    jobs, audits, favourites, watches …) are removed by the database's
    ON DELETE CASCADE / SET NULL rules. Irreversible — the caller confirms."""
    spot = _load(db, spot_id)  # raises LookupError if unknown
    db.delete(spot)
    db.commit()


def set_finish_rank(
    spot_id, rank: str | None, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Set or clear the manual "Fertigstellen" rank override.

    ``rank`` is ``red``/``yellow``/``green`` to pin the traffic-light colour, or
    ``None`` to fall back to the automatic value derived from readiness gaps.
    """
    from app.admin.rank import RANKS

    if rank is not None and rank not in RANKS:
        raise ValueError(f"invalid rank {rank!r}; use one of {RANKS} or null")
    spot = _load(db, spot_id)
    spot.finish_rank = rank
    record_audit(db, spot.id, "rank", {"finish_rank": rank}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def spot_effective_view(spot_id, *, db: Session) -> dict:
    """Effective field values with per-field provenance (``überschrieben`` / ``auto``)."""
    spot = _load(db, spot_id)
    view = apply_overrides_with_provenance(spot)
    return {"spot_id": str(spot.id), "status": spot.status, **view}
