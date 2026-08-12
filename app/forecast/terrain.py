"""Small local SRTM adapter; never downloads global rasters on request paths."""

from __future__ import annotations
import math
from pathlib import Path
import numpy as np


class TerrainUnavailable(RuntimeError):
    pass


def tile_name(lat: float, lon: float) -> str:
    south = math.floor(lat)
    west = math.floor(lon)
    return f"{'N' if south >= 0 else 'S'}{abs(south):02d}{'E' if west >= 0 else 'W'}{abs(west):03d}.hgt"


class SrtmTerrain:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _tile(self, lat: float, lon: float):
        path = self.root / tile_name(lat, lon)
        if not path.exists():
            raise TerrainUnavailable(f"missing SRTM tile {path.name}")
        size = path.stat().st_size
        side = round(math.sqrt(size / 2))
        if side * side * 2 != size or side not in (1201, 3601):
            raise TerrainUnavailable("invalid SRTM tile dimensions")
        return np.memmap(path, dtype=">i2", mode="r", shape=(side, side)), side

    def elevation(self, lat: float, lon: float) -> float | None:
        data, side = self._tile(lat, lon)
        south = math.floor(lat)
        west = math.floor(lon)
        row = round((1 - (lat - south)) * (side - 1))
        col = round((lon - west) * (side - 1))
        value = int(data[row, col])
        return None if value <= -32768 else float(value)

    def sectors(
        self, lat: float, lon: float, count: int = 16, radius_km: float = 10
    ) -> list[dict]:
        origin = self.elevation(lat, lon)
        out = []
        for index in range(count):
            bearing = index * 360 / count
            samples = []
            for distance in (1, 2, 5, 10):
                rad = math.radians(bearing)
                dy = math.cos(rad) * distance / 111
                dx = (
                    math.sin(rad)
                    * distance
                    / (111 * max(0.2, math.cos(math.radians(lat))))
                )
                try:
                    value = self.elevation(lat + dy, lon + dx)
                except TerrainUnavailable:
                    value = None
                if value is not None:
                    samples.append(value)
            maximum = max(samples) if samples else None
            shelter = (
                None
                if maximum is None or origin is None
                else max(0, min(1, (maximum - origin) / 500))
            )
            out.append(
                {
                    "start_deg": bearing - 360 / count / 2,
                    "end_deg": bearing + 360 / count / 2,
                    "mean_elevation_m": round(sum(samples) / len(samples), 1)
                    if samples
                    else None,
                    "max_elevation_m": maximum,
                    "terrain_shelter": round(shelter, 3)
                    if shelter is not None
                    else None,
                    "data_quality": "complete" if len(samples) == 4 else "partial",
                }
            )
        return out
