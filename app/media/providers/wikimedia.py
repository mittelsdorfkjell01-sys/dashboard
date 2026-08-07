"""Wikimedia Commons adapter — text search and coordinate search.

Commons is the one provider whose licenses genuinely vary per file, so the
license short name decides whether a result is usable at all. Files with no
machine-readable license are dropped: without a name there is nothing to
attribute, and CC BY / BY-SA both require attribution, so an unlicensed hit is
unusable either way.

Author fields arrive as free-form HTML and are stripped here, server-side.

Note: ``app.admin.commons`` still serves the older "fetch nearby Commons photos
into the spot gallery" endpoint. It is retired in Sprint 6 together with the
one-shot stock-image route; until then both exist, and this module is the one
the picker uses.
"""

from __future__ import annotations

from app.media.normalize import Credit, License, MediaResult
from app.media.providers.base import ProviderRequest, http_get, strip_html

API_URL = "https://commons.wikimedia.org/w/api.php"

# Short names as they appear in extmetadata.LicenseShortName. Only licenses that
# permit commercial use *and* modification are marked adoptable; everything else
# still shows up in the grid, greyed out with its real license name.
_LICENSE_TERMS: dict[str, tuple[bool, bool]] = {
    "cc0": (True, True),
    "public domain": (True, True),
    "pd": (True, True),
    "cc by 1.0": (True, True),
    "cc by 2.0": (True, True),
    "cc by 2.5": (True, True),
    "cc by 3.0": (True, True),
    "cc by 4.0": (True, True),
    "cc by-sa 1.0": (True, True),
    "cc by-sa 2.0": (True, True),
    "cc by-sa 2.5": (True, True),
    "cc by-sa 3.0": (True, True),
    "cc by-sa 4.0": (True, True),
}

_IMAGE_NAMESPACE = 6


def _license_terms(short_name: str) -> tuple[bool, bool]:
    """(commercial, modification) for a Commons short name.

    Unknown or restricted names default to ``(False, False)``: NC and ND
    variants must never be adoptable, and guessing in the permissive direction
    is the expensive mistake.
    """
    key = short_name.strip().lower()
    if "nc" in key.split() or "-nc" in key or "noncommercial" in key:
        return (False, False)
    if "nd" in key.split() or "-nd" in key or "noderiv" in key:
        return (False, False)
    return _LICENSE_TERMS.get(key, (False, False))


_COMMON_PARAMS = {
    "action": "query",
    "prop": "imageinfo",
    "iiprop": "url|size|extmetadata",
    "format": "json",
    "formatversion": "2",
}


class WikimediaAdapter:
    name = "wikimedia"

    def available(self) -> bool:
        return True  # no credential, only a descriptive User-Agent

    def search(self, request: ProviderRequest) -> list[dict]:
        body = http_get(
            API_URL,
            params={
                **_COMMON_PARAMS,
                "generator": "search",
                "gsrsearch": request.query,
                "gsrnamespace": _IMAGE_NAMESPACE,
                "gsrlimit": request.per_page,
                "gsroffset": max(0, (request.page - 1) * request.per_page),
            },
        )
        return [body]

    def search_nearby(self, request: ProviderRequest) -> list[dict]:
        """Files geotagged within ``radius_km`` of the given coordinates."""
        if request.lat is None or request.lon is None:
            return []
        body = http_get(
            API_URL,
            params={
                **_COMMON_PARAMS,
                "generator": "geosearch",
                "ggscoord": f"{request.lat}|{request.lon}",
                "ggsradius": int(min(10_000, max(10, request.radius_km * 1000))),
                "ggsnamespace": _IMAGE_NAMESPACE,
                "ggslimit": request.per_page,
            },
        )
        return [body]

    def fetch(self, external_id: str) -> list[dict]:
        """Re-resolve by page id. Commons ids are numeric; a non-numeric value
        (a URL, from an older row) has no lookup and yields nothing."""
        if not str(external_id).isdigit():
            return []
        return [
            http_get(API_URL, params={**_COMMON_PARAMS, "pageids": int(external_id)})
        ]

    def parse(self, raw: list[dict], *, geo_verified: bool = False) -> list[MediaResult]:
        results: list[MediaResult] = []
        for body in raw:
            pages = (body.get("query") or {}).get("pages") or []
            for page in pages:
                info = (page.get("imageinfo") or [None])[0]
                if not info or not info.get("url"):
                    continue
                meta = info.get("extmetadata") or {}
                license_name = strip_html(
                    (meta.get("LicenseShortName") or {}).get("value")
                )
                if not license_name:
                    continue
                commercial, modification = _license_terms(license_name)
                credit = strip_html(
                    (meta.get("Artist") or {}).get("value")
                ) or strip_html((meta.get("Credit") or {}).get("value"))
                results.append(
                    MediaResult(
                        provider=self.name,
                        external_id=str(page.get("pageid") or info["url"]),
                        thumb_url=info.get("thumburl") or info["url"],
                        preview_url=info["url"],
                        full_url=info["url"],
                        width=info.get("width"),
                        height=info.get("height"),
                        license=License(
                            name=license_name,
                            url=strip_html((meta.get("LicenseUrl") or {}).get("value")),
                            commercial=commercial,
                            modification=modification,
                        ),
                        credit=Credit(name=credit or "Wikimedia Commons"),
                        source_page=info.get("descriptionurl") or page.get("canonicalurl"),
                        delivery="hosted",
                        geo_verified=geo_verified,
                    )
                )
        return results


ADAPTER = WikimediaAdapter()
