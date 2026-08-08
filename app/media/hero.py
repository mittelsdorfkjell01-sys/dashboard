"""Hero-image requirements, validation, re-encoding and on-disk storage.

Uploads are validated (min dimensions + landscape for hero, max bytes), then
**re-encoded server-side**: downscaled to a sane max width and converted to AVIF
(falls back to built-in WebP if the AVIF plugin isn't installed). So a large,
heavy original is accepted but only a small optimised file is stored/served.

The frontend gate in ``frontend/src/components/ImageUpload.tsx`` (``HERO_REQ``)
mirrors the *input* rules (min 3840×2000, landscape, ≤ 40 MB); the backend
re-validates because a client gate can be bypassed.
"""

from __future__ import annotations

import io
import uuid
import os

from app.media import storage

# --- input requirements (mirror of frontend HERO_REQ) ----------------------
HERO_MIN_WIDTH = 3840
HERO_MIN_HEIGHT = 2000
HERO_MAX_BYTES = 40 * 1024 * 1024  # 40 MB original (re-encoded down on save)

# Community gallery uploads: moderate min size, same generous byte cap.
GALLERY_MIN_WIDTH = 1280
GALLERY_MIN_HEIGHT = 720
GALLERY_MAX_BYTES = 40 * 1024 * 1024  # 40 MB
MAX_IMAGE_PIXELS = 50_000_000
UPLOAD_CHUNK_BYTES = 1024 * 1024

# --- output re-encoding -----------------------------------------------------
HERO_OUT_MAX_WIDTH = 3840     # 4K wide is plenty; downscale beyond this
GALLERY_OUT_MAX_WIDTH = 2560
# AVIF/WebP quality (0-100). The hero is a full-bleed showcase image, so it
# gets near-visually-lossless quality — AVIF Q90 on a 3840 px source is
# ~1–2 MB and holds detail on Retina/4K displays, where a picked stock
# photo previously read as soft after Q82 AVIF compression.
HERO_OUT_QUALITY = 90
GALLERY_OUT_QUALITY = 78

# Accepted *input* content types -> canonical extension (output is avif/webp).
_CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _avif_available() -> bool:
    try:
        import pillow_avif  # noqa: F401  registers the AVIF plugin with Pillow

        return True
    except Exception:
        return False


AVIF_AVAILABLE = _avif_available()
OUTPUT_EXT = "avif" if AVIF_AVAILABLE else "webp"


def reencode_image(data: bytes, *, max_width: int, quality: int = HERO_OUT_QUALITY) -> tuple[bytes, str, int, int]:
    """Downscale to ``max_width`` and encode to AVIF (or WebP). Returns
    ``(bytes, ext, width, height)``. Raises :class:`HeroImageError` if unreadable."""
    from PIL import Image, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    if AVIF_AVAILABLE:
        import pillow_avif  # noqa: F401

    try:
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            w, h = img.size
            if w > max_width:
                img = img.resize((max_width, round(h * max_width / w)), Image.LANCZOS)
            out = io.BytesIO()
            if AVIF_AVAILABLE:
                img.save(out, format="AVIF", quality=quality)
                ext = "avif"
            else:
                img.save(out, format="WEBP", quality=quality, method=6)
                ext = "webp"
            fw, fh = img.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HeroImageError("Bild konnte nicht verarbeitet werden.")
    return out.getvalue(), ext, fw, fh


class HeroImageError(ValueError):
    """A hero image failed validation (→ 422 at the API, in German)."""


async def read_upload_limited(upload, max_bytes: int) -> bytes:
    """Read an UploadFile in bounded chunks and abort before retaining excess."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            mb = max_bytes // (1024 * 1024)
            raise HeroImageError(f"Datei zu groß (max. {mb} MB).")
        chunks.append(chunk)
    return b"".join(chunks)


def validate_hero_image(
    data: bytes, content_type: str | None, *, allow_below_min: bool = False
) -> tuple[int, int, str]:
    """Validate raw bytes against the hero rules.

    Returns ``(width, height, ext)`` on success; raises :class:`HeroImageError`
    with a German message otherwise. The actual pixel format is verified with
    Pillow, not trusted from the declared content type.

    ``allow_below_min`` skips only the minimum-resolution checks (used by the
    admin upload, which mirrors the client's "below min is allowed with a
    warning" behaviour). Format, byte size and landscape orientation are always
    enforced.
    """
    from PIL import Image, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    if len(data) > HERO_MAX_BYTES:
        mb = HERO_MAX_BYTES // (1024 * 1024)
        raise HeroImageError(f"Datei zu groß (max. {mb} MB).")
    if content_type not in _CONTENT_TYPE_EXT:
        raise HeroImageError("Format muss JPG, PNG oder WebP sein.")

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()  # cheap integrity check
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HeroImageError("Bild konnte nicht gelesen werden.")

    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(fmt)
    if ext is None:
        raise HeroImageError("Format muss JPG, PNG oder WebP sein.")

    if height >= width:
        raise HeroImageError(f"Querformat erforderlich (aktuell {width}×{height} px).")

    if not allow_below_min:
        if width < HERO_MIN_WIDTH:
            raise HeroImageError(
                f"Zu klein: {width}×{height} px — mindestens {HERO_MIN_WIDTH} px Breite nötig."
            )
        if height < HERO_MIN_HEIGHT:
            raise HeroImageError(
                f"Zu niedrig: {width}×{height} px — mindestens {HERO_MIN_HEIGHT} px Höhe nötig."
            )

    return width, height, ext


def save_hero_image(spot_id, data: bytes, ext: str, *, media_dir: str, url_prefix: str) -> str:
    """Write the hero image to ``{media_dir}/spots/{spot_id}/hero.{ext}``.

    Uses a versioned key so the prior DB reference remains valid until the new
    object and database update both succeed."""
    version = uuid.uuid4().hex
    return storage.put(
        f"spots/{spot_id}/hero-{version}.{ext}", data, ext,
        media_dir=media_dir, url_prefix=url_prefix,
    )


def save_region_hero_image(
    region_id, data: bytes, ext: str, *, media_dir: str, url_prefix: str
) -> str:
    """Write a region hero to ``{media_dir}/regions/{region_id}/hero.{ext}``.

    Mirrors :func:`save_hero_image` with a versioned key."""
    version = uuid.uuid4().hex
    return storage.put(
        f"regions/{region_id}/hero-{version}.{ext}", data, ext,
        media_dir=media_dir, url_prefix=url_prefix,
    )


def _read_image(data: bytes) -> tuple[int, int, str]:
    """Verify the bytes are a real JPG/PNG and return ``(width, height, ext)``."""
    from PIL import Image, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HeroImageError("Bild konnte nicht gelesen werden.")
    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(fmt)
    if ext is None:
        raise HeroImageError("Format muss JPG, PNG oder WebP sein.")
    return width, height, ext


def validate_gallery_image(data: bytes, content_type: str | None) -> tuple[int, int, str]:
    """Validate a community gallery image against the moderate limits.

    Raises :class:`HeroImageError` (→ 422, German) on failure; returns
    ``(width, height, ext)`` on success.
    """
    if len(data) > GALLERY_MAX_BYTES:
        mb = GALLERY_MAX_BYTES // (1024 * 1024)
        raise HeroImageError(f"Datei zu groß (max. {mb} MB).")
    width, height, ext = _read_image(data)
    if width < GALLERY_MIN_WIDTH or height < GALLERY_MIN_HEIGHT:
        raise HeroImageError(
            f"Zu klein: {width}×{height} px — mindestens "
            f"{GALLERY_MIN_WIDTH}×{GALLERY_MIN_HEIGHT} px nötig."
        )
    return width, height, ext


def save_spot_image(
    spot_id, image_id, data: bytes, ext: str, *, media_dir: str, url_prefix: str
) -> str:
    """Store a community image at ``{media_dir}/spots/{spot_id}/img/{image_id}.{ext}``.

    Unlike the single hero, a spot has many of these, so each keeps its own id in
    the filename. Returns the public URL (root-relative local / absolute Blob)."""
    return storage.put(
        f"spots/{spot_id}/img/{image_id}.{ext}", data, ext,
        media_dir=media_dir, url_prefix=url_prefix,
    )
