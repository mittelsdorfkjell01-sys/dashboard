"""Deterministic geographic model selection for public weather fields."""

from __future__ import annotations

from collections.abc import Iterable


HEALTHY_FRESHNESS = frozenset({"fresh", "delayed"})
VIEWPORT_EDGE_TOLERANCE_DEG = 0.25


def point_in_coverage(
    coverage: dict, *, latitude: float, longitude: float
) -> bool:
    return (
        float(coverage["west"]) <= longitude <= float(coverage["east"])
        and float(coverage["south"]) <= latitude <= float(coverage["north"])
    )


def bounds_in_coverage(coverage: dict, bounds: dict) -> bool:
    """Return whether a publication covers the viewport apart from tile overscan.

    Map cameras commonly request a narrow strip beyond the visible edge.  A
    quarter degree tolerance prevents that strip from replacing a detailed
    regional field with a coarser global field while preserving real geographic
    fallback outside the regional model.
    """
    tolerance = VIEWPORT_EDGE_TOLERANCE_DEG
    return (
        float(coverage["west"]) - tolerance <= float(bounds["west"])
        and float(coverage["south"]) - tolerance <= float(bounds["south"])
        and float(coverage["east"]) + tolerance >= float(bounds["east"])
        and float(coverage["north"]) + tolerance >= float(bounds["north"])
    )


def rank_model_candidates(
    models: Iterable[dict],
    *,
    latitude: float | None,
    longitude: float | None,
    requested_model: str | None,
    primary_model: str,
    bounds: dict | None = None,
) -> list[dict]:
    """Order candidates without blending or inventing data outside coverage."""
    candidates = list(models)
    for item in candidates:
        item["covers_point"] = (
            point_in_coverage(
                item["coverage"], latitude=latitude, longitude=longitude
            )
            if latitude is not None and longitude is not None
            else True
        )
        item["covers_viewport"] = (
            bounds_in_coverage(item["coverage"], bounds) if bounds is not None else True
        )

    def key(item: dict) -> tuple[int, int, int, str]:
        explicitly_requested = (
            requested_model is not None and item["key"] == requested_model
        )
        if requested_model is not None:
            group = 0 if explicitly_requested else 1 if item["covers_point"] else 2
        elif bounds is not None:
            group = 0 if item["covers_viewport"] else 2
        elif latitude is not None and longitude is not None:
            group = 0 if item["covers_point"] else 2
        else:
            group = 0 if item["key"] == primary_model else 1
        healthy = item.get("freshness") in HEALTHY_FRESHNESS
        return (group, 0 if healthy else 1, int(item["priority"]), str(item["key"]))

    return sorted(candidates, key=key)
