"""Taking a search result into the catalogue.

The client sends only an identity — provider, external id, role, target — never
a payload. Everything else is re-resolved from the provider here, because a
result that has been sitting in a browser tab may be stale, and because a
client-supplied credit or URL is a client-supplied claim about someone else's
rights.

Two delivery paths, decided by the provider and never by the caller:

* **Unsplash** — no download, ever. The CDN URL is stored and
  ``links.download_location`` is pinged once, which is an API condition rather
  than analytics. Ignoring it costs production access.
* **Everyone else** — the file is copied into our own storage and re-encoded,
  so the hero does not depend on a third party staying up.

Multi-width derivatives and the blur placeholder are deliberately *not* here:
the repo has single-width re-encoding only, and ``HeroImage``'s srcset path is
wired to build-time assets. Building that properly is its own piece of work.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.media import budget as budget_store
from app.media import storage
from app.media.hero import (
    GALLERY_OUT_MAX_WIDTH,
    GALLERY_OUT_QUALITY,
    HERO_OUT_MAX_WIDTH,
    HERO_OUT_QUALITY,
    HeroImageError,
    reencode_image,
)
from app.media.image_object import build_image, normalize_focal, utc_now_iso
from app.media.normalize import MediaResult, adoptable, gallery_eligible, hero_eligible
from app.media.providers import get_provider
from app.media.providers.base import ProviderError, head_status
from app.media.providers import unsplash as unsplash_module
from app.models import MediaUsage, Region, Spot, SpotImage

logger = logging.getLogger(__name__)

ENTITY_TYPES = ("spot", "region")
ROLES = ("hero", "gallery")


class AdoptError(ValueError):
    """The adoption is not allowed — maps to 422 with the operator-facing text."""


class DuplicateHeroError(AdoptError):
    """This photo is already in use elsewhere, so it must not become a hero."""

    def __init__(self, message: str, usages: list[dict]) -> None:
        super().__init__(message)
        self.usages = usages


@dataclass
class AdoptResult:
    entity_type: str
    entity_id: uuid.UUID
    role: str
    image: dict | None = None
    gallery_image_id: uuid.UUID | None = None
    demoted_hero: bool = False
    warnings: list[str] = field(default_factory=list)


def _load_entity(db: Session, entity_type: str, entity_id):
    if entity_type == "spot":
        entity = db.get(Spot, entity_id)
    elif entity_type == "region":
        entity = db.get(Region, entity_id)
    else:
        raise AdoptError(f"Unbekannter Typ: {entity_type}")
    if entity is None:
        raise LookupError(f"unknown {entity_type} {entity_id}")
    return entity


def _resolve(db: Session, provider: str, external_id: str) -> MediaResult:
    """Fetch the photo from its provider again and normalise it.

    Counted against the hourly budget but deliberately **not** blocked by it: the
    budget exists so browsing cannot exhaust the quota, and refusing the one
    action all that browsing was for would be perverse. If the provider itself
    rate-limits us, that surfaces as a plain error.
    """
    adapter = get_provider(provider)
    if not adapter.available():
        raise AdoptError(f"Quelle {provider} ist nicht konfiguriert.")
    if not hasattr(adapter, "fetch"):
        raise AdoptError(f"Quelle {provider} unterstützt keine Einzelabfrage.")

    try:
        raw = adapter.fetch(external_id)
    except ProviderError as exc:
        raise AdoptError(f"Bild konnte nicht neu geladen werden: {exc}")
    budget_store.budget_consume(db, provider)

    results = adapter.parse(raw)
    if not results:
        raise AdoptError(
            "Das Bild ist bei der Quelle nicht mehr verfügbar oder hat keine "
            "verwertbare Lizenz mehr."
        )
    return results[0]


def _check_gate(result: MediaResult, role: str) -> None:
    """Re-run the size and license gates server-side.

    The search response already carried these flags, but a client can send
    anything, and the size that matters is the one the provider reports now.
    """
    if not adoptable(result):
        raise AdoptError(
            f"Lizenz „{result.license.name}“ erlaubt keine kommerzielle Nutzung "
            "oder Bearbeitung."
        )
    size = f"{result.width or '?'}×{result.height or '?'} px"
    if role == "hero" and not hero_eligible(result.width, result.height):
        raise AdoptError(
            f"Für ein Header-Bild zu klein ({size}) — mindestens 3840×1920 px nötig."
        )
    if role == "gallery" and not gallery_eligible(result.width, result.height):
        raise AdoptError(
            f"Für die Galerie zu klein ({size}) — lange Kante mindestens 1600 px."
        )


def _existing_usages(db: Session, provider: str, external_id: str) -> list[MediaUsage]:
    return list(
        db.scalars(
            select(MediaUsage).where(
                MediaUsage.provider == provider,
                MediaUsage.external_id == external_id,
            )
        ).all()
    )


def _describe(db: Session, usage: MediaUsage) -> dict:
    if usage.entity_type == "spot":
        entity = db.get(Spot, usage.entity_id)
    else:
        entity = db.get(Region, usage.entity_id)
    return {
        "entity_type": usage.entity_type,
        "entity_id": str(usage.entity_id),
        "name": getattr(entity, "name", None) or "—",
        "role": usage.role,
    }


def _check_duplicates(
    db: Session, *, provider: str, external_id: str, role: str, entity_id
) -> list[str]:
    """Hard block for heroes, warning for the gallery.

    The same stock photo on a dozen entries destroys a catalogue's credibility
    faster than a missing image does, and the hero is where it shows. A gallery
    reuse is a judgement call, so it warns and lets the operator decide.
    """
    others = [
        usage
        for usage in _existing_usages(db, provider, external_id)
        if usage.entity_id != entity_id
    ]
    if not others:
        return []

    described = [_describe(db, usage) for usage in others]
    if role == "hero":
        first = described[0]
        where = "Hero" if first["role"] == "hero" else "Galeriebild"
        name = first["name"]
        raise DuplicateHeroError(
            f"Dieses Foto ist bereits {where} bei „{name}“. "
            "Ein Header-Bild muss eindeutig sein.",
            described,
        )
    names = ", ".join(f"„{item['name']}“" for item in described)
    return [f"Dieses Foto wird bereits verwendet bei {names}."]


def _store_locally(result: MediaResult, *, entity_type: str, entity_id, role: str) -> dict:
    """Download, re-encode and store the file; returns the stored url + size."""
    from app.media.providers.base import download_bytes

    settings = get_settings()
    max_width = HERO_OUT_MAX_WIDTH if role == "hero" else GALLERY_OUT_MAX_WIDTH
    quality = HERO_OUT_QUALITY if role == "hero" else GALLERY_OUT_QUALITY

    try:
        data = download_bytes(result.full_url)
        out, ext, width, height = reencode_image(data, max_width=max_width, quality=quality)
    except ProviderError as exc:
        raise AdoptError(f"Bild konnte nicht geladen werden: {exc}")
    except HeroImageError as exc:
        raise AdoptError(str(exc))

    key = f"{entity_type}s/{entity_id}/{role}-{uuid.uuid4().hex}.{ext}"
    url = storage.put(
        key,
        out,
        ext,
        media_dir=settings.media_dir,
        url_prefix=settings.media_url_prefix,
    )
    return {"url": url, "width": width, "height": height, "delivery": "hosted"}


def _prepare_file(result: MediaResult, *, entity_type: str, entity_id, role: str) -> dict:
    """Either hotlink (Unsplash) or copy into our storage (everyone else)."""
    if result.delivery == "hotlinked":
        if result.provider == unsplash_module.ADAPTER.name:
            try:
                unsplash_module.ADAPTER.ping_download(result.unsplash_download_location)
            except ProviderError as exc:
                # The adoption itself is valid and complete; a lost ping is the
                # smaller problem. Logged loudly because repeated failures do
                # put API access at risk.
                logger.warning("unsplash download ping failed for %s: %s", result.external_id, exc)
        return {
            "url": result.full_url,
            "width": result.width,
            "height": result.height,
            "delivery": "hotlinked",
        }
    return _store_locally(result, entity_type=entity_type, entity_id=entity_id, role=role)


def _next_position(db: Session, entity_type: str, entity_id) -> int:
    column = SpotImage.spot_id if entity_type == "spot" else SpotImage.region_id
    highest = db.scalar(
        select(func.max(SpotImage.position)).where(column == entity_id)
    )
    return int(highest or 0) + 1


def _gallery_row(
    db: Session,
    *,
    entity_type: str,
    entity_id,
    image: dict,
    status: str = "approved",
) -> SpotImage:
    """Store an image object as a gallery row for either entity type."""
    row = SpotImage(
        spot_id=entity_id if entity_type == "spot" else None,
        region_id=entity_id if entity_type == "region" else None,
        url=image["url"],
        kind="gallery",
        width=image.get("width"),
        height=image.get("height"),
        source=image.get("source") or "unknown",
        provider=image.get("provider"),
        external_id=image.get("external_id"),
        delivery=image.get("delivery") or "hosted",
        credit=image.get("credit"),
        credit_url=image.get("credit_url"),
        license_name=image.get("license"),
        license_url=image.get("license_url"),
        source_url=image.get("source_page"),
        geo_verified=bool(image.get("geo_verified")),
        position=_next_position(db, entity_type, entity_id),
        status=status,
    )
    db.add(row)
    return row


def _record_usage(
    db: Session, *, provider: str, external_id: str | None, entity_type: str, entity_id, role: str
) -> None:
    if not external_id:
        # Uploads and legacy images have no provider identity, so they cannot
        # take part in duplicate detection — recording them would be noise.
        return
    existing = db.scalar(
        select(MediaUsage).where(
            MediaUsage.provider == provider,
            MediaUsage.external_id == external_id,
            MediaUsage.entity_type == entity_type,
            MediaUsage.entity_id == entity_id,
        )
    )
    if existing is not None:
        existing.role = role
        return
    db.add(
        MediaUsage(
            provider=provider,
            external_id=external_id,
            entity_type=entity_type,
            entity_id=entity_id,
            role=role,
        )
    )


def adopt(
    db: Session,
    *,
    entity_type: str,
    entity_id,
    role: str,
    provider: str,
    external_id: str,
    focal: dict | None = None,
) -> AdoptResult:
    """Take a provider photo into the catalogue as hero or gallery image."""
    if entity_type not in ENTITY_TYPES:
        raise AdoptError(f"Unbekannter Typ: {entity_type}")
    if role not in ROLES:
        raise AdoptError(f"Unbekannte Rolle: {role}")

    entity = _load_entity(db, entity_type, entity_id)
    result = _resolve(db, provider, external_id)
    _check_gate(result, role)
    warnings = _check_duplicates(
        db, provider=provider, external_id=external_id, role=role, entity_id=entity.id
    )

    if not result.geo_verified:
        # Never a block — a photo of the right place found by name is normal,
        # and the admin decides. It is marked so nobody later mistakes an
        # unverified location for a verified one.
        warnings.append("Ortsbezug ungeprüft.")

    stored = _prepare_file(result, entity_type=entity_type, entity_id=entity.id, role=role)

    image = build_image(
        url=stored["url"],
        source=result.provider.title(),
        license=result.license.name,
        license_url=result.license.url,
        credit=result.credit.name,
        credit_url=result.credit.url,
        provider=result.provider,
        external_id=result.external_id,
        source_page=result.source_page,
        retrieved_at=utc_now_iso(),
        delivery=stored["delivery"],
        focal=normalize_focal(focal["x"], focal["y"]) if focal else None,
        width=stored["width"],
        height=stored["height"],
        geo_verified=result.geo_verified,
        role=role,
        source_status="ok",
        source_checked_at=utc_now_iso(),
    )

    outcome = AdoptResult(
        entity_type=entity_type, entity_id=entity.id, role=role, warnings=warnings
    )

    if role == "hero":
        previous = entity.image if isinstance(entity.image, dict) else None
        if previous and previous.get("url") and previous["url"] != image["url"]:
            # The old hero is demoted, not deleted: someone chose it once, and a
            # replacement is not a judgement that it was worthless.
            _gallery_row(
                db, entity_type=entity_type, entity_id=entity.id, image=previous
            )
            if previous.get("provider") and previous.get("external_id"):
                _record_usage(
                    db,
                    provider=previous["provider"],
                    external_id=previous["external_id"],
                    entity_type=entity_type,
                    entity_id=entity.id,
                    role="gallery",
                )
            outcome.demoted_hero = True
        entity.image = image
        outcome.image = image
    else:
        row = _gallery_row(
            db, entity_type=entity_type, entity_id=entity.id, image=image
        )
        db.flush()
        outcome.gallery_image_id = row.id
        outcome.image = image

    _record_usage(
        db,
        provider=result.provider,
        external_id=result.external_id,
        entity_type=entity_type,
        entity_id=entity.id,
        role=role,
    )
    db.commit()
    return outcome


# --- source health ---------------------------------------------------------

def verify_sources(db: Session, *, limit: int = 100) -> dict:
    """Check stored image URLs and mark the ones that have gone away.

    Operator-triggered rather than scheduled: it makes outbound requests to
    every provider and its value is in being run before a content review, not
    every night.
    """
    checked = 0
    dead: list[dict] = []
    now = utc_now_iso()

    for model, entity_type in ((Spot, "spot"), (Region, "region")):
        rows = db.scalars(
            select(model).where(model.image.isnot(None)).limit(limit)
        ).all()
        for entity in rows:
            image = entity.image
            if not isinstance(image, dict) or not image.get("url"):
                continue
            checked += 1
            status = head_status(image["url"])
            alive = status is not None and status < 400
            entity.image = {
                **image,
                "source_status": "ok" if alive else "dead",
                "source_checked_at": now,
            }
            if not alive:
                dead.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": str(entity.id),
                        "name": entity.name,
                        "url": image["url"],
                        "status": status,
                    }
                )
    db.commit()
    return {"checked": checked, "dead": dead, "checked_at": now}
