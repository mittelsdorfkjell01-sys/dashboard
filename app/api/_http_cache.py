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


def set_public_cache(response: Response) -> None:
    """Mark ``response`` edge-cacheable for the public near-static reads."""
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
