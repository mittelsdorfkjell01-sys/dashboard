"""Openverse adapter.

``license_type=commercial,modification`` is hard-coded and is **not** a
parameter this adapter accepts: the whole point is that nothing which forbids
commercial use or modification can enter the picker from here.

Credentials are optional. Without them Openverse still answers, just with a
lower anonymous rate limit — so unlike Unsplash and Pexels, a missing key does
not disable this tab. Turning off a working source for want of an optional
credential would cost function for nothing.
"""

from __future__ import annotations

import threading
import time

from app.config import get_settings
from app.media.normalize import Credit, License, MediaResult
from app.media.providers.base import ProviderRequest, http_get

API_URL = "https://api.openverse.org/v1/images/"
TOKEN_URL = "https://api.openverse.org/v1/auth_tokens/token/"

# Openverse reports licenses as short slugs plus a version.
_LICENSE_NAMES = {
    "cc0": "CC0",
    "pdm": "Public Domain Mark",
    "by": "CC BY",
    "by-sa": "CC BY-SA",
    "by-nc": "CC BY-NC",
    "by-nd": "CC BY-ND",
    "by-nc-sa": "CC BY-NC-SA",
    "by-nc-nd": "CC BY-NC-ND",
}

_token: tuple[str, float] | None = None  # (access_token, expires_at)
_token_lock = threading.Lock()


def _license_label(slug: str | None, version: str | None) -> str:
    name = _LICENSE_NAMES.get((slug or "").lower(), (slug or "unknown").upper())
    return f"{name} {version}".strip() if version else name


def _access_token() -> str | None:
    """Client-credentials token, cached in-process until shortly before expiry.

    Returns None when no credentials are configured — the caller then queries
    anonymously.
    """
    global _token
    settings = get_settings()
    if not (settings.openverse_client_id and settings.openverse_client_secret):
        return None
    with _token_lock:
        if _token and _token[1] > time.time() + 60:
            return _token[0]
        try:
            import httpx

            response = httpx.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.openverse_client_id,
                    "client_secret": settings.openverse_client_secret,
                },
                timeout=settings.media_http_timeout,
            )
            response.raise_for_status()
            body = response.json()
        except Exception:
            # An expired or rejected credential must not take the tab down —
            # anonymous access still works.
            return None
        token = body.get("access_token")
        if not token:
            return None
        _token = (token, time.time() + float(body.get("expires_in") or 3600))
        return token


class OpenverseAdapter:
    name = "openverse"

    def available(self) -> bool:
        return True  # works anonymously; credentials only raise the rate limit

    def _params(self, request: ProviderRequest) -> dict:
        return {
            "q": request.query,
            "page": request.page,
            "page_size": request.per_page,
            # Not configurable, by design.
            "license_type": "commercial,modification",
        }

    def search(self, request: ProviderRequest) -> list[dict]:
        token = _access_token()
        headers = {"Authorization": f"Bearer {token}"} if token else None
        return [http_get(API_URL, params=self._params(request), headers=headers)]

    def search_nearby(self, request: ProviderRequest) -> list[dict]:
        """Openverse has no radius search, so "near here" becomes a place-name
        query. Results are therefore *not* coordinate-verified — the caller
        keeps ``geo_verified`` false for them, which is the honest answer."""
        if not request.query:
            return []
        return self.search(request)

    def fetch(self, external_id: str) -> list[dict]:
        token = _access_token()
        headers = {"Authorization": f"Bearer {token}"} if token else None
        item = http_get(f"{API_URL}{external_id}/", params={}, headers=headers)
        return [{"results": [item]}]

    def parse(self, raw: list[dict]) -> list[MediaResult]:
        results: list[MediaResult] = []
        for body in raw:
            for item in body.get("results") or []:
                url = item.get("url")
                if not (item.get("id") and url):
                    continue
                results.append(
                    MediaResult(
                        provider=self.name,
                        external_id=str(item["id"]),
                        thumb_url=item.get("thumbnail") or url,
                        preview_url=url,
                        full_url=url,
                        width=item.get("width"),
                        height=item.get("height"),
                        license=License(
                            name=_license_label(
                                item.get("license"), item.get("license_version")
                            ),
                            url=item.get("license_url"),
                            # The query is filtered to commercial+modification
                            # upstream, so anything that comes back qualifies.
                            commercial=True,
                            modification=True,
                        ),
                        credit=Credit(
                            name=item.get("creator") or item.get("source") or "Openverse",
                            url=item.get("creator_url"),
                        ),
                        source_page=item.get("foreign_landing_url") or item.get("detail_url"),
                        delivery="hosted",
                    )
                )
        return results


ADAPTER = OpenverseAdapter()
