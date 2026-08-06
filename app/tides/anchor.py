from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnchorCandidate:
    lat: float
    lon: float
    distance_m: float
    extrapolated: bool
    warnings: tuple[str, ...]


class FesMaskAnchorSelector:
    """Select a nearby FES ocean pixel and reject straight-line land barriers.

    The FES mask supplies the authoritative model availability (0 native,
    1 extrapolated, 2 land, 3 lake). A Natural Earth land polygon additionally
    prevents crossing a peninsula or island simply because a pixel is close.
    """

    def __init__(self, mask_file: str, land_geojson: str):
        try:
            import netCDF4
            from shapely.geometry import LineString, Point, shape
            from shapely.ops import unary_union
        except ImportError as exc:
            raise RuntimeError("Tide-Worker benötigt netCDF4 und shapely") from exc
        mask_path, land_path = Path(mask_file), Path(land_geojson)
        if not mask_path.is_file() or not land_path.is_file():
            raise RuntimeError("FES-Maske oder Land-GeoJSON fehlt")
        self._dataset = netCDF4.Dataset(mask_path, "r")
        self._mask = self._dataset.variables["mask"]
        self._lats = self._coordinate("lat", "latitude")
        self._lons = self._coordinate("lon", "longitude")
        features = json.loads(land_path.read_text(encoding="utf-8"))["features"]
        self._land = unary_union([shape(item["geometry"]) for item in features])
        self._LineString = LineString
        self._Point = Point

    def _coordinate(self, *names: str):
        for name in names:
            if name in self._dataset.variables:
                return self._dataset.variables[name][:]
        raise RuntimeError(f"Koordinatenvariable fehlt: {names}")

    def select(self, lat: float, lon: float, *, max_distance_km: float) -> AnchorCandidate | None:
        import numpy as np

        model_lon = lon % 360
        lat_index = int(np.abs(self._lats - lat).argmin())
        lon_index = int(np.abs(self._lons - model_lon).argmin())
        lat_step = max(1e-9, float(abs(self._lats[min(lat_index + 1, len(self._lats) - 1)] - self._lats[lat_index])))
        lon_step = max(1e-9, float(abs(self._lons[min(lon_index + 1, len(self._lons) - 1)] - self._lons[lon_index])))
        radius = int(math.ceil(max_distance_km / min(lat_step * 111, lon_step * 111 * max(0.2, math.cos(math.radians(lat))))))
        candidates: list[AnchorCandidate] = []
        for y in range(max(0, lat_index - radius), min(len(self._lats), lat_index + radius + 1)):
            for x in range(max(0, lon_index - radius), min(len(self._lons), lon_index + radius + 1)):
                mask = int(self._mask[y, x])
                if mask not in (0, 1):
                    continue
                c_lat, c_lon_model = float(self._lats[y]), float(self._lons[x])
                c_lon = c_lon_model - 360 if c_lon_model > 180 else c_lon_model
                distance = _haversine_m(lat, lon, c_lat, c_lon)
                if distance > max_distance_km * 1000:
                    continue
                if self._crosses_land(lat, lon, c_lat, c_lon):
                    continue
                warnings = ("Modellpunkt liegt im extrapolierten Küstenraster.",) if mask == 1 else ()
                candidates.append(AnchorCandidate(c_lat, c_lon, distance, mask == 1, warnings))
        return min(candidates, key=lambda item: (item.extrapolated, item.distance_m), default=None)

    def validate(self, lat: float, lon: float) -> tuple[bool, bool]:
        import numpy as np

        y = int(np.abs(self._lats - lat).argmin())
        x = int(np.abs(self._lons - (lon % 360)).argmin())
        value = int(self._mask[y, x])
        return value in (0, 1), value == 1

    def _crosses_land(self, lat1: float, lon1: float, lat2: float, lon2: float) -> bool:
        line = self._LineString([(lon1, lat1), (lon2, lat2)])
        # The source coordinate is often exactly on the beach. Ignore a small
        # start area, but reject every land crossing after leaving the spot.
        relevant = line.difference(self._Point(lon1, lat1).buffer(0.0015))
        return not relevant.is_empty and relevant.intersects(self._land)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
