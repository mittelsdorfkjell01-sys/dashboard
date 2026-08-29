"""Pure image processing/storage checks; no catalogue database required."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.config import get_settings
from app.media import (
    EncodedImageSet,
    PartialImageSetError,
    delete_image_set,
    reencode_image_set,
    save_hero_image_set,
    validate_hero_image,
)
from app.media import storage
from app.media.storage import canonical_image_url, responsive_variant_urls


def _img_bytes(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (30, 80, 140)).save(buffer, "JPEG")
    return buffer.getvalue()


def _oriented_jpeg_bytes(width: int, height: int, orientation: int) -> bytes:
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[274] = orientation
    Image.new("RGB", (width, height), (30, 80, 140)).save(
        buffer, "JPEG", exif=exif
    )
    return buffer.getvalue()


def test_exif_orientation_is_applied_before_validation_and_encoding():
    data = _oriented_jpeg_bytes(2100, 3840, 6)
    assert validate_hero_image(data, "image/jpeg")[:2] == (3840, 2100)
    encoded = reencode_image_set(data, max_width=1920)
    assert (encoded.width, encoded.height) == (1920, 1050)


def test_responsive_image_set_contains_only_real_smaller_widths():
    encoded = reencode_image_set(_img_bytes(2000, 1000), max_width=1600)
    assert (encoded.width, encoded.height) == (1600, 800)
    assert set(encoded.variants) <= {480, 768, 1280}
    next_larger_size = len(encoded.data)
    for width in sorted(encoded.variants, reverse=True):
        assert len(encoded.variants[width]) <= next_larger_size * 0.85
        next_larger_size = len(encoded.variants[width])


def test_responsive_image_set_is_saved_and_deleted_together(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "media_backend", "local")
    encoded = reencode_image_set(_img_bytes(1000, 500), max_width=1000)
    url = save_hero_image_set(
        "spot-1",
        encoded,
        media_dir=str(tmp_path),
        url_prefix="/media",
    )
    existing_variants = [
        candidate
        for candidate in responsive_variant_urls(url)
        if (tmp_path / candidate.removeprefix("/media/")).exists()
    ]
    assert "-responsive-" in url
    assert len(existing_variants) == len(encoded.variants)

    delete_image_set(url, media_dir=str(tmp_path), url_prefix="/media")
    assert not (tmp_path / url.removeprefix("/media/")).exists()
    assert not any(
        (tmp_path / candidate.removeprefix("/media/")).exists()
        for candidate in responsive_variant_urls(url)
    )


def test_identical_normalized_sets_share_one_sha256_storage_path(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "media_backend", "local")
    encoded = reencode_image_set(_img_bytes(1800, 900), max_width=1600)
    first = save_hero_image_set(
        "spot-1", encoded, media_dir=str(tmp_path), url_prefix="/media"
    )
    second = save_hero_image_set(
        "spot-2", encoded, media_dir=str(tmp_path), url_prefix="/media"
    )
    assert first == second
    assert "/images/" in first
    stored = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(stored) == 1 + len(encoded.variants)


def test_owned_local_object_existence_check_stays_inside_media_root(
    tmp_path, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_backend", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    monkeypatch.setattr(settings, "media_url_prefix", "/media")
    target = tmp_path / "images" / "present.avif"
    target.parent.mkdir()
    target.write_bytes(b"image")

    assert storage.object_exists("/media/images/present.avif") is True
    assert storage.object_exists("/media/images/missing.avif") is False
    assert storage.object_exists("/media/../../outside.avif") is False


def test_only_responsive_derivatives_are_canonicalized():
    derivative = "/media/images/aa/hash-responsive-480_768-w480.avif"
    assert canonical_image_url(derivative) == (
        "/media/images/aa/hash-responsive-480_768.avif"
    )
    assert canonical_image_url("/media/gallery/sunset-w480.jpg") == (
        "/media/gallery/sunset-w480.jpg"
    )


def test_explicit_variant_token_lists_only_files_that_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_backend", "local")
    encoded = reencode_image_set(_img_bytes(1800, 900), max_width=1600)
    url = save_hero_image_set(
        "spot-1", encoded, media_dir=str(tmp_path), url_prefix="/media"
    )
    assert len(responsive_variant_urls(url)) == len(encoded.variants)
    for width in encoded.variants:
        assert f"w{width}." in " ".join(responsive_variant_urls(url))


def test_avif_quality_is_selected_perceptually_instead_of_fixed_q85():
    flat = reencode_image_set(
        _img_bytes(1000, 500),
        max_width=1000,
        variant_widths=(),
    )
    buffer = io.BytesIO()
    gradient = Image.linear_gradient("L").resize((1000, 500)).convert("RGB")
    gradient.save(buffer, "JPEG", quality=95)
    detailed = reencode_image_set(
        buffer.getvalue(),
        max_width=1000,
        variant_widths=(),
    )

    assert flat.quality in {78, 82, 85, 88, 91}
    assert detailed.quality in {78, 82, 85, 88, 91}
    assert flat.quality < 85
    assert detailed.quality > flat.quality


def test_partial_content_addressed_write_reports_canonical_url(monkeypatch):
    encoded = EncodedImageSet(
        data=b"canonical",
        ext="avif",
        width=1000,
        height=500,
        quality=82,
        variants={480: b"variant"},
    )
    calls = []

    def fail_after_main(key, data, ext, *, media_dir, url_prefix):
        calls.append(key)
        if len(calls) == 2:
            raise RuntimeError("provider interrupted")
        return f"/media/{key}"

    monkeypatch.setattr(storage, "put", fail_after_main)
    with pytest.raises(PartialImageSetError) as raised:
        save_hero_image_set(
            "unused",
            encoded,
            media_dir="unused",
            url_prefix="/media",
        )

    assert raised.value.canonical_url.startswith("/media/images/")
    assert len(calls) == 2
