"""Pluggable object storage for uploaded images: local disk or Vercel Blob.

Selected by ``settings.media_backend``:
- ``local`` (default): write to ``{media_dir}/{key}`` and return the root-relative
  URL ``{url_prefix}/{key}`` — as before (dev, or a VPS with a persistent volume).
- ``blob``: upload the bytes to Vercel Blob and return the public https URL — for
  serverless hosts (Vercel) whose filesystem is ephemeral/read-only.

The frontend already renders absolute image URLs unchanged (``resolveMediaUrl``),
so a Blob URL needs no frontend change.

NOTE: the Blob branch talks to Vercel Blob's REST API and can only be verified
against a real ``BLOB_READ_WRITE_TOKEN`` on a deploy — it is inert in local mode.
"""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.config import get_settings

RESPONSIVE_IMAGE_WIDTHS = (480, 768, 1280, 1920)
RESPONSIVE_IMAGE_MARKER = "-responsive"

_CONTENT_TYPE = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "avif": "image/avif",
}

_BLOB_API = "https://blob.vercel-storage.com"
_BLOB_CURRENT_API = "https://vercel.com/api/blob"


def put(key: str, data: bytes, ext: str, *, media_dir: str, url_prefix: str) -> str:
    """Store ``data`` under ``key`` (a ``/``-joined relative path) and return its
    public URL. Local mode writes to disk; blob mode uploads to Vercel Blob."""
    if get_settings().media_backend == "blob":
        return _blob_put(key, data, ext)

    path = os.path.join(media_dir, *key.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix=".upload-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.remove(temporary_path)
        except FileNotFoundError:
            pass
        raise
    return f"{url_prefix.rstrip('/')}/{key}"


def delete(key: str, *, media_dir: str) -> None:
    """Best-effort removal of a previously stored object (e.g. a stale hero of a
    different extension). A failure here is non-fatal."""
    if get_settings().media_backend == "blob":
        _blob_delete(key)
        return
    path = os.path.join(media_dir, *key.split("/"))
    if os.path.exists(path):
        os.remove(path)


def delete_url(url: str | None, *, media_dir: str, url_prefix: str) -> None:
    """Delete only URLs created by this storage module.

    External image URLs are ignored. Local paths are resolved below
    ``media_dir`` so an unexpected database value cannot escape that directory.
    """
    if not url:
        return
    settings = get_settings()
    if settings.media_backend == "blob":
        parsed = urlparse(url)
        configured_base = getattr(settings, "blob_public_base", None)
        owned = bool(
            parsed.scheme == "https"
            and (
                (
                    parsed.hostname
                    and parsed.hostname.endswith(".blob.vercel-storage.com")
                )
                or (
                    configured_base
                    and url.startswith(f"{configured_base.rstrip('/')}/")
                )
            )
        )
        if owned:
            _blob_delete_url(url)
        return

    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return
    prefix = f"{url_prefix.rstrip('/')}/"
    if not parsed.path.startswith(prefix):
        return
    key = parsed.path[len(prefix):]
    root = os.path.realpath(media_dir)
    path = os.path.realpath(os.path.join(root, *key.split("/")))
    if os.path.commonpath((root, path)) != root:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def is_owned_url(url: str | None) -> bool:
    """Whether ``url`` belongs to the configured local/Blob media backend."""
    if not url:
        return False
    settings = get_settings()
    parsed = urlparse(url)
    if settings.media_backend == "blob":
        configured_base = getattr(settings, "blob_public_base", None)
        return bool(
            parsed.scheme == "https"
            and (
                (parsed.hostname and parsed.hostname.endswith(".blob.vercel-storage.com"))
                or (
                    configured_base
                    and url.startswith(f"{configured_base.rstrip('/')}/")
                )
            )
        )
    prefix = f"{settings.media_url_prefix.rstrip('/')}/"
    return not parsed.scheme and not parsed.netloc and parsed.path.startswith(prefix)


def object_exists(url: str) -> bool:
    """Check an owned object while its lifecycle advisory lock is held."""
    if not is_owned_url(url):
        return False
    settings = get_settings()
    parsed = urlparse(url)
    if settings.media_backend == "blob":
        import httpx

        try:
            response = httpx.head(url, follow_redirects=True, timeout=15.0)
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Vercel Blob existence check failed: {type(exc).__name__}: {exc}"
            ) from exc

    prefix = f"{settings.media_url_prefix.rstrip('/')}/"
    key = parsed.path[len(prefix):]
    root = os.path.realpath(settings.media_dir)
    path = os.path.realpath(os.path.join(root, *key.split("/")))
    return os.path.commonpath((root, path)) == root and os.path.isfile(path)


def responsive_variant_urls(url: str | None) -> list[str]:
    """Return deterministic derivative URLs for a responsive hosted image.

    Old uploads do not carry the marker and therefore safely return no
    derivatives. Query strings/fragments are retained for completeness.
    """
    if not url:
        return []
    parsed = urlparse(url)
    stem, separator, extension = parsed.path.rpartition(".")
    if not separator:
        return []
    marker_at = stem.rfind(RESPONSIVE_IMAGE_MARKER)
    if marker_at < 0:
        return []
    suffix = stem[marker_at + len(RESPONSIVE_IMAGE_MARKER):]
    if not suffix:
        # Legacy sets predate the explicit width token.
        widths = RESPONSIVE_IMAGE_WIDTHS
    elif suffix == "-none":
        widths = ()
    elif re.fullmatch(r"-(?:[1-9]\d*)(?:_[1-9]\d*)*", suffix):
        widths = tuple(int(value) for value in suffix[1:].split("_"))
    else:
        return []
    urls: list[str] = []
    for width in widths:
        variant_path = f"{stem}-w{width}.{extension}"
        urls.append(parsed._replace(path=variant_path).geturl())
    return urls


def delete_image_set(url: str | None, *, media_dir: str, url_prefix: str) -> None:
    """Best-effort removal of a canonical image and all generated variants."""
    delete_url(url, media_dir=media_dir, url_prefix=url_prefix)
    for variant_url in responsive_variant_urls(url):
        delete_url(variant_url, media_dir=media_dir, url_prefix=url_prefix)


def canonical_image_url(url: str) -> str:
    """Map a responsive derivative URL back to its canonical main object."""
    parsed = urlparse(url)
    stem, separator, extension = parsed.path.rpartition(".")
    if not separator or RESPONSIVE_IMAGE_MARKER not in stem:
        return url
    canonical_stem = re.sub(r"-w[1-9]\d*$", "", stem)
    path = f"{canonical_stem}.{extension}"
    return parsed._replace(path=path).geturl()


def delete_candidate_strict(
    url: str,
    *,
    delete_set: bool,
    media_dir: str,
    url_prefix: str,
) -> None:
    """Delete one queued object/set and surface provider errors for retry."""
    urls = [url, *responsive_variant_urls(url)] if delete_set else [url]
    if get_settings().media_backend == "blob":
        _blob_delete_urls_strict(urls)
        return
    for candidate in urls:
        parsed = urlparse(candidate)
        prefix = f"{url_prefix.rstrip('/')}/"
        if parsed.scheme or parsed.netloc or not parsed.path.startswith(prefix):
            continue
        key = parsed.path[len(prefix):]
        root = os.path.realpath(media_dir)
        path = os.path.realpath(os.path.join(root, *key.split("/")))
        if os.path.commonpath((root, path)) != root:
            raise ValueError("media deletion path escaped storage root")
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def _blob_api_headers(token: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {token}",
        "x-api-version": "11",
        "x-api-blob-request-id": str(uuid.uuid4()),
    }


def list_blob_objects(
    *, prefix: str, limit: int, cursor: str | None = None
) -> dict:
    """List one official Vercel Blob page without the heavyweight full SDK."""
    import httpx

    token = get_settings().blob_read_write_token
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is not set (media_backend=blob)")
    params = {"prefix": prefix, "limit": max(1, min(1000, limit))}
    if cursor:
        params["cursor"] = cursor
    response = httpx.get(
        _BLOB_CURRENT_API,
        headers=_blob_api_headers(token),
        params=params,
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    items = []
    for blob in payload.get("blobs", []):
        uploaded = str(blob["uploadedAt"]).replace("Z", "+00:00")
        uploaded_at = datetime.fromisoformat(uploaded)
        if uploaded_at.tzinfo is None:
            uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
        items.append(
            {
                "url": blob["url"],
                "pathname": blob["pathname"],
                "size": int(blob["size"]),
                "uploaded_at": uploaded_at,
            }
        )
    return {
        "items": items,
        "cursor": payload.get("cursor"),
        "has_more": bool(payload.get("hasMore")),
    }


# --- Vercel Blob REST backend ----------------------------------------------

def _blob_put(key: str, data: bytes, ext: str) -> str:
    import httpx

    token = get_settings().blob_read_write_token
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is not set (media_backend=blob)")
    try:
        resp = httpx.put(
            f"{_BLOB_API}/{key}",
            headers={
                "authorization": f"Bearer {token}",
                "x-content-type": _CONTENT_TYPE.get(ext, "application/octet-stream"),
                # Deterministic path (overwrite the same key) instead of a random
                # suffix, so a spot's hero has a stable URL across re-uploads.
                "x-add-random-suffix": "0",
                "x-allow-overwrite": "1",
            },
            content=data,
            timeout=30.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Surface as RuntimeError so the adopt endpoint's 422 branch can
        # convert it into an operator-facing message with the actual reason
        # (wrong token, wrong store, wrong region) instead of a bare 500.
        body_snippet = (exc.response.text or "")[:200]
        raise RuntimeError(
            f"Vercel Blob PUT {exc.response.status_code}: {body_snippet}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Vercel Blob PUT failed: {type(exc).__name__}: {exc}") from exc
    return resp.json()["url"]


def _blob_delete(key: str) -> None:
    settings = get_settings()
    token = settings.blob_read_write_token
    if not token:
        return
    # Blob deletes by full URL; with x-add-random-suffix=0 the public URL is the
    # store base + key. If the base is unknown we simply skip (a stale
    # different-extension hero is harmless and gets overwritten on same-ext).
    base = getattr(settings, "blob_public_base", None)
    if not base:
        return
    _blob_delete_url(f"{base.rstrip('/')}/{key}")


def _blob_delete_url(url: str) -> None:
    try:
        _blob_delete_urls_strict([url])
    except Exception:
        pass


def _blob_delete_urls_strict(urls: list[str]) -> None:
    import httpx

    token = get_settings().blob_read_write_token
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is not set (media_backend=blob)")
    owned = [url for url in dict.fromkeys(urls) if is_owned_url(url)]
    if not owned:
        return
    headers = {
        **_blob_api_headers(token),
        "content-type": "application/json",
    }
    try:
        response = httpx.post(
            f"{_BLOB_CURRENT_API}/delete",
            headers=headers,
            json={"urls": owned},
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Vercel Blob delete failed: {type(exc).__name__}: {exc}"
        ) from exc
