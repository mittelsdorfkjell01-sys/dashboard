"""Canonical shape of the ``image`` JSONB carried by spots and regions.

Every write path — the admin URL form, the hero upload, the community
hero-candidate promotion, the seed and (from Sprint 2 on) the media picker —
builds its image object here. Stored JSON is sparse; readers can use
``upgrade_legacy`` whenever they need the complete logical shape.
Before this module each caller assembled its own dict and
``manage_spot_image`` truncated the result back to four fields, which silently
dropped a previously chosen focal point and left nowhere to record where a photo
came from.

**License snapshot, not license reference.** ``license`` / ``license_url`` /
``credit`` hold the terms as they read at ``retrieved_at``. Photos get deleted,
accounts vanish and provider terms change; a link alone would not survive that.

**Focal points stay in the repo's format** — ``{"x": .., "y": ..}`` in *percent*
(0..100), not a 0..1 pair. That is what ``object-position`` consumes in
``HeroImage.tsx``, what ``ImageFocalEditor`` emits and what both
``POST /image/focal`` endpoints already store.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

# Machine-readable origin. The first five are the media-picker providers; the
# rest cover the paths that existed before it:
#   upload    — an operator uploaded the file through the admin form
#   community — a visitor's hero candidate, promoted in moderation
#   manual    — an operator pasted a URL (provenance is whatever they typed)
#   seed      — placeholder fixture, deliberately not a real photo
#   unknown   — rows that predate this module
PROVIDERS = frozenset(
    {
        "unsplash",
        "pexels",
        "wikimedia",
        "openverse",
        "upload",
        "community",
        "manual",
        "seed",
        "unknown",
    }
)

# hotlinked = served from the provider's CDN (Unsplash's terms require it);
# hosted    = the bytes live in our own storage.
DELIVERIES = frozenset({"hotlinked", "hosted"})

ROLES = frozenset({"hero", "gallery"})

# The four rights fields a published image must carry. Readiness
# (``app.admin.readiness.image_ready``) checks exactly these.
RIGHTS_FIELDS = ("url", "source", "license", "credit")

CENTER_FOCAL: dict[str, float] = {"x": 50.0, "y": 50.0}

# Every logical key a canonical image object understands, in a stable order.
# Stored JSONB is sparse: defaults and nulls are reconstructed by
# ``upgrade_legacy`` when an editing path needs the full logical shape.
CANONICAL_KEYS = (
    "url",
    "source",
    "license",
    "license_url",
    "credit",
    "credit_url",
    "provider",
    "external_id",
    "source_page",
    "retrieved_at",
    "delivery",
    "focal",
    "focal_mobile",
    "rotation",
    "width",
    "height",
    "geo_verified",
    "role",
    # Curated landing-hero rotation flag. True → this spot's hero photo is one of
    # the full-screen slides the landing reel cycles through (see the admin Hero
    # tab + LandingHero). Absent/False → the photo is used on tiles/detail only.
    "hero_reel",
    # Source health, written by the maintenance check (Sprint 3). "ok" |
    # "dead" | None (never checked). Photos get deleted and accounts vanish, so
    # a hero that still renders from cache can already be gone at the source.
    "source_status",
    "source_checked_at",
)

SOURCE_STATUSES = frozenset({"ok", "dead"})

COMPACT_DEFAULTS = {
    "provider": "unknown",
    "delivery": "hosted",
    "focal": CENTER_FOCAL,
    "rotation": 0.0,
    "geo_verified": False,
    "role": "hero",
    "hero_reel": False,
}
_MISSING = object()

# Seed fixtures point at this unreachable host on purpose, so the frontend
# renders its designed no-image state instead of a broken <img>. Mirrors
# ``SENTINEL_HOST`` in frontend/src/lib/api.ts.
PLACEHOLDER_HOST_SUFFIX = ".local"


class ImageObjectError(ValueError):
    """An image object failed validation.

    A ``ValueError`` subclass because the admin routes already map ``ValueError``
    to a 422 with the message shown to the operator.
    """


def normalize_focal(x: Any, y: Any) -> dict[str, float]:
    """Clamp a focal point into the stored ``{x, y}`` percent format."""
    try:
        fx, fy = float(x), float(y)
    except (TypeError, ValueError):
        raise ImageObjectError("Fokuspunkt muss aus zwei Zahlen bestehen.")
    return {"x": max(0.0, min(100.0, fx)), "y": max(0.0, min(100.0, fy))}


def normalize_rotation(value: Any) -> float:
    """Clamp a subtle horizon correction to the editor's supported range."""
    try:
        rotation = float(value)
    except (TypeError, ValueError):
        raise ImageObjectError("Drehung muss eine Zahl sein.")
    return round(max(-5.0, min(5.0, rotation)), 1)


def _coerce_focal(value: Any) -> dict[str, float]:
    if isinstance(value, dict) and "x" in value and "y" in value:
        return normalize_focal(value["x"], value["y"])
    # A two-element sequence is accepted so an external caller (or a future
    # picker payload written in the 0..1 convention) cannot store a shape the
    # renderer would silently ignore — but 0..1 pairs are scaled, not stored raw.
    if isinstance(value, (list, tuple)) and len(value) == 2:
        fx, fy = float(value[0]), float(value[1])
        if 0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0:
            return normalize_focal(fx * 100.0, fy * 100.0)
        return normalize_focal(fx, fy)
    return dict(CENTER_FOCAL)


def _clean(value: Any) -> str | None:
    """Trim a string field; empty/whitespace and non-strings become ``None``."""
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def utc_now_iso() -> str:
    """Retrieval timestamp in the ISO-8601 form the image object stores."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compact_image(image: dict) -> dict:
    """Drop reconstructable defaults and null values before JSONB storage."""
    return {
        key: value
        for key, value in image.items()
        if value is not None and COMPACT_DEFAULTS.get(key, _MISSING) != value
    }


def build_image(
    *,
    url: str,
    source: str,
    license: str,  # noqa: A002 - the stored key is "license"
    credit: str,
    license_url: str | None = None,
    credit_url: str | None = None,
    provider: str = "unknown",
    external_id: str | None = None,
    source_page: str | None = None,
    retrieved_at: str | None = None,
    delivery: str = "hosted",
    focal: Any = None,
    focal_mobile: Any = None,
    rotation: Any = 0,
    width: Any = None,
    height: Any = None,
    geo_verified: bool = False,
    role: str = "hero",
    hero_reel: bool = False,
    source_status: str | None = None,
    source_checked_at: str | None = None,
) -> dict:
    """Assemble a canonical image object, or raise :class:`ImageObjectError`.

    The four rights fields are mandatory — an image nobody can attribute is
    unusable regardless of where it came from. Optional nulls and conservative
    defaults are omitted from storage; ``upgrade_legacy`` reconstructs them.
    """
    values = {
        "url": _clean(url),
        "source": _clean(source),
        "license": _clean(license),
        "credit": _clean(credit),
    }
    missing = [key for key, value in values.items() if value is None]
    if missing:
        raise ImageObjectError(f"image missing rights fields: {missing}")

    # Callers commonly hand over ``{key: payload.get(key) for key in
    # CANONICAL_KEYS}``, so an absent enum arrives as None rather than not at
    # all. Treat that as "unspecified" and fall back to the documented default.
    provider = provider or "unknown"
    delivery = delivery or "hosted"
    role = role or "hero"

    if provider not in PROVIDERS:
        raise ImageObjectError(f"unknown image provider: {provider!r}")
    if delivery not in DELIVERIES:
        raise ImageObjectError(f"unknown image delivery: {delivery!r}")
    if role not in ROLES:
        raise ImageObjectError(f"unknown image role: {role!r}")
    if source_status is not None and source_status not in SOURCE_STATUSES:
        raise ImageObjectError(f"unknown source status: {source_status!r}")

    return compact_image({
        "url": values["url"],
        "source": values["source"],
        "license": values["license"],
        "license_url": _clean(license_url),
        "credit": values["credit"],
        "credit_url": _clean(credit_url),
        "provider": provider,
        "external_id": _clean(external_id),
        "source_page": _clean(source_page),
        "retrieved_at": _clean(retrieved_at),
        "delivery": delivery,
        "focal": _coerce_focal(focal),
        # None means "no mobile-specific focal set" — the renderer falls back
        # to `focal`. Stored as a dict once an operator picks one; different
        # from `focal` because a landscape hero cropped to 16:9 mobile often
        # needs a different area than the desktop 21:9.
        "focal_mobile": _coerce_focal(focal_mobile) if focal_mobile else None,
        "rotation": normalize_rotation(rotation or 0),
        "width": _positive_int(width),
        "height": _positive_int(height),
        "geo_verified": bool(geo_verified),
        "role": role,
        "hero_reel": bool(hero_reel),
        "source_status": source_status,
        "source_checked_at": _clean(source_checked_at),
    })


def upgrade_legacy(image: Any) -> dict | None:
    """Pad a pre-Sprint-1 image object (four fields, maybe ``focal``) to the
    canonical shape without inventing provenance.

    Unknown origin becomes ``provider="unknown"`` / ``delivery="hosted"``, a
    missing focal point becomes dead centre, everything else stays ``None``.
    Mirrors the SQL in migration ``0027_media_provenance`` so a row written by
    an older process is normalised the moment it is edited again.

    ``None`` in, ``None`` out; a non-dict value (corrupt row) is also dropped
    rather than guessed at.
    """
    if not isinstance(image, dict):
        return None
    provider = image.get("provider")
    delivery = image.get("delivery")
    role = image.get("role")
    return {
        "url": _clean(image.get("url")),
        "source": _clean(image.get("source")),
        "license": _clean(image.get("license")),
        "license_url": _clean(image.get("license_url")),
        "credit": _clean(image.get("credit")),
        "credit_url": _clean(image.get("credit_url")),
        "provider": provider if provider in PROVIDERS else "unknown",
        "external_id": _clean(image.get("external_id")),
        "source_page": _clean(image.get("source_page")),
        "retrieved_at": _clean(image.get("retrieved_at")),
        "delivery": delivery if delivery in DELIVERIES else "hosted",
        "focal": _coerce_focal(image.get("focal")),
        "focal_mobile": (
            _coerce_focal(image.get("focal_mobile"))
            if image.get("focal_mobile")
            else None
        ),
        "rotation": normalize_rotation(image.get("rotation") or 0),
        "width": _positive_int(image.get("width")),
        "height": _positive_int(image.get("height")),
        "geo_verified": bool(image.get("geo_verified")),
        "role": role if role in ROLES else "hero",
        "hero_reel": bool(image.get("hero_reel")),
        "source_status": (
            image.get("source_status")
            if image.get("source_status") in SOURCE_STATUSES
            else None
        ),
        "source_checked_at": _clean(image.get("source_checked_at")),
    }


def with_fields(previous: Any, **changes: Any) -> dict:
    """Return ``previous`` upgraded to the canonical shape with ``changes``
    applied — the merge used by the attribution and focal-point editors, which
    must not reset the rest of the object.

    Raises :class:`ImageObjectError` if there is no image to edit or the result
    would lose a rights field.
    """
    base = upgrade_legacy(previous)
    if base is None or not base.get("url"):
        raise ImageObjectError("Kein Bild vorhanden.")
    merged = {**base, **changes}
    return build_image(**{key: merged.get(key) for key in CANONICAL_KEYS})


def is_placeholder(image: Any) -> bool:
    """Whether this image is a stand-in rather than a real photo.

    Seeded fixtures point at an unreachable ``*.local`` host so the UI renders
    its no-image state. Counting those as "has an image" would make the
    readiness checklist — and the "Spots ohne Hero" work list built on it —
    report work as done that nobody has done.
    """
    if not isinstance(image, dict):
        return False
    if image.get("provider") == "seed":
        return True
    url = image.get("url")
    if not isinstance(url, str):
        return False
    host = (urlparse(url).hostname or "").lower()
    return host.endswith(PLACEHOLDER_HOST_SUFFIX)


def placeholder_image(slug: str, *, kind: str = "spot") -> dict:
    """The seed's stand-in image object for ``slug``.

    Deliberately unreachable and marked ``provider="seed"`` so both the frontend
    and :func:`is_placeholder` recognise it for what it is.
    """
    return build_image(
        url=f"https://placeholder.local/{kind}/{slug}.jpg",
        source="Seed",
        license="Platzhalter",
        credit="seed",
        provider="seed",
        delivery="hosted",
        role="hero",
    )
