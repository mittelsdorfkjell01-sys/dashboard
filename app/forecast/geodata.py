"""Official DEM/land-cover adapters and descriptive phase-1 profile analysis."""

from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
from pathlib import Path
import hashlib

from app.forecast.geodata_catalog import GEODATASETS

WORLDCOVER_CLASSES = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse",
    70: "snow_ice",
    80: "permanent_water",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_lichen",
}
WATER_CLASSES = {0: "land", 1: "ocean", 2: "lake", 3: "river"}


def tile_origin(value: float, size: int) -> int:
    return math.floor(value / size) * size


def tile_code(lat: float, lon: float, size: int = 3) -> str:
    south, west = tile_origin(lat, size), tile_origin(lon, size)
    return f"{'N' if south >= 0 else 'S'}{abs(south):02d}{'E' if west >= 0 else 'W'}{abs(west):03d}"


def analysis_crs(lat: float, lon: float) -> str:
    if lat >= 84:
        return "EPSG:3413"
    if lat <= -80:
        return "EPSG:3031"
    zone = min(60, max(1, int((lon + 180) // 6) + 1))
    return f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"


class WorldCoverAdapter:
    dataset = GEODATASETS["worldcover-2021"]

    @staticmethod
    def tile(lat: float, lon: float) -> str:
        return tile_code(lat, lon, 3)

    @classmethod
    def url(cls, lat: float, lon: float, layer: str = "Map") -> str:
        if layer not in {"Map", "InputQuality"}:
            raise ValueError("unknown WorldCover layer")
        tile = cls.tile(lat, lon)
        folder = "map" if layer == "Map" else "inputquality"
        return f"{cls.dataset.base_url}/{folder}/ESA_WorldCover_10m_2021_v200_{tile}_{layer}.tif"

    @staticmethod
    def summarize_rings(
        classes: np.ndarray, distances_m: np.ndarray, valid: np.ndarray | None = None
    ) -> dict:
        if classes.shape != distances_m.shape:
            raise ValueError("class and distance grids must match")
        valid = (classes != 0) if valid is None else valid & (classes != 0)
        rings = ((0, 250), (250, 2000), (2000, 5000))
        output = {}
        for low, high in rings:
            mask = valid & (distances_m >= low) & (distances_m < high)
            count = int(mask.sum())
            shares = {
                name: float((classes[mask] == code).sum() / count) if count else 0.0
                for code, name in WORLDCOVER_CLASSES.items()
            }
            output[f"{low}-{high}m"] = {
                "original": {
                    str(code): shares[name] for code, name in WORLDCOVER_CLASSES.items()
                },
                "groups": shares,
                "coverage": float(
                    count / max(1, ((distances_m >= low) & (distances_m < high)).sum())
                ),
            }
        return output

    @classmethod
    def analyze_remote(
        cls, lat: float, lon: float, *, cache_root: str | Path, radius_m: int = 5000
    ) -> tuple[dict, dict]:
        """Read only COG blocks intersecting the 5 km window, then cache the derived window."""
        import rasterio
        from pyproj import Transformer
        from rasterio.windows import Window

        tile = cls.tile(lat, lon)
        target = (
            Path(cache_root)
            / cls.dataset.key
            / cls.dataset.version
            / f"{tile}-{lat:.5f}-{lon:.5f}-r{radius_m}.npz"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        cache_hit = target.exists()
        if cache_hit:
            with np.load(target) as saved:
                classes = saved["classes"]
                xs = saved["xs"]
                ys = saved["ys"]
        else:
            with rasterio.open(cls.url(lat, lon)) as source:
                if str(source.crs) != "EPSG:4326" or source.nodata != 0:
                    raise ValueError("unexpected WorldCover CRS or NoData")
                row, col = source.index(lon, lat)
                pixels = 510  # >5 km at equator; metric crop below is authoritative.
                window = Window(
                    col - pixels, row - pixels, pixels * 2 + 1, pixels * 2 + 1
                ).intersection(Window(0, 0, source.width, source.height))
                classes = source.read(1, window=window, boundless=False)
                transform = source.window_transform(window)
                rows, cols = np.indices(classes.shape)
                xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
                xs, ys = np.asarray(xs), np.asarray(ys)
            temporary = target.with_suffix(".part.npz")
            np.savez_compressed(temporary, classes=classes, xs=xs, ys=ys)
            temporary.replace(target)
        crs = analysis_crs(lat, lon)
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        mx, my = transformer.transform(xs, ys)
        cx, cy = transformer.transform(lon, lat)
        distances = np.hypot(np.asarray(mx) - cx, np.asarray(my) - cy)
        metrics = cls.summarize_rings(classes, distances, valid=distances <= radius_m)
        checksum = hashlib.sha256(target.read_bytes()).hexdigest()
        return metrics, {
            "tile": tile,
            "path": str(target),
            "checksum": checksum,
            "size_bytes": target.stat().st_size,
            "cache_hit": cache_hit,
            "analysis_crs": crs,
            "coverage": float(
                ((classes != 0) & (distances <= radius_m)).sum()
                / max(1, (distances <= radius_m).sum())
            ),
        }


class CopernicusDemAdapter:
    dataset = GEODATASETS["cop-dem-glo30"]

    @staticmethod
    def tile(lat: float, lon: float) -> str:
        return tile_code(lat, lon, 1)

    @staticmethod
    def validate_metadata(
        *, crs: str, vertical_datum: str, layers: set[str]
    ) -> list[str]:
        if crs != "EPSG:4326":
            raise ValueError("Copernicus DEM DGED must be EPSG:4326")
        if vertical_datum != "EPSG:3855":
            raise ValueError("Copernicus DEM must explicitly use EGM2008/EPSG:3855")
        return [] if {"WBM", "HEM"} <= layers else ["quality_layer_missing"]

    @staticmethod
    def summarize(
        elevation: np.ndarray, water: np.ndarray, *, pixel_m: float = 30
    ) -> dict:
        valid = np.isfinite(elevation)
        if not valid.any():
            raise ValueError("DEM window contains no valid elevation")
        centre = tuple(s // 2 for s in elevation.shape)
        wbm = int(water[centre]) if int(water[centre]) in WATER_CLASSES else -1
        water_mask = np.isin(water, [1, 2, 3])
        land_mask = water == 0
        yy, xx = np.indices(elevation.shape)
        distance = np.hypot(yy - centre[0], xx - centre[1]) * pixel_m
        nearest_water = float(distance[water_mask].min()) if water_mask.any() else None
        nearest_land = float(distance[land_mask].min()) if land_mask.any() else None
        gy, gx = np.gradient(
            np.where(valid, elevation, np.nanmedian(elevation[valid])), pixel_m
        )
        slope = math.degrees(math.atan(float(np.hypot(gy[centre], gx[centre]))))
        aspect = (
            math.degrees(math.atan2(float(gx[centre]), -float(gy[centre]))) + 360
        ) % 360
        values = elevation[valid]
        return {
            "target_elevation_m": float(elevation[centre]),
            "environment_elevation_m": float(np.median(values)),
            "elevation_quantiles_m": [
                float(x) for x in np.quantile(values, [0.1, 0.5, 0.9])
            ],
            "elevation_std_m": float(np.std(values)),
            "relative_min_m": float(values.min() - elevation[centre]),
            "relative_max_m": float(values.max() - elevation[centre]),
            "slope_deg": slope,
            "aspect_deg": aspect,
            "ruggedness_m": float(
                np.percentile(values, 90) - np.percentile(values, 10)
            ),
            "surface": WATER_CLASSES.get(wbm, "coastal_ambiguous"),
            "distance_to_water_m": nearest_water,
            "distance_to_land_m": nearest_land,
            "nodata_fraction": float(1 - valid.mean()),
        }


@dataclass(frozen=True)
class Phase2Sector:
    index: int
    center_deg: float
    width_deg: float = 22.5
    # Fetch, coastline and roughness are intentionally absent until calculated.


PHASE2_SECTORS = tuple(Phase2Sector(i, i * 22.5) for i in range(16))
