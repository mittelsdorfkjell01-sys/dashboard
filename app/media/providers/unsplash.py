"""Unsplash adapter.

Two API conditions shape this file:

* **Hotlink, never download.** Photos are served from Unsplash's CDN, so every
  result carries ``delivery="hotlinked"``. Sprint 3 stores the CDN URL as-is.
* **Ping ``links.download_location`` on adopt.** Not on search, not on preview —
  only when an operator actually takes the photo. Violating this costs
  production API access, so the location is carried through the result and the
  ping happens in the adopt route.

Attribution links get the UTM parameters Unsplash requires.
"""

from __future__ import annotations

from app.config import get_settings
from app.media.normalize import Credit, License, MediaResult
from app.media.providers.base import ProviderRequest, ProviderUnavailable, http_get

API_URL = "https://api.unsplash.com/search/photos"

UTM = "utm_source=surfwinddata&utm_medium=referral"

# The Unsplash License permits commercial use and modification without
# attribution — we attribute anyway, because their API terms require it.
UNSPLASH_LICENSE = License(
    name="Unsplash License",
    url="https://unsplash.com/license",
    commercial=True,
    modification=True,
)


def _with_utm(url: str | None) -> str | None:
    if not url:
        return None
    return f"{url}{'&' if '?' in url else '?'}{UTM}"


def _sized(raw_url: str | None, width: int) -> str | None:
    """Unsplash CDN URLs take sizing parameters, so one raw URL yields every
    size we need without a second request."""
    if not raw_url:
        return None
    join = "&" if "?" in raw_url else "?"
    return f"{raw_url}{join}w={width}&q=80&fm=jpg&fit=max"


class UnsplashAdapter:
    name = "unsplash"

    def available(self) -> bool:
        return bool(get_settings().unsplash_access_key)

    def search(self, request: ProviderRequest) -> list[dict]:
        key = get_settings().unsplash_access_key
        if not key:
            raise ProviderUnavailable("UNSPLASH_ACCESS_KEY is not configured")
        # No `orientation` filter: the hero gate already rejects portraits, and
        # filtering here would hide perfectly good gallery candidates.
        body = http_get(
            API_URL,
            params={
                "query": request.query,
                "page": request.page,
                "per_page": request.per_page,
            },
            headers={"Authorization": f"Client-ID {key}"},
        )
        return [body]

    def fetch(self, external_id: str) -> list[dict]:
        """Re-resolve one photo by id, in the same envelope ``parse`` expects.

        Adopt never trusts the client's copy of a search result: prices of being
        wrong here are a broken hero URL or a credit naming the wrong person.
        """
        key = get_settings().unsplash_access_key
        if not key:
            raise ProviderUnavailable("UNSPLASH_ACCESS_KEY is not configured")
        photo = http_get(
            f"https://api.unsplash.com/photos/{external_id}",
            params={},
            headers={"Authorization": f"Client-ID {key}"},
        )
        return [{"results": [photo]}]

    def ping_download(self, download_location: str) -> None:
        """Report a download to Unsplash — an API condition, not telemetry.

        Called exactly once, when an operator actually adopts the photo. Failing
        it must not fail the adoption: the image is already resolved and valid,
        and a lost ping is a smaller problem than a half-finished write.
        """
        key = get_settings().unsplash_access_key
        if not (key and download_location):
            return
        http_get(
            download_location, params={}, headers={"Authorization": f"Client-ID {key}"}
        )

    def parse(self, raw: list[dict]) -> list[MediaResult]:
        results: list[MediaResult] = []
        for body in raw:
            for photo in body.get("results") or []:
                urls = photo.get("urls") or {}
                user = photo.get("user") or {}
                full = urls.get("raw") or urls.get("full")
                if not (photo.get("id") and full):
                    continue
                results.append(
                    MediaResult(
                        provider=self.name,
                        external_id=str(photo["id"]),
                        thumb_url=urls.get("thumb") or _sized(full, 400) or full,
                        preview_url=_sized(full, 1600) or urls.get("regular") or full,
                        full_url=full,
                        width=photo.get("width"),
                        height=photo.get("height"),
                        license=UNSPLASH_LICENSE,
                        credit=Credit(
                            name=user.get("name") or user.get("username") or "Unsplash",
                            url=_with_utm((user.get("links") or {}).get("html")),
                        ),
                        source_page=_with_utm((photo.get("links") or {}).get("html")),
                        delivery="hotlinked",
                        unsplash_download_location=(photo.get("links") or {}).get(
                            "download_location"
                        ),
                    )
                )
        return results


ADAPTER = UnsplashAdapter()
