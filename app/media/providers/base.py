"""Shared plumbing for the provider adapters: the request shape and HTTP."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class ProviderRequest:
    """What the picker asked for, in provider-neutral terms.

    ``role`` rides along for the adapters' benefit but must not change the
    upstream query — see ``app.media.search`` for why the cache key omits it.
    """

    query: str
    page: int = 1
    per_page: int = 24
    role: str = "hero"
    lat: float | None = None
    lon: float | None = None
    radius_km: float = 5.0


class ProviderError(RuntimeError):
    """The upstream call failed. Degrades this one tab, never the overlay."""


class ProviderUnavailable(ProviderError):
    """A required credential is missing — the tab reports ``disabled``."""


def http_get(url: str, *, params: dict, headers: dict | None = None) -> dict:
    """One GET against a provider API, returning decoded JSON.

    Every network failure — timeout, connection reset, non-2xx, malformed body —
    is re-raised as :class:`ProviderError` so the caller has exactly one failure
    mode to isolate per tab.
    """
    import httpx

    settings = get_settings()
    try:
        response = httpx.get(
            url,
            params=params,
            headers={"User-Agent": settings.wikimedia_user_agent, **(headers or {})},
            timeout=settings.media_http_timeout,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # httpx.*Error, JSONDecodeError, …
        raise ProviderError(f"{url}: {type(exc).__name__}: {exc}") from exc


# Providers whose files we host ourselves are downloaded once, at adopt time.
# Generous, because these are full-resolution originals — but bounded, so a
# mislabelled multi-gigabyte file cannot exhaust the function's memory.
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024
_DOWNLOAD_CHUNK = 512 * 1024


def download_bytes(url: str) -> bytes:
    """Fetch a remote image, aborting once it exceeds the cap.

    Streamed and checked as it arrives rather than after the fact — reading the
    whole body first would defeat the point of the limit.
    """
    import httpx

    settings = get_settings()
    chunks: list[bytes] = []
    total = 0
    try:
        with httpx.stream(
            "GET",
            url,
            headers={"User-Agent": settings.wikimedia_user_agent},
            timeout=settings.media_http_timeout * 3,
            follow_redirects=True,
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(_DOWNLOAD_CHUNK):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ProviderError(
                        f"{url}: file exceeds {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB"
                    )
                chunks.append(chunk)
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError(f"{url}: {type(exc).__name__}: {exc}") from exc
    return b"".join(chunks)


def head_status(url: str) -> int | None:
    """HTTP status of ``url``, or None when it could not be reached at all.

    Used by the source-health check. Falls back to a ranged GET because a fair
    number of CDNs answer HEAD with 405 while serving GET fine — reporting those
    as dead would be a false alarm.
    """
    import httpx

    settings = get_settings()
    try:
        response = httpx.head(
            url,
            headers={"User-Agent": settings.wikimedia_user_agent},
            timeout=settings.media_http_timeout,
            follow_redirects=True,
        )
        if response.status_code in (403, 405, 501):
            response = httpx.get(
                url,
                headers={
                    "User-Agent": settings.wikimedia_user_agent,
                    "Range": "bytes=0-0",
                },
                timeout=settings.media_http_timeout,
                follow_redirects=True,
            )
        return response.status_code
    except Exception:
        return None


def strip_html(value: str | None) -> str | None:
    """Wikimedia's Artist/Credit fields are free-form HTML (often a bare link).

    Stripped **server-side** so no provider markup can reach the admin UI.
    """
    if not value:
        return None
    import re

    text = re.sub(r"<[^>]+>", "", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None
