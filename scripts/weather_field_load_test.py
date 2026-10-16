"""Bounded async load test for map-open and immutable forecast assets."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import math
import statistics
import time
from urllib.parse import urljoin

import httpx


@dataclass
class Result:
    elapsed_ms: float
    ok: bool


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return math.inf
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


async def hit(client: httpx.AsyncClient, url: str) -> Result:
    started = time.perf_counter()
    try:
        response = await client.get(url)
        ok = 200 <= response.status_code < 400
    except httpx.HTTPError:
        ok = False
    return Result((time.perf_counter() - started) * 1000, ok)


def tile_coordinates(longitude: float, latitude: float, zoom: int) -> tuple[int, int]:
    latitude = min(85.05112878, max(-85.05112878, latitude))
    x = int(((longitude + 180) / 360) * 2**zoom)
    y = int((1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * 2**zoom)
    return max(0, min(2**zoom - 1, x)), max(0, min(2**zoom - 1, y))


def asset_urls(base_url: str, payload: dict) -> list[str]:
    manifest = payload.get("manifest") or {}
    times = manifest.get("valid_times") or []
    lods = (manifest.get("tile_scheme") or {}).get("lod") or []
    coverage = manifest.get("coverage") or {}
    if not times or not lods or not coverage:
        return []
    zoom = int(lods[0]["source_zoom"])
    lon = (float(coverage["west"]) + float(coverage["east"])) / 2
    lat = (float(coverage["south"]) + float(coverage["north"])) / 2
    x, y = tile_coordinates(lon, lat, zoom)
    time_keys = []
    for value in (times[0], times[min(1, len(times) - 1)]):
        parsed = time.strptime(str(value)[:13], "%Y-%m-%dT%H")
        time_keys.append(time.strftime("%Y%m%dT%HZ", parsed))
    field_template = str(manifest.get("field_template", ""))
    urls = [
        field_template.replace("{valid_time}", key).replace("{z}", str(zoom)).replace("{x}", str(x)).replace("{y}", str(y))
        for key in dict.fromkeys(time_keys)
    ]
    # Adjacent cell exercises a pan without requiring another manifest call.
    if field_template:
        urls.append(field_template.replace("{valid_time}", time_keys[0]).replace("{z}", str(zoom)).replace("{x}", str(min(2**zoom - 1, x + 1))).replace("{y}", str(y)))
    series_template = manifest.get("series_template")
    if series_template:
        urls.append(str(series_template).replace("{z}", str(zoom)).replace("{x}", str(x)).replace("{y}", str(y)))
    return [urljoin(base_url + "/", url) for url in urls if url]


async def run(
    base_url: str,
    users: int,
    requests_per_user: int,
    *,
    include_assets: bool = True,
) -> list[Result]:
    limits = httpx.Limits(max_connections=users, max_keepalive_connections=min(users, 100))
    timeout = httpx.Timeout(20)
    async with httpx.AsyncClient(base_url=base_url, limits=limits, timeout=timeout) as client:
        async def journey() -> list[Result]:
            results = []
            for _ in range(requests_per_user):
                for endpoint in ("/weather-fields/wind", "/weather-fields/waves"):
                    started = time.perf_counter()
                    try:
                        response = await client.get(endpoint)
                        ok = 200 <= response.status_code < 400
                        results.append(Result((time.perf_counter() - started) * 1000, ok))
                        if ok and include_assets:
                            for url in asset_urls(base_url, response.json()):
                                results.append(await hit(client, url))
                    except (httpx.HTTPError, ValueError):
                        results.append(Result((time.perf_counter() - started) * 1000, False))
            return results

        groups = await asyncio.gather(*(journey() for _ in range(users)))
    return [result for group in groups for result in group]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, choices=(100, 500, 1000), default=100)
    parser.add_argument("--requests-per-user", type=int, default=2)
    parser.add_argument("--max-p95-ms", type=float, default=500)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Exercise the API control plane without downloading CDN-served assets.",
    )
    args = parser.parse_args()
    results = asyncio.run(
        run(
            args.base_url.rstrip("/"),
            args.users,
            args.requests_per_user,
            include_assets=not args.manifest_only,
        )
    )
    durations = [result.elapsed_ms for result in results]
    failures = sum(not result.ok for result in results)
    error_rate = failures / len(results) if results else 1.0
    p95 = percentile(durations, 0.95)
    print(
        f"users={args.users} requests={len(results)} errors={failures} "
        f"error_rate={error_rate:.4f} median_ms={statistics.median(durations):.1f} "
        f"p95_ms={p95:.1f}"
    )
    return 0 if p95 <= args.max_p95_ms and error_rate <= args.max_error_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
