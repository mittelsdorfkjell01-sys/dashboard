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
import tempfile
from urllib.parse import urlparse

from app.config import get_settings

_CONTENT_TYPE = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "avif": "image/avif",
}

_BLOB_API = "https://blob.vercel-storage.com"


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
        if url.startswith("https://"):
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


# --- Vercel Blob REST backend ----------------------------------------------

def _blob_put(key: str, data: bytes, ext: str) -> str:
    import httpx

    token = get_settings().blob_read_write_token
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is not set (media_backend=blob)")
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
    return resp.json()["url"]


def _blob_delete(key: str) -> None:
    import httpx

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
    import httpx

    token = get_settings().blob_read_write_token
    if not token:
        return
    try:
        response = httpx.post(
            f"{_BLOB_API}/delete",
            headers={
                "authorization": f"Bearer {token}",
                "content-type": "application/json",
            },
            json={"urls": [url]},
            timeout=15.0,
        )
        response.raise_for_status()
    except Exception:
        pass
