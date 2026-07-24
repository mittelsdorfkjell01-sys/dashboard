"""Wikimedia Commons geosearch — free photos near a spot's coordinates, with
mandatory license + credit. Behind a protocol so the network is mocked in
tests, same shape as the Unsplash stock-image seam in :mod:`app.admin.stock`.
"""

from __future__ import annotations

from typing import Protocol


class CommonsClient(Protocol):
    def search(self, lat: float, lon: float, *, radius_m: int = 1000, limit: int = 12) -> list[dict]: ...


class HttpCommonsClient:  # pragma: no cover - live network only
    """Returns a list of ``{url, width, height, license_name, license_url,
    credit, source_url}`` dicts for photos found near ``(lat, lon)``.

    Combines geosearch + imageinfo in one request. The geosearch also turns up
    parking lots and place-name signs (anything geotagged nearby, not just
    "photos of the spot") — filtering those out is a human job, done later by
    an admin hiding individual results, not something this client can judge.
    Entries with no machine-readable license are dropped: without a license
    short-name there's nothing to credit, and CC BY / CC BY-SA both require
    attribution, so an unlicensed hit is unusable either way.
    """

    API_URL = "https://commons.wikimedia.org/w/api.php"

    def search(self, lat: float, lon: float, *, radius_m: int = 1000, limit: int = 12) -> list[dict]:
        import httpx

        resp = httpx.get(
            self.API_URL,
            params={
                "action": "query",
                "generator": "geosearch",
                "ggscoord": f"{lat}|{lon}",
                "ggsradius": radius_m,
                "ggsnamespace": 6,
                "ggslimit": limit,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|size",
                "format": "json",
                "formatversion": 2,
            },
            headers={"User-Agent": "surfwinddata.com/1.0 (contact: admin@surfwinddata.com)"},
            timeout=10.0,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages") or []

        results: list[dict] = []
        for page in pages:
            info = (page.get("imageinfo") or [None])[0]
            if not info:
                continue
            meta = info.get("extmetadata") or {}
            license_name = (meta.get("LicenseShortName") or {}).get("value")
            if not license_name:
                continue
            artist = (meta.get("Artist") or {}).get("value")
            credit = (meta.get("Credit") or {}).get("value")
            results.append(
                {
                    "url": info["url"],
                    "width": info.get("width"),
                    "height": info.get("height"),
                    "license_name": license_name,
                    "license_url": (meta.get("LicenseUrl") or {}).get("value"),
                    "credit": _strip_html(artist) or _strip_html(credit) or "Wikimedia Commons",
                    "source_url": info.get("descriptionurl") or page.get("canonicalurl"),
                }
            )
        return results


def _strip_html(value: str | None) -> str | None:
    """Commons' Artist/Credit fields are free-form HTML (often just a link) —
    strip tags for a plain-text credit line."""
    if not value:
        return None
    import re

    text = re.sub(r"<[^>]+>", "", value).strip()
    return text or None


_default_client: CommonsClient | None = None


def default_commons_client() -> CommonsClient:
    global _default_client
    if _default_client is None:
        _default_client = HttpCommonsClient()
    return _default_client
