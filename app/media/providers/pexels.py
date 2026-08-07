"""Pexels adapter.

The Pexels License allows commercial use and modification and asks for
attribution to the photographer plus a link back — which is what we render
anyway. ``src.original`` is the full-size file; the reported ``width``/``height``
describe that original, so the gates judge the right thing.
"""

from __future__ import annotations

from app.config import get_settings
from app.media.normalize import Credit, License, MediaResult
from app.media.providers.base import ProviderRequest, ProviderUnavailable, http_get

API_URL = "https://api.pexels.com/v1/search"

PEXELS_LICENSE = License(
    name="Pexels License",
    url="https://www.pexels.com/license/",
    commercial=True,
    modification=True,
)


class PexelsAdapter:
    name = "pexels"

    def available(self) -> bool:
        return bool(get_settings().pexels_api_key)

    def search(self, request: ProviderRequest) -> list[dict]:
        key = get_settings().pexels_api_key
        if not key:
            raise ProviderUnavailable("PEXELS_API_KEY is not configured")
        body = http_get(
            API_URL,
            params={
                "query": request.query,
                "page": request.page,
                "per_page": request.per_page,
            },
            headers={"Authorization": key},
        )
        return [body]

    def fetch(self, external_id: str) -> list[dict]:
        key = get_settings().pexels_api_key
        if not key:
            raise ProviderUnavailable("PEXELS_API_KEY is not configured")
        photo = http_get(
            f"https://api.pexels.com/v1/photos/{external_id}",
            params={},
            headers={"Authorization": key},
        )
        return [{"photos": [photo]}]

    def parse(self, raw: list[dict]) -> list[MediaResult]:
        results: list[MediaResult] = []
        for body in raw:
            for photo in body.get("photos") or []:
                src = photo.get("src") or {}
                original = src.get("original")
                if not (photo.get("id") and original):
                    continue
                results.append(
                    MediaResult(
                        provider=self.name,
                        external_id=str(photo["id"]),
                        thumb_url=src.get("tiny") or src.get("small") or original,
                        preview_url=src.get("large2x") or src.get("large") or original,
                        full_url=original,
                        width=photo.get("width"),
                        height=photo.get("height"),
                        license=PEXELS_LICENSE,
                        credit=Credit(
                            name=photo.get("photographer") or "Pexels",
                            url=photo.get("photographer_url"),
                        ),
                        source_page=photo.get("url"),
                        # Pexels permits hosting the file ourselves, which gets
                        # us our own derivatives and removes a third-party
                        # dependency from the hero's critical path.
                        delivery="hosted",
                    )
                )
        return results


ADAPTER = PexelsAdapter()
