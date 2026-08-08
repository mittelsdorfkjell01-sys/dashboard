"""Spot write workflow: create, curate, override, publish."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.admin.audit import record_audit
from app.admin.constants import (
    STATUS_ARCHIVED,
    STATUS_DRAFT,
    STATUS_LIVE,
    validate_bottom_types,
    validate_facilities,
    validate_levels,
    validate_styles,
    validate_water_characters,
    validate_water_types,
)
from app.media.image_object import (
    CANONICAL_KEYS,
    build_image,
    normalize_focal,
    with_fields,
)
from app.names import available_slug, clean_display_name
from app.admin.readiness import validate_spot_readiness
from app.admin.duplicates import enforce_duplicates, find_spot_duplicates
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
    allow_duplicate: bool = False,
) -> Any:
    """Create a draft spot and inherit region defaults.

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
    duplicate_candidates = enforce_duplicates(
        "Spot",
        find_spot_duplicates(
            db,
            name=data["name"],
            region_id=region.id,
            lat=lat,
            lon=lon,
        ),
        allow_likely=allow_duplicate,
    )
    editorial = dict(defaults.get("spot_template") or {})
    editorial.update(data.get("editorial") or {})

    # Enforce the controlled category vocabularies (ValueError -> 422 at the API).
    level = validate_levels(data.get("level"))
    water_character = validate_water_characters(data.get("water_character"))
    water_type = validate_water_types(data.get("water_type"))
    bottom_type = validate_bottom_types(data.get("bottom_type"))
    style = validate_styles(data.get("style"))
    facilities = validate_facilities(data.get("facilities"))

    spot = Spot(
        slug=available_slug(db, Spot, data.get("slug") or data["name"]),
        name=clean_display_name(data["name"]),
        region_id=region.id,
        location=_point(lat, lon),
        sports=data.get("sports") or [],
        water_type=water_type,
        bottom_type=bottom_type,
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
    changes: dict[str, Any] = {"name": spot.name}
    if duplicate_candidates:
        changes["duplicate_override"] = [item["id"] for item in duplicate_candidates]
    record_audit(db, spot.id, "create", changes, actor)
    if commit:
        db.commit()
        db.refresh(spot)

    # Climatology is intentionally not started here. Editors choose the explicit
    # button, while Go Live computes it automatically when it is still missing.
    return spot


def update_spot(
    spot_id,
    data: dict,
    *,
    db: Session,
    client=None,
    actor: str | None = "admin",
    allow_duplicate: bool = False,
) -> Any:
    """Patch a spot's editorial/structural columns. Only keys present in ``data``
    are touched (so ``None`` means "clear", absent means "leave as is").

    Category axes are validated against the controlled vocabularies; an invalid
    value raises ``ValueError`` (→ 422 at the API). ``editorial`` is *merged*, so
    a partial editorial patch keeps untouched keys.
    """
    spot = _load(db, spot_id)

    from geoalchemy2.shape import to_shape

    point = to_shape(spot.location)
    proposed_region_id = data.get("region_id", spot.region_id)
    proposed_lat = float(data.get("lat", point.y))
    proposed_lon = float(data.get("lon", point.x))
    duplicate_candidates = enforce_duplicates(
        "Spot",
        find_spot_duplicates(
            db,
            name=data.get("name") or spot.name,
            region_id=proposed_region_id,
            lat=proposed_lat,
            lon=proposed_lon,
            exclude_id=spot.id,
        ),
        allow_likely=allow_duplicate,
    )

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
    coordinates_changed = data.get("lat") is not None and data.get("lon") is not None
    grid_cell_changed = False
    if coordinates_changed:
        from app.era5.grid import resolve_grid_cell

        lat, lon = float(data["lat"]), float(data["lon"])
        old_cell = spot.era5_cell
        new_cell = resolve_grid_cell(lat, lon)
        spot.location = _point(lat, lon)
        spot.era5_cell = new_cell
        grid_cell_changed = old_cell != new_cell
        if grid_cell_changed:
            from app.admin.jobs import supersede_active_jobs
            from app.era5.freshness import mark_stale

            supersede_active_jobs(spot.id, db=db, commit=False)
            spot.climatology = mark_stale(spot.climatology, "grid_cell")
    if "sports" in data and data["sports"] is not None:
        spot.sports = list(data["sports"])
    if "bottom_type" in data:
        spot.bottom_type = validate_bottom_types(data["bottom_type"])
    if "model_pref" in data:
        spot.model_pref = data["model_pref"]
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

    changes: dict[str, Any] = {"fields": sorted(data)}
    if duplicate_candidates:
        changes["duplicate_override"] = [item["id"] for item in duplicate_candidates]
    record_audit(db, spot.id, "update", changes, actor)
    if coordinates_changed:
        from app.tides.service import invalidate_for_coordinates

        invalidate_for_coordinates(spot.id, db=db, actor=actor)
    db.commit()
    db.refresh(spot)
    if (
        grid_cell_changed
        and client is not None
        and isinstance(spot.climatology, dict)
        and spot.climatology.get("weeks")
    ):
        from app.admin.jobs import trigger_era5_job

        try:
            trigger_era5_job(
                spot.id,
                db=db,
                client=client,
                force=True,
                reason="location_changed",
            )
        except Exception:
            # The stale marker is already durable; the daily maintenance run can
            # enqueue it later even if the provider is temporarily unavailable.
            db.rollback()
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
    if field == "bottom_type":
        value = validate_bottom_types(value)
    elif field == "water_type":
        value = validate_water_types(value)
    elif field == "level":
        value = validate_levels(value)
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
    """Replace the spot's hero image.

    ``image`` is a raw payload (from the URL form, the upload route, the
    community hero promotion or the media picker); it is normalised into the
    canonical object here, so provenance and focal point survive instead of
    being cut back to four fields. The rights fields url/source/license/credit
    remain mandatory.
    """
    spot = _load(db, spot_id)
    spot.image = build_image(**{k: image.get(k) for k in CANONICAL_KEYS})
    record_audit(db, spot.id, "image", {"url": spot.image["url"]}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def update_image_attribution(
    spot_id, *, credit: str, license: str, source: str, db: Session, actor="admin"
) -> Any:
    """Edit the current hero's rights fields (credit/license/source) in place,
    preserving the url, the focal point and the provenance (unlike
    manage_spot_image, which replaces the image). Used by the spot form's
    attribution editor — Wikimedia author fields in particular are unreliable
    and need correcting, but they can never be emptied."""
    spot = _load(db, spot_id)
    spot.image = with_fields(
        spot.image, credit=credit, license=license, source=source
    )
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
    focal = normalize_focal(x, y)
    spot.image = with_fields(spot.image, focal=focal)
    record_audit(db, spot.id, "image", {"focal": focal}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def set_image_geo_verified(
    spot_id, value: bool, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Mark the hero image's location as operator-verified (or unset it).

    The picker only sets `geo_verified` when the source actually carries
    coordinates near the spot; a name-match photo of the right place comes
    in as `false` and shows the "Ortsbezug ungeprüft" badge. An operator
    who has visually confirmed the location can flip that flag here.
    """
    spot = _load(db, spot_id)
    if not (isinstance(spot.image, dict) and spot.image.get("url")):
        raise ValueError("Kein Bild vorhanden.")
    spot.image = with_fields(spot.image, geo_verified=value)
    record_audit(db, spot.id, "image", {"geo_verified": value}, actor)
    db.commit()
    db.refresh(spot)
    return spot


def set_image_focal_mobile(
    spot_id, x: float | None, y: float | None, *, db: Session, actor: str | None = "admin"
) -> Any:
    """Store the hero's mobile focal point, or clear it when x/y are None.

    Kept separate from :func:`set_image_focal` so an admin can nudge one crop
    without disturbing the other — a landscape photo often needs a different
    area to survive the 16:9 mobile crop than the 21:9 desktop one.
    """
    spot = _load(db, spot_id)
    if not (isinstance(spot.image, dict) and spot.image.get("url")):
        raise ValueError("Kein Bild zum Positionieren.")
    focal_mobile = normalize_focal(x, y) if x is not None and y is not None else None
    spot.image = with_fields(spot.image, focal_mobile=focal_mobile)
    record_audit(db, spot.id, "image", {"focal_mobile": focal_mobile}, actor)
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
