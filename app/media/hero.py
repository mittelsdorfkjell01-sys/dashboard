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

import hashlib
import io
import struct
import uuid
from dataclasses import dataclass, field

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
# AVIF/WebP quality (0-100). These are search centres, not fixed output values:
# a representative preview is encoded around the centre and the smallest
# candidate meeting PERCEPTUAL_SSIM_MIN is used for the complete image set.
HERO_OUT_QUALITY = 85
GALLERY_OUT_QUALITY = 78
PERCEPTUAL_SSIM_MIN = 0.999
PERCEPTUAL_PREVIEW_WIDTH = 960

# Shared widths for every newly hosted image. Keeping one width ladder for
# heroes and galleries means an image can later move between both roles without
# broken srcset URLs. The original/capped output remains the canonical URL.
RESPONSIVE_IMAGE_WIDTHS = (480, 768, 1280, 1920)
RESPONSIVE_IMAGE_MARKER = "-responsive"
# A derivative must save at least 15% versus the next larger file. If it does
# not, omitting it costs no visual quality: the browser simply chooses that
# next larger source.
MIN_VARIANT_BYTE_SAVING = 0.15

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


@dataclass(frozen=True)
class EncodedImageSet:
    """One canonical image plus smaller width derivatives."""

    data: bytes
    ext: str
    width: int
    height: int
    quality: int
    variants: dict[int, bytes] = field(default_factory=dict)


def _encode_pillow_image(img, *, quality: int) -> tuple[bytes, str]:
    out = io.BytesIO()
    save_kwargs = {}
    if icc_profile := img.info.get("icc_profile"):
        save_kwargs["icc_profile"] = icc_profile
    if AVIF_AVAILABLE:
        img.save(
            out,
            format="AVIF",
            quality=quality,
            speed=4,
            subsampling="4:2:0",
            **save_kwargs,
        )
        ext = "avif"
    else:
        img.save(out, format="WEBP", quality=quality, method=6, **save_kwargs)
        ext = "webp"
    return out.getvalue(), ext


def _normalized_rgb_image(source):
    """Apply orientation and normalize embedded colour profiles to sRGB.

    EXIF/XMP metadata is deliberately not copied. If an unusual ICC profile
    cannot be transformed, it is retained so colour still renders correctly.
    """
    from PIL import ImageCms, ImageOps

    oriented = ImageOps.exif_transpose(source)
    icc_profile = source.info.get("icc_profile")
    if icc_profile:
        try:
            converted = ImageCms.profileToProfile(
                oriented,
                ImageCms.ImageCmsProfile(io.BytesIO(icc_profile)),
                ImageCms.createProfile("sRGB"),
                outputMode="RGB",
            )
            converted.info.clear()
            return converted
        except Exception:
            # A malformed/unsupported profile must not make an otherwise valid
            # upload unusable. Preserve it on the RGB conversion instead.
            converted = oriented.convert("RGB")
            converted.info.clear()
            converted.info["icc_profile"] = icc_profile
            return converted
    converted = oriented.convert("RGB")
    converted.info.clear()
    return converted


def _block_ssim(reference, candidate) -> float:
    """Mean 8×8 luminance SSIM; compact and dependency-free beyond NumPy."""
    import numpy as np

    ref = np.asarray(reference.convert("RGB"), dtype=np.float32)
    got = np.asarray(candidate.convert("RGB"), dtype=np.float32)
    ref = 0.2126 * ref[:, :, 0] + 0.7152 * ref[:, :, 1] + 0.0722 * ref[:, :, 2]
    got = 0.2126 * got[:, :, 0] + 0.7152 * got[:, :, 1] + 0.0722 * got[:, :, 2]
    height = ref.shape[0] - ref.shape[0] % 8
    width = ref.shape[1] - ref.shape[1] % 8
    if height == 0 or width == 0:
        # Upload validation normally keeps images far above one block. This
        # fallback makes the reusable encoder safe for tiny test/tool images.
        error = np.mean((ref - got) ** 2)
        return float(1 / (1 + error))
    ref = ref[:height, :width].reshape(height // 8, 8, width // 8, 8)
    got = got[:height, :width].reshape(height // 8, 8, width // 8, 8)
    ref = ref.transpose(0, 2, 1, 3)
    got = got.transpose(0, 2, 1, 3)
    ref_mean = ref.mean(axis=(2, 3))
    got_mean = got.mean(axis=(2, 3))
    ref_delta = ref - ref_mean[..., None, None]
    got_delta = got - got_mean[..., None, None]
    ref_variance = (ref_delta**2).mean(axis=(2, 3))
    got_variance = (got_delta**2).mean(axis=(2, 3))
    covariance = (ref_delta * got_delta).mean(axis=(2, 3))
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    scores = (
        (2 * ref_mean * got_mean + c1) * (2 * covariance + c2)
    ) / (
        (ref_mean**2 + got_mean**2 + c1)
        * (ref_variance + got_variance + c2)
    )
    return float(scores.mean())


def _select_perceptual_quality(img, *, centre: int) -> int:
    """Choose the smallest candidate that clears the visual-quality floor."""
    from PIL import Image

    if img.width > PERCEPTUAL_PREVIEW_WIDTH:
        preview = img.resize(
            (
                PERCEPTUAL_PREVIEW_WIDTH,
                round(img.height * PERCEPTUAL_PREVIEW_WIDTH / img.width),
            ),
            Image.LANCZOS,
        )
    else:
        preview = img
    qualities = sorted(
        {max(1, min(100, centre + offset)) for offset in (-7, -3, 0, 3, 6)}
    )
    acceptable: list[tuple[int, int]] = []
    for quality in qualities:
        payload, _ = _encode_pillow_image(preview, quality=quality)
        with Image.open(io.BytesIO(payload)) as decoded:
            decoded.load()
            score = _block_ssim(preview, decoded)
        if score >= PERCEPTUAL_SSIM_MIN:
            acceptable.append((len(payload), quality))
    return min(acceptable)[1] if acceptable else qualities[-1]


def reencode_image_set(
    data: bytes,
    *,
    max_width: int,
    quality: int = HERO_OUT_QUALITY,
    variant_widths: tuple[int, ...] = RESPONSIVE_IMAGE_WIDTHS,
) -> EncodedImageSet:
    """Normalize EXIF orientation and encode a responsive hosted image set."""
    from PIL import Image, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    if AVIF_AVAILABLE:
        import pillow_avif  # noqa: F401

    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            oriented = _normalized_rgb_image(source)
            width, height = oriented.size
            if width > max_width:
                main = oriented.resize(
                    (max_width, round(height * max_width / width)), Image.LANCZOS
                )
            else:
                main = oriented

            selected_quality = _select_perceptual_quality(main, centre=quality)
            encoded, ext = _encode_pillow_image(main, quality=selected_quality)
            final_width, final_height = main.size
            candidates: dict[int, bytes] = {}
            for variant_width in sorted(set(variant_widths), reverse=True):
                if variant_width <= 0 or variant_width >= final_width:
                    continue
                variant = main.resize(
                    (
                        variant_width,
                        round(final_height * variant_width / final_width),
                    ),
                    Image.LANCZOS,
                )
                candidates[variant_width], _ = _encode_pillow_image(
                    variant, quality=selected_quality
                )
            variants: dict[int, bytes] = {}
            next_larger_size = len(encoded)
            for variant_width in sorted(candidates, reverse=True):
                payload = candidates[variant_width]
                if len(payload) <= next_larger_size * (1 - MIN_VARIANT_BYTE_SAVING):
                    variants[variant_width] = payload
                    next_larger_size = len(payload)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HeroImageError("Bild konnte nicht verarbeitet werden.")

    return EncodedImageSet(
        data=encoded,
        ext=ext,
        width=final_width,
        height=final_height,
        quality=selected_quality,
        variants=variants,
    )


def reencode_image(
    data: bytes,
    *,
    max_width: int,
    quality: int = HERO_OUT_QUALITY,
) -> tuple[bytes, str, int, int]:
    """Downscale to ``max_width`` and encode to AVIF (or WebP). Returns
    ``(bytes, ext, width, height)``. Raises :class:`HeroImageError` if unreadable."""
    encoded = reencode_image_set(
        data, max_width=max_width, quality=quality, variant_widths=()
    )
    return encoded.data, encoded.ext, encoded.width, encoded.height


class HeroImageError(ValueError):
    """A hero image failed validation (→ 422 at the API, in German)."""


class PartialImageSetError(RuntimeError):
    """A responsive write failed after its canonical object was persisted."""

    def __init__(self, canonical_url: str, cause: Exception) -> None:
        super().__init__(str(cause))
        self.canonical_url = canonical_url


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
    from PIL import Image, ImageOps, UnidentifiedImageError

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
            width, height = ImageOps.exif_transpose(img).size
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


def save_responsive_image(
    key_base: str | None,
    encoded: EncodedImageSet,
    *,
    media_dir: str,
    url_prefix: str,
) -> str:
    """Persist a content-addressed responsive set for both storage backends.

    New callers pass ``None`` and therefore reuse the exact same SHA-256 path
    when the normalized output bytes are identical. A custom key remains
    supported for backwards-compatible tooling.
    """
    content_addressed = key_base is None
    if content_addressed:
        key_base = content_addressed_key_base(encoded)
    widths = "_".join(str(width) for width in sorted(encoded.variants)) or "none"
    base = f"{key_base}{RESPONSIVE_IMAGE_MARKER}-{widths}"
    written: list[str] = []
    try:
        main_url = storage.put(
            f"{base}.{encoded.ext}",
            encoded.data,
            encoded.ext,
            media_dir=media_dir,
            url_prefix=url_prefix,
        )
        written.append(main_url)
        for width, payload in encoded.variants.items():
            written.append(
                storage.put(
                    f"{base}-w{width}.{encoded.ext}",
                    payload,
                    encoded.ext,
                    media_dir=media_dir,
                    url_prefix=url_prefix,
                )
            )
        return main_url
    except Exception as exc:
        # Content-addressed paths may already belong to a different DB row.
        # Never roll them back here; the orphan sweep safely removes genuinely
        # unreferenced partial sets after its grace period.
        if not content_addressed:
            for url in written:
                storage.delete_url(url, media_dir=media_dir, url_prefix=url_prefix)
        if content_addressed and written:
            raise PartialImageSetError(written[0], cause=exc) from exc
        raise


def image_set_digest(encoded: EncodedImageSet) -> str:
    """Stable SHA-256 identity of the normalized canonical file and variants."""
    digest = hashlib.sha256()
    digest.update(b"surfwind-image-set-v1\0")
    digest.update(encoded.ext.encode("ascii"))
    digest.update(
        struct.pack(
            ">IIIQ",
            encoded.width,
            encoded.height,
            encoded.quality,
            len(encoded.data),
        )
    )
    digest.update(encoded.data)
    for width, payload in sorted(encoded.variants.items()):
        digest.update(struct.pack(">IQ", width, len(payload)))
        digest.update(payload)
    return digest.hexdigest()


def content_addressed_key_base(encoded: EncodedImageSet) -> str:
    checksum = image_set_digest(encoded)
    return f"images/{checksum[:2]}/{checksum}"


def save_hero_image_set(
    spot_id,
    encoded: EncodedImageSet,
    *,
    media_dir: str,
    url_prefix: str,
) -> str:
    return save_responsive_image(
        None,
        encoded,
        media_dir=media_dir,
        url_prefix=url_prefix,
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


def save_region_hero_image_set(
    region_id,
    encoded: EncodedImageSet,
    *,
    media_dir: str,
    url_prefix: str,
) -> str:
    return save_responsive_image(
        None,
        encoded,
        media_dir=media_dir,
        url_prefix=url_prefix,
    )


def _read_image(data: bytes) -> tuple[int, int, str]:
    """Verify the bytes are a real JPG/PNG and return ``(width, height, ext)``."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = ImageOps.exif_transpose(img).size
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


def save_spot_image_set(
    spot_id,
    image_id,
    encoded: EncodedImageSet,
    *,
    media_dir: str,
    url_prefix: str,
) -> str:
    return save_responsive_image(
        None,
        encoded,
        media_dir=media_dir,
        url_prefix=url_prefix,
    )
