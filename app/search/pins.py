"""Map pins: private ranking, public spot serialisation, and zoom clustering."""

from __future__ import annotations

from typing import Any

from app.scoring import Scorer

# Score tiers -> colour bucket for map pins (live or seasonal value, via scorer).
_COLOR_TIERS = (
    (0.75, "green"),
    (0.5, "lime"),
    (0.25, "amber"),
    (0.0, "grey"),
)

# Below this zoom level, nearby pins are merged into clusters.
CLUSTER_ZOOM_THRESHOLD = 8


def coords(spot: Any) -> tuple[float, float]:
    """(lat, lon) for a spot's geography point."""
    from geoalchemy2.shape import to_shape

    p = to_shape(spot.location)
    return p.y, p.x


def spot_brief(spot: Any) -> dict:
    lat, lon = coords(spot)
    return {
        "id": str(getattr(spot, "id", "")),
        "slug": getattr(spot, "slug", None),
        "name": getattr(spot, "name", None),
        "location": {"lat": lat, "lon": lon},
        "sports": list(getattr(spot, "sports", None) or []),
    }


def value_to_color(value: float | None) -> str:
    if value is None:
        return "grey"
    for threshold, color in _COLOR_TIERS:
        if value >= threshold:
            return color
    return "grey"


def build_pin(
    spot: Any, time_context: dict | None, profile: dict | None, *, scorer: Scorer
) -> dict:
    """Serialize one pin without exposing the score used by collection ranking."""
    del time_context, profile, scorer
    return spot_brief(spot)


def build_pins(
    spots: list[Any], time_context: dict | None, profile: dict | None, *, scorer: Scorer
) -> list[dict]:
    ranked = sorted(
        spots,
        key=lambda spot: float(scorer.score(spot, time_context, profile)),
        reverse=True,
    )
    return [spot_brief(spot) for spot in ranked]


def _cell_size_deg(zoom: int) -> float:
    """Grid cell size for clustering; coarser (larger) at lower zoom."""
    return max(0.05, 2 ** (8 - max(zoom, 0)) * 0.05)


def cluster_pins(pins: list[dict], zoom: int) -> list[dict]:
    """Cluster pins into grid cells at low zoom; pass through at high zoom.

    Each output item is ``{lat, lon, count, spot_ids, cluster: bool}``. At/above
    :data:`CLUSTER_ZOOM_THRESHOLD` every pin is its own (count-1) cluster.
    """
    if zoom >= CLUSTER_ZOOM_THRESHOLD:
        return [
            {
                "lat": p["location"]["lat"],
                "lon": p["location"]["lon"],
                "count": 1,
                "spot_ids": [p["id"]],
                "cluster": False,
            }
            for p in pins
        ]

    cell = _cell_size_deg(zoom)
    buckets: dict[tuple[int, int], list[dict]] = {}
    for p in pins:
        lat, lon = p["location"]["lat"], p["location"]["lon"]
        key = (int(lat // cell), int(lon // cell))
        buckets.setdefault(key, []).append(p)

    clusters: list[dict] = []
    for members in buckets.values():
        n = len(members)
        clusters.append(
            {
                "lat": round(sum(m["location"]["lat"] for m in members) / n, 6),
                "lon": round(sum(m["location"]["lon"] for m in members) / n, 6),
                "count": n,
                "spot_ids": [m["id"] for m in members],
                "cluster": n > 1,
            }
        )
    return clusters
