"""Deterministic phase-2 directional geofeatures. Never imported by physics."""

from __future__ import annotations
import hashlib
import math
from dataclasses import dataclass
import numpy as np

SHADOW_VERSION = "swd-shadow-v2-sectors16-rays9"
SECTOR_CENTERS = tuple(i * 22.5 for i in range(16))
RAY_OFFSETS = tuple(np.linspace(-9, 9, 9))
RINGS_M = ((0, 250), (250, 2000), (2000, 20000), (20000, 100000))
ROUGHNESS_GROUP = {
    10: "high",
    20: "medium",
    30: "low_medium",
    40: "low_medium",
    50: "high_heterogeneous",
    60: "very_low",
    70: "very_low",
    80: "water",
    90: "low_medium",
    95: "high",
    100: "very_low",
}
ROUGHNESS_SCORE = {
    "water": 0,
    "very_low": 0.15,
    "low_medium": 0.4,
    "medium": 0.6,
    "high": 0.85,
    "high_heterogeneous": 1,
}


@dataclass(frozen=True)
class MetricRaster:
    water: np.ndarray
    landcover: np.ndarray
    elevation_m: np.ndarray
    pixel_m: float
    center: tuple[int, int]

    def sample(self, bearing: float, distance_m: float) -> tuple[int, int] | None:
        rad = math.radians(bearing)  # meteorological upwind: 0 means trace north.
        row = round(self.center[0] - math.cos(rad) * distance_m / self.pixel_m)
        col = round(self.center[1] + math.sin(rad) * distance_m / self.pixel_m)
        return (
            (row, col)
            if 0 <= row < self.water.shape[0] and 0 <= col < self.water.shape[1]
            else None
        )


def ray_distances(max_m: float = 100000) -> np.ndarray:
    return np.unique(
        np.concatenate(
            (
                np.arange(30, 250, 30),
                np.arange(250, 2000, 60),
                np.arange(2000, 20000, 180),
                np.arange(20000, max_m + 1, 600),
            )
        )
    )


def analyze_ray(grid: MetricRaster, bearing: float, max_m: float = 100000) -> dict:
    distances = ray_distances(max_m)
    samples = []
    for distance in distances:
        cell = grid.sample(bearing, float(distance))
        if cell is None:
            samples.append((distance, None, None, None))
            continue
        r, c = cell
        water = int(grid.water[r, c])
        cover = int(grid.landcover[r, c])
        elevation = float(grid.elevation_m[r, c])
        samples.append(
            (
                distance,
                water if water in (0, 1, 2, 3) else None,
                cover if cover else None,
                elevation if np.isfinite(elevation) else None,
            )
        )
    valid = [s for s in samples if s[1] is not None]
    water_samples = [s for s in valid if s[1] in (1, 2, 3)]
    certain_land = [s[0] for s in valid if s[1] == 0]
    transitions = sum(1 for a, b in zip(valid, valid[1:]) if a[1] != b[1])
    first_land = min(certain_land) if certain_land else None
    longest = 0.0
    run = 0.0
    previous = 0.0
    for distance, water, _, _ in valid:
        step = distance - previous
        previous = distance
        if water in (1, 2, 3):
            run += step
            longest = max(longest, run)
        else:
            run = 0
    rings = {}
    for low, high in RINGS_M:
        ring = [s for s in valid if low < s[0] <= high]
        rings[f"{low}-{high}m"] = {
            "water_fraction": sum(s[1] in (1, 2, 3) for s in ring) / len(ring)
            if ring
            else None,
            "coverage": len(ring) / max(1, sum(low < d <= high for d in distances)),
        }
    anchor = float(grid.elevation_m[grid.center])
    max_angle = None
    blocker_distance = None
    blocker_height = None
    for distance, _, _, elevation in valid:
        if (
            distance < 2 * grid.pixel_m
            or distance > 20000
            or elevation is None
            or not np.isfinite(anchor)
        ):
            continue
        curvature = distance * distance / (2 * 6_371_000)
        relative = elevation - anchor - curvature
        angle = math.degrees(math.atan2(relative, distance))
        if max_angle is None or angle > max_angle:
            max_angle, blocker_distance, blocker_height = (
                angle,
                float(distance),
                float(relative),
            )
    covers = [s[2] for s in valid if s[2] is not None and s[0] <= 5000]
    groups = (
        {
            name: sum(ROUGHNESS_GROUP.get(c) == name for c in covers) / len(covers)
            # Stable order is part of the scientific hash. Iterating a set made
            # floating-point summation differ by ~1e-17 between processes.
            for name in sorted(set(ROUGHNESS_GROUP.values()))
        }
        if covers
        else {}
    )
    roughness = (
        sum(ROUGHNESS_SCORE[k] * v for k, v in groups.items()) if groups else None
    )
    double_count = any(c in (10, 50, 95) for c in covers)
    return {
        "bearing_deg": bearing % 360,
        "first_certain_land_m": float(first_land) if first_land is not None else None,
        "longest_water_m": longest,
        "censored": bool(first_land is None and valid and valid[-1][0] >= max_m - 600),
        "water_land_transitions": transitions,
        "water_types": {
            str(code): sum(s[1] == code for s in water_samples) / len(water_samples)
            if water_samples
            else 0
            for code in (1, 2, 3)
        },
        "rings": rings,
        "coverage": len(valid) / len(samples),
        "nodata_fraction": 1 - len(valid) / len(samples),
        "terrain": {
            "horizon_angle_deg": max_angle,
            "blocker_distance_m": blocker_distance,
            "relative_height_m": blocker_height,
        },
        "roughness": {
            "groups": groups,
            "index": roughness,
            "possible_double_counting": double_count,
        },
    }


def _quantile(values, q):
    clean = [v for v in values if v is not None]
    return float(np.quantile(clean, q)) if clean else None


def analyze_sectors(grid: MetricRaster) -> list[dict]:
    out = []
    for index, center in enumerate(SECTOR_CENTERS):
        rays = [analyze_ray(grid, center + float(offset)) for offset in RAY_OFFSETS]
        valid = [r for r in rays if r["coverage"] >= 0.8]
        lands = [r["first_certain_land_m"] for r in valid]
        longest = [r["longest_water_m"] for r in valid]
        angles = [r["terrain"]["horizon_angle_deg"] for r in valid]
        status = "valid" if len(valid) >= 6 else "degraded" if valid else "unavailable"
        out.append(
            {
                "sector_index": index,
                "center_deg": center,
                "status": status,
                "features": {
                    "fetch": {
                        "first_land_p10_m": _quantile(lands, 0.1),
                        "first_land_median_m": _quantile(lands, 0.5),
                        "first_land_p90_m": _quantile(lands, 0.9),
                        "longest_water_median_m": _quantile(longest, 0.5),
                        "open_ray_fraction": sum(r["censored"] for r in valid)
                        / len(valid)
                        if valid
                        else None,
                        "censored": any(r["censored"] for r in valid),
                        "meaning": "wind inflow fetch, not wave fetch",
                    },
                    "terrain": {
                        "horizon_median_deg": _quantile(angles, 0.5),
                        "horizon_p90_deg": _quantile(angles, 0.9),
                    },
                    "roughness": {
                        "index_median": _quantile(
                            [r["roughness"]["index"] for r in valid], 0.5
                        ),
                        "possible_double_counting": any(
                            r["roughness"]["possible_double_counting"] for r in valid
                        ),
                    },
                    "rays": rays,
                },
                "quality": {
                    "valid_rays": len(valid),
                    "required_rays": 6,
                    "total_rays": 9,
                    "algorithm_version": SHADOW_VERSION,
                    "resampling": {
                        "water": "nearest/area fraction",
                        "landcover": "nearest/area fraction",
                        "elevation": "continuous",
                    },
                },
            }
        )
    return out


def find_water_anchor(grid: MetricRaster, tolerance_m: float = 250) -> dict:
    r, c = grid.center
    if grid.water[r, c] in (1, 2, 3):
        return {
            "row": r,
            "col": c,
            "distance_m": 0.0,
            "bearing_deg": None,
            "reason": "original coordinate is water",
            "status": "valid",
        }
    radius = math.ceil(tolerance_m / grid.pixel_m)
    candidates = []
    for rr in range(max(0, r - radius), min(grid.water.shape[0], r + radius + 1)):
        for cc in range(max(0, c - radius), min(grid.water.shape[1], c + radius + 1)):
            if grid.water[rr, cc] in (1, 2, 3):
                distance = math.hypot(rr - r, cc - c) * grid.pixel_m
                if distance <= tolerance_m:
                    candidates.append((distance, rr, cc))
    if not candidates:
        return {"status": "unavailable", "reason": "no water within coastal tolerance"}
    distance, rr, cc = min(candidates)
    bearing = (math.degrees(math.atan2(cc - c, r - rr)) + 360) % 360
    return {
        "row": rr,
        "col": cc,
        "distance_m": distance,
        "bearing_deg": bearing,
        "reason": "nearest water within tolerance",
        "status": "degraded",
    }


def coastline_normals(grid: MetricRaster, water_type: int) -> dict:
    if water_type == 3:
        return {
            "type": "river_not_applicable",
            "status": "not_applicable",
            "scales": {},
        }
    boundary = []
    mask = grid.water == water_type
    for r, c in zip(*np.where(mask)):
        if any(
            0 <= rr < mask.shape[0] and 0 <= cc < mask.shape[1] and not mask[rr, cc]
            for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
        ):
            boundary.append((r, c))
    result = {}
    cr, cc = grid.center
    for scale in (500, 2000, 5000):
        points = np.array(
            [
                (c - cc, cr - r)
                for r, c in boundary
                if math.hypot(r - cr, c - cc) * grid.pixel_m <= scale
            ],
            dtype=float,
        )
        if len(points) < 3:
            result[str(scale)] = {"status": "unavailable"}
            continue
        covariance = np.cov(points.T)
        values, vectors = np.linalg.eigh(covariance)
        tangent = vectors[:, np.argmax(values)]
        tangent_deg = (math.degrees(math.atan2(tangent[0], tangent[1])) + 360) % 180
        normal_a = (tangent_deg + 90) % 360
        stability = float(1 - values.min() / max(values.max(), 1e-9))
        result[str(scale)] = {
            "status": "valid" if stability > 0.5 else "conflicted",
            "tangent_deg": tangent_deg,
            "normal_candidates_deg": [normal_a, (normal_a + 180) % 360],
            "stability": stability,
            "coast_distance_m": float(
                min(math.hypot(r - cr, c - cc) for r, c in boundary) * grid.pixel_m
            ),
        }
    return {
        "type": "coast"
        if water_type == 1
        else "lake_shore"
        if water_type == 2
        else "lagoon_shore",
        "status": "valid"
        if any(v.get("status") == "valid" for v in result.values())
        else "conflicted",
        "scales": result,
    }


def input_hash(spot_id, coordinate_hash, dataset_versions, asset_hashes) -> str:
    raw = "|".join(
        [
            str(spot_id),
            coordinate_hash,
            SHADOW_VERSION,
            *sorted(dataset_versions),
            *sorted(asset_hashes),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()
