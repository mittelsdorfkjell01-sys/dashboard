"""Global Wind Atlas omnidirectional bias factor (WP3-A).

The Global Wind Atlas publishes no per-sector A/k GeoTIFFs — only *combined*
(all-sector) layers. So this produces ONE omnidirectional factor per spot,
``C = mean_GWA@10m / mean_ERA5@10m``, clamped to [0.50, 1.60], and writes it to
all 12 sectors with ``direction_offset_deg = 0``. Directional resolution (cape
vs. bay, onshore vs. offshore) comes later from WP5/WAsP, which overrides
individual sectors at a higher version. Until then this is honestly labelled
omnidirectional, never as direction-resolved.

The compute is pure behind injectable adapters; the reader/reference do the IO.
Without a mounted raster the result is neutral with a clear status — never an
invented factor. Persistence (candidate, enabled=False) is owned by
``app/forecast/sector_runner.py``; this module only computes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from app.weather.physics.limits import clamp

SECTOR_COUNT = 12
SECTOR_WIDTH = 30.0
FACTOR_LOW, FACTOR_HIGH = 0.50, 1.60
REFERENCE_WINDOW = (2008, 2017)
GWA_VERSION = "GWA-3.0"
REQUIRED_HEIGHT_M = 10

WIND_SPEED_VARIABLE = "wind-speed"
WEIBULL_A_VARIABLE = "combined-Weibull-A"
WEIBULL_K_VARIABLE = "combined-Weibull-k"
DEFAULT_FILENAME_TEMPLATE = "gwa_{variable}_{height}.tif"

STATUS_OK = "ok"
STATUS_NOT_MOUNTED = "gwa_not_mounted"
STATUS_NODATA = "gwa_nodata"
STATUS_REFERENCE_UNAVAILABLE = "reference_unavailable"


def sector_bounds(index: int) -> tuple[float, float]:
    start = (index * SECTOR_WIDTH) % 360.0
    return start, (start + SECTOR_WIDTH) % 360.0


def weibull_mean(a: float, k: float) -> float:
    """Mean wind speed of a Weibull(A, k): ``A * Gamma(1 + 1/k)``."""
    if not (a > 0 and k > 0):
        return float("nan")
    return a * math.gamma(1.0 + 1.0 / k)


def bin_mean_speeds(u10, v10) -> list[float]:
    """Mean wind speed per 30-degree from-sector from ERA5 u/v (kept for WP5)."""
    import numpy as np

    u = np.asarray(u10, dtype="float64")
    v = np.asarray(v10, dtype="float64")
    speed = np.hypot(u, v)
    direction = np.degrees(np.arctan2(-u, -v)) % 360.0
    finite = np.isfinite(speed) & np.isfinite(direction)
    index = (direction // SECTOR_WIDTH).astype("int64") % SECTOR_COUNT
    means = []
    for sector in range(SECTOR_COUNT):
        selected = finite & (index == sector)
        means.append(float(speed[selected].mean()) if bool(selected.any()) else float("nan"))
    return means


@dataclass(frozen=True)
class WeibullSector:
    a: float  # Weibull scale A @10 m
    k: float  # Weibull shape k


class GwaRasterReader(Protocol):
    mounted: bool

    def read(self, lat: float, lon: float) -> float | None:
        """Mean GWA wind speed (m/s) @10 m at the point, or None on NoData/ocean."""


class ReferenceWindSource(Protocol):
    def mean_speed(self, lat: float, lon: float, window: tuple[int, int]) -> float | None:
        """All-sector mean reference wind speed (m/s) @10 m, or None if unavailable."""


@dataclass(frozen=True)
class SectorFactor:
    index: int
    start_deg: float
    end_deg: float
    speed_factor: float
    direction_offset_deg: float
    confidence: str  # "ok" | "low"
    saturated: bool


@dataclass(frozen=True)
class GwaSectorResult:
    status: str
    sectors: list[SectorFactor]
    provenance: dict

    @property
    def enabled(self) -> bool:
        return self.status == STATUS_OK


def _uniform_sectors(factor: float, confidence: str, saturated: bool) -> list[SectorFactor]:
    """The same omnidirectional factor on all 12 sectors (offset 0)."""
    out = []
    for index in range(SECTOR_COUNT):
        start, end = sector_bounds(index)
        out.append(SectorFactor(index, start, end, round(factor, 4), 0.0, confidence, saturated))
    return out


def compute_gwa_sectors(
    lat: float,
    lon: float,
    *,
    gwa_reader: GwaRasterReader,
    reference: ReferenceWindSource,
    window: tuple[int, int] = REFERENCE_WINDOW,
    reference_model: str = "era5",
    grid_cell: list | None = None,
    variable: str = WIND_SPEED_VARIABLE,
    height: int = REQUIRED_HEIGHT_M,
) -> GwaSectorResult:
    """One omnidirectional factor applied to all 12 sectors; neutral on missing data."""
    provenance = {
        "method": "gwa_over_reference_omni", "gwa_version": GWA_VERSION,
        "reference_model": reference_model, "window": list(window), "grid_cell": grid_cell,
        "variable": variable, "height": height,
    }

    if not getattr(gwa_reader, "mounted", False):
        return GwaSectorResult(STATUS_NOT_MOUNTED, _uniform_sectors(1.0, "ok", False),
                               {**provenance, "status": STATUS_NOT_MOUNTED})
    mean_gwa = gwa_reader.read(lat, lon)
    if mean_gwa is None:
        return GwaSectorResult(STATUS_NODATA, _uniform_sectors(1.0, "ok", False),
                               {**provenance, "status": STATUS_NODATA})
    mean_ref = reference.mean_speed(lat, lon, window)
    if mean_ref is None:
        return GwaSectorResult(STATUS_REFERENCE_UNAVAILABLE, _uniform_sectors(1.0, "ok", False),
                               {**provenance, "status": STATUS_REFERENCE_UNAVAILABLE})

    if not (math.isfinite(mean_gwa) and math.isfinite(mean_ref)) or mean_ref <= 0 or mean_gwa <= 0:
        # Data present but the ratio is unusable -> neutral, low confidence.
        return GwaSectorResult(STATUS_OK, _uniform_sectors(1.0, "low", False),
                               {**provenance, "status": STATUS_OK})
    raw = mean_gwa / mean_ref
    factor = clamp(raw, FACTOR_LOW, FACTOR_HIGH)
    return GwaSectorResult(STATUS_OK, _uniform_sectors(factor, "ok", factor != raw),
                           {**provenance, "status": STATUS_OK,
                            "mean_gwa": round(mean_gwa, 3), "mean_reference": round(mean_ref, 3)})


# --- concrete adapters (thin IO; compute stays pure) -----------------------


class Era5ReferenceSource:
    """All-sector ERA5 mean @10 m via OpenMeteoHistoryClient over the window."""

    def __init__(self, client=None) -> None:
        self._client = client

    def mean_speed(self, lat: float, lon: float, window: tuple[int, int]) -> float | None:
        client = self._client
        if client is None:
            from app.era5.openmeteo import OpenMeteoHistoryClient

            client = OpenMeteoHistoryClient()
        y0, y1 = window
        request = {"area": [lat, lon, lat, lon], "year": [str(year) for year in range(y0, y1 + 1)]}
        try:
            request_id = client.submit("reanalysis-era5-single-levels", request)
            if client.poll(request_id) != "completed":
                return None
            series = client.fetch_series(request_id)
        except Exception:
            return None
        u10, v10 = series.get("u10"), series.get("v10")
        if u10 is None or v10 is None:
            return None
        import numpy as np

        speed = np.hypot(np.asarray(u10, dtype="float64"), np.asarray(v10, dtype="float64"))
        finite = speed[np.isfinite(speed)]
        return float(finite.mean()) if finite.size else None


class MountedGwaRasterReader:
    """Reads one combined GWA layer at the point and enforces the 10 m height.

    Primary: the mean wind-speed layer (``gwa_wind-speed_10.tif`` by default) ->
    mean_GWA directly. Fallback: combined Weibull A & k -> A*Gamma(1+1/k). The
    filename template is configurable ({variable}/{height}); the 10 m height is
    required (GWA's default is 100 m) and a non-10 m construction is refused.
    NoData/ocean -> None (a small nearest-valid ring rescues a single masked
    coastal pixel). rasterio is lazy; never used on a request path.
    """

    def __init__(self, raster_dir: str | None = None, *, height: int = REQUIRED_HEIGHT_M,
                 filename_template: str | None = None, variable: str = WIND_SPEED_VARIABLE) -> None:
        if int(height) != REQUIRED_HEIGHT_M:
            raise ValueError(f"GWA reader requires the {REQUIRED_HEIGHT_M} m height; refusing {height} m")
        if raster_dir is None or filename_template is None:
            from app.config import get_settings

            settings = get_settings()
            raster_dir = raster_dir or settings.gwa_raster_dir
            filename_template = filename_template or settings.gwa_raster_filename_template
        self._dir = raster_dir
        self._template = filename_template or DEFAULT_FILENAME_TEMPLATE
        self._height = int(height)
        self._variable = variable
        self._open: dict = {}

    @property
    def mounted(self) -> bool:
        return bool(self._dir)

    def path_for(self, variable: str) -> str:
        import os

        return os.path.join(self._dir, self._template.format(variable=variable, height=self._height))

    def read(self, lat: float, lon: float) -> float | None:
        if not self._dir:
            return None
        primary = self._sample(self.path_for(self._variable), lon, lat)
        if primary is not None:
            return primary
        a = self._sample(self.path_for(WEIBULL_A_VARIABLE), lon, lat)
        k = self._sample(self.path_for(WEIBULL_K_VARIABLE), lon, lat)
        if a is None or k is None:
            return None
        mean = weibull_mean(a, k)
        return mean if math.isfinite(mean) else None

    def _dataset(self, path: str):
        dataset = self._open.get(path)
        if dataset is None:
            import rasterio

            dataset = rasterio.open(path)
            self._open[path] = dataset
        return dataset

    def _sample(self, path: str, lon: float, lat: float) -> float | None:
        try:
            dataset = self._dataset(path)
            nodata = dataset.nodata
            value = next(dataset.sample([(lon, lat)]))[0]
            if _valid(value, nodata):
                return float(value)
            # Nearest-valid ring (~GWA 250 m pixels) rescues a single masked pixel.
            for step in (0.0025, 0.005):
                for dlon, dlat in ((step, 0), (-step, 0), (0, step), (0, -step)):
                    neighbour = next(dataset.sample([(lon + dlon, lat + dlat)]))[0]
                    if _valid(neighbour, nodata):
                        return float(neighbour)
        except Exception:
            return None
        return None


def _valid(value, nodata) -> bool:
    if value is None:
        return False
    if nodata is not None and value == nodata:
        return False
    return bool(math.isfinite(float(value)))


# --- preflight doctor -------------------------------------------------------

# Plausible mean-value ranges per variable, to catch a grossly wrong layer
# (power-density ~50-2000, capacity-factor 0-1) mounted by mistake. Validated
# against the real GWA 10 m wind-speed tiles, where sheltered inland means sit
# around 2 m/s (Luxembourg mean ~2.1) — hence a low bound of 1.0, not 2.0. The
# height itself lives in the filename, not the value, so 10 m vs 100 m is not
# distinguished here; the filename/height check is authoritative for that.
PLAUSIBLE_RANGE = {
    WIND_SPEED_VARIABLE: (1.0, 40.0),
    WEIBULL_A_VARIABLE: (1.0, 45.0),
    WEIBULL_K_VARIABLE: (1.0, 4.0),
}


def gwa_raster_doctor(raster_dir: str | None = None, *, height: int = REQUIRED_HEIGHT_M,
                      filename_template: str | None = None) -> dict:
    """Inspect the mounted GWA raster and fail loudly on a wrong layer/height."""
    try:
        reader = MountedGwaRasterReader(raster_dir, height=height, filename_template=filename_template)
    except ValueError as exc:
        return {"ok": False, "mounted": False, "problems": [str(exc)], "files": []}
    if not reader.mounted:
        return {"ok": False, "mounted": False, "problems": ["GWA_RASTER_DIR is not set"], "files": []}

    problems: list[str] = []
    files: list[dict] = []
    checked_any = False
    for variable in (WIND_SPEED_VARIABLE, WEIBULL_A_VARIABLE, WEIBULL_K_VARIABLE):
        path = reader.path_for(variable)
        report = _inspect_file(path, variable)
        files.append(report)
        if not report["exists"]:
            continue
        checked_any = True
        if report.get("crs") != "EPSG:4326":
            problems.append(f"{path}: CRS is {report.get('crs')}, expected EPSG:4326")
        low, high = PLAUSIBLE_RANGE[variable]
        mean = report.get("mean")
        if mean is not None and not (low <= mean <= high):
            problems.append(f"{path}: mean {mean} outside plausible {variable} range {low}-{high} "
                            f"(wrong height or variable mounted?)")
    if not checked_any:
        import glob
        import os

        present = [os.path.basename(p) for p in glob.glob(os.path.join(reader._dir, "gwa_*"))]
        problems.append(f"No expected {height} m GWA layer found. Present files: {present or 'none'}")
    return {"ok": not problems, "mounted": True, "height": height, "problems": problems, "files": files}


def _inspect_file(path: str, variable: str) -> dict:
    import os

    if not os.path.exists(path):
        return {"path": path, "variable": variable, "exists": False}
    try:
        import numpy as np
        import rasterio

        with rasterio.open(path) as dataset:
            crs = str(dataset.crs)
            nodata = dataset.nodata
            array = dataset.read(1, out_shape=(min(dataset.height, 128), min(dataset.width, 128))).astype("float64")
        valid = array[np.isfinite(array)]
        if nodata is not None:
            valid = valid[valid != nodata]
        stats = ({"min": round(float(valid.min()), 3), "max": round(float(valid.max()), 3),
                  "mean": round(float(valid.mean()), 3)} if valid.size else {"min": None, "max": None, "mean": None})
        return {"path": path, "variable": variable, "exists": True, "crs": crs, "nodata": nodata, **stats}
    except Exception as exc:
        return {"path": path, "variable": variable, "exists": True, "error": f"{type(exc).__name__}: {exc}"}
