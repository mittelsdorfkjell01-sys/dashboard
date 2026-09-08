"""Global Wind Atlas sector-factor producer (offline).

Computes, per 30-degree sector, ``speed_factor = mean_GWA / mean_reference`` and
writes 12 versioned rows into ``spot_weather_sectors``. It NEVER fetches a raster
on a request path and NEVER invents a factor: without a mounted GWA raster, on an
ocean/NoData cell, or on a failed reference fetch it returns a clear status and
neutral (1.0) factors. Station wind is not involved.

Raster and reference access sit behind injectable adapters; the core
``compute_gwa_sectors`` is a pure function so the factor arithmetic is fully
testable without any IO.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Protocol

from app.weather.physics.limits import clamp

SECTOR_COUNT = 12
SECTOR_WIDTH = 30.0
FACTOR_LOW, FACTOR_HIGH = 0.50, 1.60
# Above this GLO-30 slope gradient the WAsP linear flow model is invalid
# (flow separation); flag the sector low-confidence instead of trusting it.
STEEP_SLOPE_GRADIENT = 0.30
REFERENCE_WINDOW = (2008, 2017)
GWA_VERSION = "GWA-3.0"

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
    """Mean wind speed per 30-degree from-sector from ERA5 u/v components.

    Twelve GWA-aligned sectors (not the 16-sector default in ``bins.py``). Empty
    sectors return NaN, which the factor step treats as low-confidence neutral.
    """
    import numpy as np

    u = np.asarray(u10, dtype="float64")
    v = np.asarray(v10, dtype="float64")
    speed = np.hypot(u, v)
    direction = np.degrees(np.arctan2(-u, -v)) % 360.0  # meteorological "from"
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

    def read(self, lat: float, lon: float) -> list[WeibullSector] | None:
        """12 (A, k) sectors at the point, or None on an ocean/NoData cell."""


class ReferenceWindSource(Protocol):
    def sector_mean_speeds(self, lat: float, lon: float, window: tuple[int, int]) -> list[float] | None:
        """12 mean wind speeds (m/s), or None if the reference fetch failed."""


class SlopeProvider(Protocol):
    def sector_gradients(self, lat: float, lon: float) -> list[float] | None:
        """12 GLO-30 slope gradients, or None if unavailable."""


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


def _neutral_sectors() -> list[SectorFactor]:
    out = []
    for index in range(SECTOR_COUNT):
        start, end = sector_bounds(index)
        out.append(SectorFactor(index, start, end, 1.0, 0.0, "ok", False))
    return out


def compute_gwa_sectors(
    lat: float,
    lon: float,
    *,
    gwa_reader: GwaRasterReader,
    reference: ReferenceWindSource,
    window: tuple[int, int] = REFERENCE_WINDOW,
    reference_model: str = "era5",
    slope_provider: SlopeProvider | None = None,
    grid_cell: list | None = None,
) -> GwaSectorResult:
    """Pure factor arithmetic. Missing/insufficient inputs degrade to neutral."""
    provenance = {
        "method": "gwa_over_reference", "gwa_version": GWA_VERSION,
        "reference_model": reference_model, "window": list(window), "grid_cell": grid_cell,
    }

    if not getattr(gwa_reader, "mounted", False):
        return GwaSectorResult(STATUS_NOT_MOUNTED, _neutral_sectors(), {**provenance, "status": STATUS_NOT_MOUNTED})
    weibull = gwa_reader.read(lat, lon)
    if weibull is None:
        return GwaSectorResult(STATUS_NODATA, _neutral_sectors(), {**provenance, "status": STATUS_NODATA})
    means = reference.sector_mean_speeds(lat, lon, window)
    if means is None:
        return GwaSectorResult(STATUS_REFERENCE_UNAVAILABLE, _neutral_sectors(),
                               {**provenance, "status": STATUS_REFERENCE_UNAVAILABLE})
    if len(weibull) != SECTOR_COUNT or len(means) != SECTOR_COUNT:
        raise ValueError("GWA reader and reference must each return 12 sectors")

    gradients = slope_provider.sector_gradients(lat, lon) if slope_provider is not None else None
    sectors = []
    for index in range(SECTOR_COUNT):
        start, end = sector_bounds(index)
        mean_gwa = weibull_mean(weibull[index].a, weibull[index].k)
        mean_ref = means[index]
        steep = (gradients is not None and index < len(gradients)
                 and gradients[index] is not None and gradients[index] > STEEP_SLOPE_GRADIENT)
        if not (math.isfinite(mean_gwa) and math.isfinite(mean_ref)) or mean_ref <= 0 or mean_gwa <= 0:
            # No trustworthy ratio -> stay neutral, mark low confidence.
            sectors.append(SectorFactor(index, start, end, 1.0, 0.0, "low", False))
            continue
        raw = mean_gwa / mean_ref
        factor = clamp(raw, FACTOR_LOW, FACTOR_HIGH)
        sectors.append(SectorFactor(
            index, start, end, round(factor, 4), 0.0,
            "low" if steep else "ok", factor != raw,
        ))
    return GwaSectorResult(STATUS_OK, sectors, {**provenance, "status": STATUS_OK})


# --- persistence -----------------------------------------------------------


def result_signature(result: GwaSectorResult) -> str:
    payload = {
        "status": result.status,
        "method": result.provenance.get("method"),
        "gwa_version": result.provenance.get("gwa_version"),
        "reference_model": result.provenance.get("reference_model"),
        "window": result.provenance.get("window"),
        "grid_cell": result.provenance.get("grid_cell"),
        "sectors": [[s.index, s.speed_factor, s.confidence, s.saturated] for s in result.sectors],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _sector_note(result: GwaSectorResult, sector: SectorFactor, signature: str) -> str:
    return json.dumps({
        "method": result.provenance["method"], "gwa_version": result.provenance["gwa_version"],
        "reference_model": result.provenance["reference_model"], "window": result.provenance["window"],
        "grid_cell": result.provenance["grid_cell"], "saturated": sector.saturated,
        "confidence": sector.confidence, "sig": signature,
    }, separators=(",", ":"))[:500]


def persist_gwa_sectors(db, spot_id, result: GwaSectorResult, *, now=None) -> dict:
    """Write 12 versioned sector rows; idempotent for an unchanged result.

    ``reference_unavailable`` never writes. A profile is created if missing.
    """
    from sqlalchemy import select

    from app.models import SpotWeatherProfile, SpotWeatherSector

    if result.status == STATUS_REFERENCE_UNAVAILABLE:
        return {"status": result.status, "written": 0, "version": None, "reason": "no_write"}

    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id))
    if profile is None:
        profile = SpotWeatherProfile(spot_id=spot_id)
        db.add(profile)
        db.flush()

    existing = db.scalars(
        select(SpotWeatherSector).where(SpotWeatherSector.profile_id == profile.id)
    ).all()
    latest_version = max((sector.version for sector in existing), default=0)
    signature = result_signature(result)

    if latest_version:
        latest_rows = [row for row in existing if row.version == latest_version]
        stored_sig = next((_note_sig(row.note) for row in latest_rows if row.note), None)
        if stored_sig == signature:
            return {"status": result.status, "written": 0, "version": latest_version, "reason": "idempotent"}

    version = latest_version + 1
    for sector in result.sectors:
        db.add(SpotWeatherSector(
            profile_id=profile.id, start_deg=sector.start_deg, end_deg=sector.end_deg,
            speed_factor=sector.speed_factor, direction_offset_deg=sector.direction_offset_deg,
            version=version, enabled=result.enabled, note=_sector_note(result, sector, signature),
        ))
    db.commit()
    return {"status": result.status, "written": SECTOR_COUNT, "version": version, "reason": "written"}


def _note_sig(note: str | None) -> str | None:
    if not note:
        return None
    try:
        return json.loads(note).get("sig")
    except (ValueError, TypeError):
        return None


# --- concrete adapters (thin IO; core stays pure and tested) ---------------


class Era5ReferenceSource:
    """ERA5 hourly wind via OpenMeteoHistoryClient, binned into 12 sectors."""

    def __init__(self, client=None) -> None:
        self._client = client

    def sector_mean_speeds(self, lat: float, lon: float, window: tuple[int, int]) -> list[float] | None:
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
        return bin_mean_speeds(u10, v10)


class MountedGwaRasterReader:
    """Reads per-sector Weibull A/k from a mounted GWA v3 raster export.

    Expected layout under ``GWA_RASTER_DIR``: single-band EPSG:4326 GeoTIFFs
    ``gwa3_A_{deg}.tif`` and ``gwa3_k_{deg}.tif`` for deg in 0,30,...,330.
    rasterio is imported lazily so the neutral (unmounted) path needs no
    geospatial stack. Never used on a request path.
    """

    def __init__(self, raster_dir: str | None = None) -> None:
        if raster_dir is None:
            from app.config import get_settings

            raster_dir = get_settings().gwa_raster_dir
        self._dir = raster_dir

    @property
    def mounted(self) -> bool:
        return bool(self._dir)

    def read(self, lat: float, lon: float) -> list[WeibullSector] | None:
        if not self._dir:
            return None
        import os

        import rasterio

        sectors: list[WeibullSector] = []
        for index in range(SECTOR_COUNT):
            deg = int(index * SECTOR_WIDTH)
            a_path = os.path.join(self._dir, f"gwa3_A_{deg}.tif")
            k_path = os.path.join(self._dir, f"gwa3_k_{deg}.tif")
            a = self._sample(rasterio, a_path, lon, lat)
            k = self._sample(rasterio, k_path, lon, lat)
            if a is None or k is None:  # ocean / NoData / missing tile
                return None
            sectors.append(WeibullSector(a=a, k=k))
        return sectors

    @staticmethod
    def _sample(rasterio, path: str, lon: float, lat: float) -> float | None:
        try:
            with rasterio.open(path) as dataset:
                value = next(dataset.sample([(lon, lat)]))[0]
                nodata = dataset.nodata
        except Exception:
            return None
        if value is None or (nodata is not None and value == nodata) or not math.isfinite(float(value)):
            return None
        return float(value)


def build_spot_sectors(db, spot, *, gwa_reader=None, reference=None,
                       window: tuple[int, int] = REFERENCE_WINDOW, reference_model: str = "era5") -> dict:
    """Compute and persist GWA sector factors for one spot (offline job)."""
    from app.era5.grid import resolve_grid_cell
    from app.live import service as live_service

    lat, lon = live_service._spot_coords(spot)
    grid_cell = resolve_grid_cell(lat, lon)["wind"]
    reader = gwa_reader or MountedGwaRasterReader()
    ref = reference or Era5ReferenceSource()
    result = compute_gwa_sectors(
        lat, lon, gwa_reader=reader, reference=ref,
        window=window, reference_model=reference_model, grid_cell=grid_cell,
    )
    outcome = persist_gwa_sectors(db, spot.id, result)
    return {"spot_id": str(spot.id), **outcome}
