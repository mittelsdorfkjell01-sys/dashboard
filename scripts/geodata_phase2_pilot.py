"""Run the corrected five-spot phase-2 pilot entirely from the local cache."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from geoalchemy2.shape import to_shape
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.forecast.geodata import analysis_crs
from app.forecast.shadow import (
    MetricRaster,
    SHADOW_VERSION,
    analyze_sectors,
    coastline_normals,
    find_water_anchor,
)
from app.models import Spot

NAMES = ("Baleal", "Brouwersdam", "Mundaka", "Lo Stagnone", "Pozo Izquierdo")
CACHE = Path("data/geodata-cache")
DERIVED = CACHE / "derived-shadow-corrected"
REPORT = Path("reports/geodata-phase2-analysis.json")
WARM_REPORT = Path("reports/geodata-phase2-warm.json")
PIXEL_M = 600.0
SIZE = 335
CENTER = (SIZE // 2, SIZE // 2)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def scientific_hash(sectors: list[dict]) -> str:
    encoded = json.dumps(
        sectors, sort_keys=True, separators=(",", ":"), allow_nan=False,
        default=json_default,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def old_landcover(name: str) -> np.ndarray:
    old = json.loads(REPORT.read_text(encoding="utf-8"))
    item = next(spot for spot in old["spots"] if spot["name"] == name)
    with np.load(item["derived_grid"]["path"]) as saved:
        landcover = saved["landcover"].copy()
    if landcover.shape != (SIZE, SIZE):
        raise RuntimeError(f"unexpected cached WorldCover grid for {name}")
    return landcover


def build_grid(name: str, lat: float, lon: float) -> tuple[Path, list[dict]]:
    crs = analysis_crs(lat, lon)
    cx, cy = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(lon, lat)
    transform = from_origin(
        cx - (CENTER[1] + 0.5) * PIXEL_M,
        cy + (CENTER[0] + 0.5) * PIXEL_M,
        PIXEL_M,
        PIXEL_M,
    )
    water = np.ones((SIZE, SIZE), dtype=np.uint8)  # catalogue-confirmed gaps are ocean
    elevation = np.zeros((SIZE, SIZE), dtype=np.float32)
    sources: list[dict] = []
    root = CACHE / "cop-dem-glo30" / "2024_1"
    for product in sorted(path for path in root.iterdir() if path.is_dir()):
        used_layers = []
        for layer, destination, nodata, resampling in (
            ("WBM", water, 255, Resampling.nearest),
            ("DEM", elevation, np.nan, Resampling.bilinear),
        ):
            path = product / f"{layer}.tif"
            if not path.exists():
                continue
            temporary = np.full((SIZE, SIZE), nodata, dtype=destination.dtype)
            with rasterio.open(path) as source:
                reproject(
                    source=rasterio.band(source, 1),
                    destination=temporary,
                    src_transform=source.transform,
                    src_crs=source.crs,
                    src_nodata=source.nodata,
                    dst_transform=transform,
                    dst_crs=crs,
                    dst_nodata=nodata,
                    resampling=resampling,
                )
            valid = temporary != 255 if layer == "WBM" else np.isfinite(temporary)
            if valid.any():
                destination[valid] = temporary[valid]
                used_layers.append({"layer": layer, "sha256": sha256(path)})
        if used_layers:
            sources.append({"product_id": product.name, "layers": used_layers})
    if not sources:
        raise RuntimeError(f"no cached DEM products intersect {name}")
    landcover = old_landcover(name)
    target = DERIVED / name.lower().replace(" ", "-") / "grid.npz"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".part.npz")
    np.savez_compressed(
        temporary,
        water=water,
        landcover=landcover,
        elevation_m=elevation,
        pixel_m=np.array(PIXEL_M),
        center=np.array(CENTER),
    )
    temporary.replace(target)
    return target, sources


def analyze_grid(path: Path) -> tuple[list[dict], dict, dict]:
    with np.load(path) as saved:
        grid = MetricRaster(
            saved["water"], saved["landcover"], saved["elevation_m"],
            float(saved["pixel_m"]), tuple(int(v) for v in saved["center"]),
        )
    sectors = analyze_sectors(grid)
    anchor = find_water_anchor(grid)
    r, c = grid.center
    water_type = int(grid.water[r, c])
    coast = coastline_normals(grid, water_type if water_type in (1, 2, 3) else 1)
    return sectors, anchor, coast


def profile_class(sectors: list[dict]) -> str:
    valid = sum(item["status"] == "valid" for item in sectors)
    if valid == 16:
        return "A"
    if valid >= 14:
        return "B"
    if valid >= 12:
        return "C"
    return "D"


def main() -> None:
    previous = json.loads(REPORT.read_text(encoding="utf-8"))
    old_grids = {item["name"]: item["derived_grid"]["path"] for item in previous["spots"]}
    # Preserve references while build_grid reads the old WorldCover-derived arrays.
    for item in previous["spots"]:
        item["derived_grid"]["path"] = old_grids[item["name"]]
    spots_out = []
    with SessionLocal() as db:
        spots = {s.name: s for s in db.scalars(select(Spot).where(Spot.name.in_(NAMES), Spot.status == "published")).all()}
        if len(spots) != 5:
            raise RuntimeError("pilot requires exactly five published spots")
        for name in NAMES:
            point = to_shape(spots[name].location)
            grid_path, sources = build_grid(name, point.y, point.x)
            sectors, anchor, coast = analyze_grid(grid_path)
            counts = {state: sum(s["status"] == state for s in sectors) for state in ("valid", "degraded", "unavailable")}
            klass = profile_class(sectors)
            spots_out.append({
                "spot_id": str(spots[name].id), "name": name,
                "coordinates": [point.y, point.x], "analysis_crs": analysis_crs(point.y, point.x),
                "products": sources,
                "derived_grid": {"path": str(grid_path.resolve()), "sha256": sha256(grid_path), "size_bytes": grid_path.stat().st_size, "shape": [SIZE, SIZE], "pixel_m": PIXEL_M},
                "water_anchor": anchor, "coastline": coast, "sectors": sectors,
                "sector_counts": counts, "profile_class": klass,
                "scientific_hash": scientific_hash(sectors),
                "status": "accepted" if klass != "D" else "rejected_quality",
            })
    status = "accepted" if all(s["profile_class"] != "D" for s in spots_out) else "rejected_quality"
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "algorithm": SHADOW_VERSION, "status": status, "network_requests": 0, "spots": spots_out}
    REPORT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=json_default),
        encoding="utf-8",
    )

    warm = []
    for item in spots_out:
        sectors, _, _ = analyze_grid(Path(item["derived_grid"]["path"]))
        warm.append({"name": item["name"], "grid_hash": sha256(Path(item["derived_grid"]["path"])), "scientific_hash": scientific_hash(sectors), "identical": scientific_hash(sectors) == item["scientific_hash"]})
    warm_report = {"generated_at": datetime.now(timezone.utc).isoformat(), "status": "accepted" if status == "accepted" and all(s["identical"] for s in warm) else "rejected", "network_requests": 0, "network_fallback": False, "identical": all(s["identical"] for s in warm), "spots": warm}
    WARM_REPORT.write_text(json.dumps(warm_report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": status, "spots": [{"name": s["name"], "class": s["profile_class"], **s["sector_counts"]} for s in spots_out], "warm_identical": warm_report["identical"]}))


if __name__ == "__main__":
    main()
