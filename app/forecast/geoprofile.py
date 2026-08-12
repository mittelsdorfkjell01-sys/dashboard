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
from app.models import (
    GeodataAsset,
    GeodataDataset,
    SpotGeoProfileInput,
    SpotGeoProfileVersion,
)


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
    landcover = {}
    raster_diagnostics = {}
    worldcover_asset = None
    try:
        from app.forecast.geodata import WorldCoverAdapter, analysis_crs
        from app.forecast.geodata_catalog import sync_catalog

        sync_catalog(db)
        landcover, raster_diagnostics = WorldCoverAdapter.analyze_remote(
            p.y, p.x, cache_root=get_settings().geodata_cache_dir
        )
        dataset = db.scalar(
            select(GeodataDataset).where(
                GeodataDataset.key == "worldcover-2021",
                GeodataDataset.version == "v200",
            )
        )
        worldcover_asset = db.scalar(
            select(GeodataAsset).where(
                GeodataAsset.dataset_id == dataset.id,
                GeodataAsset.asset_key == raster_diagnostics["path"],
                GeodataAsset.byte_range.is_(None),
            )
        )
        if worldcover_asset is None:
            from datetime import datetime, timezone

            worldcover_asset = GeodataAsset(
                dataset_id=dataset.id,
                asset_key=raster_diagnostics["path"],
                tile_id=raster_diagnostics["tile"],
                bbox={},
                file_type="NPZ-derived-window",
                crs="EPSG:4326",
                size_bytes=raster_diagnostics["size_bytes"],
                checksum=raster_diagnostics["checksum"],
                storage_path=raster_diagnostics["path"],
                status="ready",
                last_accessed_at=datetime.now(timezone.utc),
                asset_metadata={"source_format": "COG", "range_windowed": True},
            )
            db.add(worldcover_asset)
            db.flush()
        sources.append(
            {
                "key": "worldcover-2021",
                "dataset_version": "v200",
                "resolution_m": 10,
                "asset_hash": raster_diagnostics["checksum"],
            }
        )
    except Exception as exc:
        warnings.append(f"WorldCover unavailable: {type(exc).__name__}: {exc}")
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
        quality="B" if corrections and landcover else "C" if sources else "D",
        sources=sources,
        profile={
            "latitude": p.y,
            "longitude": p.x,
            "elevation_m": elevation,
            "sector_count": 16,
            "sectors": sectors,
            "corrections_enabled": corrections,
            "analysis_crs": analysis_crs(p.y, p.x) if landcover else None,
            "landcover_rings": landcover,
            "raster_diagnostics": raster_diagnostics,
            "feature_quality": {
                "landcover": {
                    "class": "B" if landcover else "D",
                    "coverage": raster_diagnostics.get("coverage", 0),
                },
                "elevation": {
                    "class": "B" if elevation is not None else "D",
                    "fallback": "nasa-srtm" if elevation is not None else None,
                },
            },
            "profile_class": "B"
            if corrections and landcover
            else "C"
            if sources
            else "D",
        },
        warnings=warnings,
        active=bool(sources),
    )
    if profile.active:
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
    if worldcover_asset is not None:
        db.add(
            SpotGeoProfileInput(
                profile_id=profile.id,
                asset_id=worldcover_asset.id,
                role="landcover",
                quality={"coverage": raster_diagnostics.get("coverage"), "class": "B"},
            )
        )
    return profile
