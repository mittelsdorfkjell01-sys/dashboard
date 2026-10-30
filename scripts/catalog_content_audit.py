"""Read-only catalogue/content audit for seeds and an optional public runtime.

The command never opens a database session and never writes to the remote
service.  Runtime counts therefore describe only records visible through the
public API; draft and moderation counts remain explicitly unknown.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


from app.admin.content_review import content_consistency_warnings


def _is_placeholder_image(value: Any) -> bool:
    """Match known placeholder hosts without trusting URL substrings."""
    try:
        host = (urlsplit(str(value or "")).hostname or "").rstrip(".").lower()
    except ValueError:
        return False
    return host in {"placeholder.local", "example.com"} or host.endswith(
        (".placeholder.local", ".example.com")
    )


def _fetch_json(url: str, *, timeout: float = 15.0) -> Any:
    request = Request(url, headers={"User-Agent": "surfwinddata-catalog-audit/1"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - explicit operator URL
        return json.load(response)


def seed_inventory() -> dict[str, Any]:
    from app.seed.data import REGIONS as CORE_REGIONS, SPOTS as CORE_SPOTS
    from app.seed.data_europe import REGIONS as EU_REGIONS, SPOTS as EU_SPOTS

    spots = [*CORE_SPOTS, *EU_SPOTS]
    return {
        "scope": "repository_seed_definitions_not_live_data",
        "regions": {
            "core": len(CORE_REGIONS),
            "europe": len(EU_REGIONS),
            "combined_unique": len({row["slug"] for row in [*CORE_REGIONS, *EU_REGIONS]}),
        },
        "spots": {
            "core": len(CORE_SPOTS),
            "europe": len(EU_SPOTS),
            "combined_unique": len({row["slug"] for row in spots}),
            "by_status": dict(sorted(Counter(row.get("status", "unknown") for row in spots).items())),
            "sport_memberships": dict(sorted(Counter(
                sport for row in spots for sport in row.get("sports", [])
            ).items())),
        },
    }


def description_warnings(spot: dict[str, Any]) -> list[str]:
    return content_consistency_warnings(spot)


def runtime_inventory(
    spots: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    details: list[dict[str, Any]],
) -> dict[str, Any]:
    coverage_keys = {
        "description": lambda row: bool((row.get("editorial") or {}).get("description")),
        "safety_notice": lambda row: bool((row.get("editorial") or {}).get("safety_notice")),
        "tide": lambda row: bool((row.get("editorial") or {}).get("tide")),
        "usable_wind_directions": lambda row: bool(
            (row.get("editorial") or {}).get("usable_wind_directions")
        ),
        "variant_conditions": lambda row: bool(row.get("variant_conditions")),
        "variant_hazards": lambda row: any(
            bool((value or {}).get("hazards"))
            for value in (row.get("variant_conditions") or {}).values()
        ),
        "variant_local_rules": lambda row: any(
            bool((value or {}).get("local_rules"))
            for value in (row.get("variant_conditions") or {}).values()
        ),
        "variant_entry": lambda row: any(
            bool((value or {}).get("entry"))
            for value in (row.get("variant_conditions") or {}).values()
        ),
        "variant_launch_area": lambda row: any(
            bool((value or {}).get("launch_area"))
            for value in (row.get("variant_conditions") or {}).values()
        ),
        "content_source": lambda row: bool(
            (row.get("editorial") or {}).get("source")
            or (row.get("editorial") or {}).get("sources")
        ),
        "content_last_checked": lambda row: bool(
            (row.get("editorial") or {}).get("last_checked")
        ),
        "image": lambda row: bool(row.get("image")),
        "image_license": lambda row: bool((row.get("image") or {}).get("license")),
        "origin": lambda row: bool(row.get("origin")),
    }
    country_sports: dict[str, Counter] = defaultdict(Counter)
    for row in spots:
        country = row.get("region_country") or "unknown"
        country_sports[country]["spots"] += 1
        country_sports[country].update(row.get("sports") or [])

    warning_rows = [
        {"slug": row.get("slug"), "name": row.get("name"), "warnings": warnings}
        for row in details
        if (warnings := description_warnings(row))
    ]
    placeholder_regions = sum(
        _is_placeholder_image((row.get("image") or {}).get("url"))
        for row in regions
    )
    return {
        "scope": "public_api_only_drafts_and_pending_are_unknown",
        "spots": {
            "count": len(spots),
            "by_status": dict(sorted(Counter(row.get("status", "unknown") for row in spots).items())),
            "by_origin": dict(sorted(Counter(row.get("origin", "unknown") for row in spots).items())),
            "sport_memberships": dict(sorted(Counter(
                sport for row in spots for sport in row.get("sports", [])
            ).items())),
            "country_sport_matrix": {
                country: dict(sorted(values.items()))
                for country, values in sorted(country_sports.items())
            },
            "content_coverage": {
                key: sum(bool(predicate(row)) for row in details)
                for key, predicate in coverage_keys.items()
            },
            "content_warnings": warning_rows,
        },
        "regions": {
            "count": len(regions),
            "by_status": dict(sorted(Counter(row.get("status", "unknown") for row in regions).items())),
            "without_season": sum(not row.get("season") for row in regions),
            "without_description": sum(not row.get("description") for row in regions),
            "without_image": sum(not row.get("image") for row in regions),
            "placeholder_or_example_image": placeholder_regions,
            "zero_spots": [row.get("slug") for row in regions if not row.get("spot_count")],
            "single_spot": [row.get("slug") for row in regions if row.get("spot_count") == 1],
        },
        "community_pending": "unknown_not_publicly_exposed",
    }


def audit_runtime(api_base: str, *, workers: int = 4) -> dict[str, Any]:
    base = api_base.rstrip("/") + "/"
    spots = _fetch_json(urljoin(base, "spots"))
    regions = _fetch_json(urljoin(base, "regions"))
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as executor:
        details = list(executor.map(
            lambda row: _fetch_json(urljoin(base, f"spots/{row['slug']}")), spots
        ))
    return runtime_inventory(spots, regions, details)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base",
        help="Optional public API base, e.g. https://surfwinddata.com/api. GET only.",
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    result: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_inventory": seed_inventory(),
        "runtime_inventory": "not_requested",
    }
    if args.api_base:
        result["runtime_inventory"] = audit_runtime(args.api_base, workers=args.workers)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
