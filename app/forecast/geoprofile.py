"""Idempotent automatic geoprofile foundation.

The first production slice persists an honest coordinate profile for every
spot. Raster-derived corrections are activated only when versioned inputs are
present; absence lowers quality instead of inventing terrain or coastline.
"""

from __future__ import annotations
import hashlib
from sqlalchemy import func, select, update
from geoalchemy2.shape import to_shape

from app.forecast import GEO_PROFILE_VERSION
from app.models import SpotGeoProfileVersion


def coordinate_hash(spot) -> str:
    p = to_shape(spot.location)
    return hashlib.sha256(f"{p.y:.7f},{p.x:.7f}".encode()).hexdigest()


def ensure_profile(db, spot, *, force: bool = False) -> SpotGeoProfileVersion:
    digest = coordinate_hash(spot)
    existing = db.scalar(
        select(SpotGeoProfileVersion).where(
            SpotGeoProfileVersion.spot_id == spot.id,
            SpotGeoProfileVersion.coordinate_hash == digest,
            SpotGeoProfileVersion.algorithm_version == GEO_PROFILE_VERSION,
        )
    )
    # Same coordinates + algorithm are the same immutable input version. A
    # manual double-click/retry reuses it instead of creating duplicates.
    if existing:
        return existing
    version = (
        db.scalar(
            select(func.max(SpotGeoProfileVersion.version)).where(
                SpotGeoProfileVersion.spot_id == spot.id
            )
        )
        or 0
    ) + 1
    p = to_shape(spot.location)
    sources = []
    warnings = []
    sectors = []
    elevation = None
    from app.config import get_settings

    root = get_settings().forecast_srtm_dir
    if root:
        from app.forecast.terrain import SrtmTerrain, TerrainUnavailable

        try:
            terrain = SrtmTerrain(root)
            elevation = terrain.elevation(p.y, p.x)
            sectors = terrain.sectors(p.y, p.x)
            sources = [
                {
                    "key": "nasa-srtm",
                    "dataset_version": "operator-provisioned",
                    "resolution_m": 90,
                }
            ]
        except TerrainUnavailable as exc:
            warnings.append(str(exc))
    if not sources:
        warnings.append(
            "Global raster package not provisioned; physical correction remains neutral."
        )
    corrections = bool(
        sources
        and elevation is not None
        and any(s["terrain_shelter"] is not None for s in sectors)
    )
    profile = SpotGeoProfileVersion(
        spot_id=spot.id,
        version=version,
        algorithm_version=GEO_PROFILE_VERSION,
        coordinate_hash=digest,
        status="ready",
        quality="terrain" if corrections else "coordinates",
        sources=sources,
        profile={
            "latitude": p.y,
            "longitude": p.x,
            "elevation_m": elevation,
            "sector_count": 16,
            "sectors": sectors,
            "corrections_enabled": corrections,
        },
        warnings=warnings,
        active=True,
    )
    db.execute(
        update(SpotGeoProfileVersion)
        .where(
            SpotGeoProfileVersion.spot_id == spot.id,
            SpotGeoProfileVersion.active.is_(True),
        )
        .values(active=False, status="stale")
    )
    db.add(profile)
    db.flush()
    return profile
