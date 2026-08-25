"""Shared Cache-Control for public, near-static GET endpoints.

These responses (the spot list/record, the region list/record) change only when
an admin edits data. Tagging them with ``s-maxage`` lets Vercel's edge CDN serve
them without invoking the Python function or waking Neon — so a first page open
(e.g. the landing's "aktuelle Top Spots") isn't blocked on a cold start.

``stale-while-revalidate`` hides the cold revalidation entirely: once the fresh
window lapses the edge returns the slightly stale copy instantly and refreshes in
the background, so no visitor ever waits on the cold function.

Only used on the public read path; live/forecast stay uncached (time-sensitive),
and the /admin* write endpoints never set this.
"""

from fastapi import Response

# 10s fresh at the edge, then served stale for up to 5 min while it revalidates
# in the background. Short enough that an admin editing a spot (focal point,
# attribution, gallery, publish) sees the change on the public site within
# ~10s, long enough to still absorb bursty landing-page reads without
# hammering the origin.
PUBLIC_CACHE_CONTROL = "public, s-maxage=10, stale-while-revalidate=300"

# The featured ranking is deliberately stable for a UTC day. Keep it at the
# edge for six hours and allow yesterday's result while Vercel refreshes it in
# the background. That removes repeated serverless cold starts from the landing
# path without making ordinary edited spot/region responses stale for hours.
TOP_SPOTS_CACHE_CONTROL = (
    "public, max-age=300, s-maxage=21600, stale-while-revalidate=86400"
)

# The public map attaches the catalogue version (count + latest updated_at) to
# its spot-list URL.  A versioned URL is immutable: an editorial change produces
# a different URL, so the old response can safely stay at the edge for a day.
# The cheap version token itself is cached only briefly, bounding publication
# delay while preventing every open map tab from querying Postgres each minute.
MAP_CATALOG_CACHE_CONTROL = (
    "public, max-age=60, s-maxage=86400, stale-while-revalidate=604800"
)
CATALOG_VERSION_CACHE_CONTROL = (
    "public, max-age=15, s-maxage=60, stale-while-revalidate=60"
)


def set_public_cache(response: Response) -> None:
    """Mark ``response`` edge-cacheable for the public near-static reads."""
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL


def set_top_spots_cache(response: Response) -> None:
    """Cache the daily featured ranking more aggressively than edited content."""
    response.headers["Cache-Control"] = TOP_SPOTS_CACHE_CONTROL


def set_map_catalog_cache(response: Response) -> None:
    """Cache one immutable, version-addressed public map catalogue."""
    response.headers["Cache-Control"] = MAP_CATALOG_CACHE_CONTROL


def set_catalog_version_cache(response: Response) -> None:
    """Briefly edge-cache the public map's inexpensive change token."""
    response.headers["Cache-Control"] = CATALOG_VERSION_CACHE_CONTROL
