"""WP5 microscale producer: internal-boundary-layer roughness transfer.

The dominant local coastal effect is the land/sea roughness change: offshore
wind at the beach is still land-influenced (weaker), onshore wind arrives almost
at its over-water strength. This module computes a per-sector speed factor from a
two-log-profile with an internal boundary layer (IBL) growing over the upwind
fetch, and writes the result into ``spot_weather_sectors`` at a HIGHER version so
it overrides the WP3 GWA prior; the engine is unchanged (it reads select_sector).

Raster access (WorldCover roughness, GLO-30 WBM coastline/fetch, GLO-30 DEM) sits
behind an injectable surface provider; the physics is pure and fully tested.
Without the rasters mounted the producer reports ``microscale_unavailable`` and
does NOT touch the GWA rows — it never invents a factor. Orographic speed-up
(PyWAsP/WAsP) is a separate, deferred term that defaults to neutral 1.0.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Protocol

from app.forecast.geodata import WORLDCOVER_CLASSES
from app.weather.physics.limits import clamp

SECTOR_COUNT = 12
SECTOR_WIDTH = 30.0
FACTOR_LOW, FACTOR_HIGH = 0.50, 1.60
REFERENCE_HEIGHT_M = 10.0
MAX_BLENDING_HEIGHT_M = 200.0
CHARNOCK_SEA_Z0 = 0.0002  # open-sea aerodynamic roughness (m), Charnock ~light wind

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "microscale_unavailable"

# Aerodynamic roughness length z0 (m) per ESA WorldCover class. Standard
# land-cover values; water uses the Charnock sea roughness.
WORLDCOVER_Z0 = {
    "tree_cover": 0.80, "shrubland": 0.10, "grassland": 0.03, "cropland": 0.05,
    "built_up": 1.00, "bare_sparse": 0.01, "snow_ice": 0.001,
    "permanent_water": CHARNOCK_SEA_Z0, "herbaceous_wetland": 0.05,
    "mangroves": 0.50, "moss_lichen": 0.01,
}
DEFAULT_LAND_Z0 = 0.03  # grassland fallback for an unknown class

# Coarse typical surface-feature heights (m) per class, used ONLY to separate a
# GLO-30 DSM into a bare-earth DTM for the (deferred) orography term, so canopy
# and buildings are not double-counted as terrain. Not a spot measurement.
WORLDCOVER_CANOPY_M = {
    "tree_cover": 15.0, "built_up": 8.0, "mangroves": 8.0, "shrubland": 2.0,
}


def roughness_for_class(class_code) -> float:
    name = WORLDCOVER_CLASSES.get(int(class_code)) if class_code is not None else None
    return WORLDCOVER_Z0.get(name, DEFAULT_LAND_Z0)


def dtm_from_dsm(dsm_elevation_m: float, class_code) -> float:
    """Estimate bare-earth (DTM) height from a GLO-30 DSM sample.

    GLO-30 is a surface model: vegetation and buildings raise it. Subtract a
    coarse class-typical feature height so orography is not inflated by land
    cover (DSM-vs-DTM separation). Roughness is taken from land cover, never
    from this height.
    """
    name = WORLDCOVER_CLASSES.get(int(class_code)) if class_code is not None else None
    return float(dsm_elevation_m) - WORLDCOVER_CANOPY_M.get(name, 0.0)


def surface_is_water(wbm_value, nodata=None) -> bool:
    """Interpret a GLO-30 Water Body Mask sample.

    WBM codes: 0 = land, 1 = ocean, 2 = lake, 3 = river. GLO-30 ocean cells are
    frequently NoData, so NoData (and a missing sample) counts as water, never as
    "missing". Only an explicit 0 is land.
    """
    if wbm_value is None:
        return True
    if nodata is not None and wbm_value == nodata:
        return True
    return int(wbm_value) != 0


def internal_boundary_layer_height(fetch_m: float, z0: float) -> float:
    """IBL height over a fetch of new surface (Elliott/Wood ~ x**0.8 growth)."""
    if fetch_m <= 0 or z0 <= 0:
        return REFERENCE_HEIGHT_M
    height = 0.28 * z0 * (fetch_m / z0) ** 0.8
    return min(MAX_BLENDING_HEIGHT_M, max(REFERENCE_HEIGHT_M, height))


def roughness_transfer_factor(z0_upwind: float, z0_downwind: float, fetch_m: float,
                              *, height: float = REFERENCE_HEIGHT_M) -> float:
    """Speed factor at ``height`` after a single roughness change.

    Two-log profile: the upwind and downwind log profiles are anchored to the
    same speed at the IBL top; below it the flow follows the new (downwind)
    surface. >1 moving to smoother ground, <1 to rougher, ->1 at zero fetch.
    """
    z0u = max(1e-5, float(z0_upwind))
    z0d = max(1e-5, float(z0_downwind))
    if abs(z0u - z0d) < 1e-9:
        return 1.0
    blend = internal_boundary_layer_height(fetch_m, max(z0u, z0d))
    if blend <= height:
        return 1.0
    downwind = math.log(height / z0d) / math.log(blend / z0d)
    upwind = math.log(height / z0u) / math.log(blend / z0u)
    return downwind / upwind


@dataclass(frozen=True)
class SectorSurface:
    upwind_z0: float
    downwind_z0: float
    fetch_m: float
    upwind_is_water: bool


class SurfaceProvider(Protocol):
    mounted: bool

    def sector_surface(self, lat: float, lon: float, sector_index: int) -> SectorSurface | None:
        """Upwind/downwind roughness and over-surface fetch, or None (no data)."""


class OrographyProvider(Protocol):
    def sector_speedup(self, lat: float, lon: float, sector_index: int) -> float:
        """Fractional orographic speed-up (1.0 = neutral). Deferred: default 1.0."""


@dataclass(frozen=True)
class MicroscaleSector:
    index: int
    start_deg: float
    end_deg: float
    speed_factor: float
    direction_offset_deg: float
    confidence: str
    saturated: bool
    upwind_z0: float
    downwind_z0: float
    fetch_m: float


@dataclass(frozen=True)
class MicroscaleResult:
    status: str
    sectors: list[MicroscaleSector]
    provenance: dict

    @property
    def enabled(self) -> bool:
        return self.status == STATUS_OK


def _sector_bounds(index: int) -> tuple[float, float]:
    start = (index * SECTOR_WIDTH) % 360.0
    return start, (start + SECTOR_WIDTH) % 360.0


def compute_microscale_sectors(lat: float, lon: float, *, surface_provider: SurfaceProvider,
                               orography: OrographyProvider | None = None,
                               grid_cell: list | None = None) -> MicroscaleResult:
    """Pure composition: IBL roughness transfer x optional orographic speed-up."""
    provenance = {"method": "microscale_ibl", "grid_cell": grid_cell}
    if not getattr(surface_provider, "mounted", False):
        return MicroscaleResult(STATUS_UNAVAILABLE, [], {**provenance, "status": STATUS_UNAVAILABLE})

    sectors: list[MicroscaleSector] = []
    for index in range(SECTOR_COUNT):
        start, end = _sector_bounds(index)
        surface = surface_provider.sector_surface(lat, lon, index)
        if surface is None:
            continue
        speedup = orography.sector_speedup(lat, lon, index) if orography is not None else 1.0
        raw = roughness_transfer_factor(surface.upwind_z0, surface.downwind_z0, surface.fetch_m) * speedup
        factor = clamp(raw, FACTOR_LOW, FACTOR_HIGH)
        sectors.append(MicroscaleSector(
            index, start, end, round(factor, 4), 0.0,
            "ok", factor != raw, surface.upwind_z0, surface.downwind_z0, surface.fetch_m,
        ))
    if not sectors:
        return MicroscaleResult(STATUS_UNAVAILABLE, [], {**provenance, "status": STATUS_UNAVAILABLE})
    return MicroscaleResult(STATUS_OK, sectors, {**provenance, "status": STATUS_OK})


def result_signature(result: MicroscaleResult) -> str:
    payload = {
        "method": result.provenance.get("method"),
        "grid_cell": result.provenance.get("grid_cell"),
        "sectors": [[s.index, s.speed_factor, s.confidence, s.saturated] for s in result.sectors],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _sector_note(result: MicroscaleResult, sector: MicroscaleSector, signature: str) -> str:
    return json.dumps({
        "method": result.provenance["method"], "grid_cell": result.provenance["grid_cell"],
        "upwind_z0": round(sector.upwind_z0, 5), "downwind_z0": round(sector.downwind_z0, 5),
        "fetch_m": round(sector.fetch_m, 1), "saturated": sector.saturated,
        "confidence": sector.confidence, "sig": signature,
    }, separators=(",", ":"))[:500]


def persist_microscale_sectors(db, spot_id, result: MicroscaleResult) -> dict:
    """Write a higher-version sector set that overrides the GWA prior.

    ``microscale_unavailable`` never writes (the GWA rows stay active). Also
    fills the profile roughness/land/water reference fields from the result.
    """
    from sqlalchemy import select

    from app.models import SpotWeatherProfile, SpotWeatherSector

    if result.status != STATUS_OK or not result.sectors:
        return {"status": result.status, "written": 0, "version": None, "reason": "no_write"}

    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id))
    if profile is None:
        profile = SpotWeatherProfile(spot_id=spot_id)
        db.add(profile)
        db.flush()

    existing = db.scalars(
        select(SpotWeatherSector).where(SpotWeatherSector.profile_id == profile.id)
    ).all()
    latest_version = max((row.version for row in existing), default=0)
    signature = result_signature(result)
    if latest_version:
        latest_rows = [row for row in existing if row.version == latest_version]
        stored = next((_note_sig(row.note) for row in latest_rows if row.note), None)
        if stored == signature:
            return {"status": result.status, "written": 0, "version": latest_version, "reason": "idempotent"}

    version = latest_version + 1
    for sector in result.sectors:
        db.add(SpotWeatherSector(
            profile_id=profile.id, start_deg=sector.start_deg, end_deg=sector.end_deg,
            speed_factor=sector.speed_factor, direction_offset_deg=sector.direction_offset_deg,
            version=version, enabled=True, note=_sector_note(result, sector, signature),
        ))
    # Surface provenance for audit (land/water reference + representative roughness).
    land = [s for s in result.sectors if s.downwind_z0 > CHARNOCK_SEA_Z0]
    profile.roughness_length_m = round(sum(s.downwind_z0 for s in land) / len(land), 5) if land else CHARNOCK_SEA_Z0
    profile.land_reference = {"z0_by_sector": {s.index: s.downwind_z0 for s in result.sectors}}
    profile.water_reference = {"charnock_z0": CHARNOCK_SEA_Z0,
                               "water_sectors": [s.index for s in result.sectors if s.upwind_z0 <= CHARNOCK_SEA_Z0]}
    db.commit()
    return {"status": result.status, "written": len(result.sectors), "version": version, "reason": "written"}


def _note_sig(note: str | None) -> str | None:
    if not note:
        return None
    try:
        return json.loads(note).get("sig")
    except (ValueError, TypeError):
        return None


class RasterSurfaceProvider:
    """WorldCover roughness + GLO-30 WBM coastline/fetch, read per sector.

    Unmounted (no raster dirs configured) -> mounted is False and the producer
    reports microscale_unavailable. WBM NoData is treated as water (Charnock),
    never as missing. rasterio is imported lazily; never used on a request path.
    """

    def __init__(self, worldcover_dir: str | None = None, dem_dir: str | None = None) -> None:
        self._worldcover_dir = worldcover_dir
        self._dem_dir = dem_dir

    @property
    def mounted(self) -> bool:
        return bool(self._worldcover_dir and self._dem_dir)

    def sector_surface(self, lat: float, lon: float, sector_index: int) -> SectorSurface | None:
        # Real sampling (WorldCover class ring + WBM coastline distance per bearing)
        # is wired where the rasters are mounted; unmounted installs get None.
        if not self.mounted:
            return None
        raise NotImplementedError(
            "RasterSurfaceProvider sampling runs only in the raster-mounted offline job"
        )


def build_spot_microscale(db, spot, *, surface_provider=None, orography=None) -> dict:
    """Compute and persist the microscale override for one spot (offline job)."""
    from app.era5.grid import resolve_grid_cell
    from app.live import service as live_service

    lat, lon = live_service._spot_coords(spot)
    grid_cell = resolve_grid_cell(lat, lon)["wind"]
    provider = surface_provider or RasterSurfaceProvider()
    result = compute_microscale_sectors(lat, lon, surface_provider=provider,
                                        orography=orography, grid_cell=grid_cell)
    outcome = persist_microscale_sectors(db, spot.id, result)
    return {"spot_id": str(spot.id), **outcome}
