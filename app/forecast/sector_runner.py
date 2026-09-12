"""Sector-producer runner: writes CANDIDATE sector factors, never activates.

Iterates published spots, runs a producer (GWA or microscale) and persists its
12 sectors as a new *candidate* version with ``enabled = False``. Activation is a
separate, WP1-gated path (see app/api/admin_weather.py); this runner never flips
``enabled`` to True, so writing candidates cannot change a single served value
(select_sector picks the newest *enabled* version).

Only ``status == "ok"`` writes factor rows; every other status (gwa_not_mounted,
gwa_nodata, reference_unavailable, microscale_unavailable) is recorded in the
run summary so coverage gaps are visible, never stored as a real factor. A
content hash over factors + provenance prevents version spam on re-runs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.era5.grid import resolve_grid_cell
from app.live import service as live_service
from app.models import ForecastSectorBuild, Spot, SpotWeatherProfile, SpotWeatherSector

PRODUCERS = ("gwa", "microscale")


def _compute(producer: str, spot):
    lat, lon = live_service._spot_coords(spot)
    grid_cell = resolve_grid_cell(lat, lon)["wind"]
    if producer == "gwa":
        from app.forecast.gwa_producer import Era5ReferenceSource, MountedGwaRasterReader, compute_gwa_sectors

        return compute_gwa_sectors(lat, lon, gwa_reader=MountedGwaRasterReader(),
                                   reference=Era5ReferenceSource(), grid_cell=grid_cell)
    if producer == "microscale":
        from app.forecast.microscale import RasterSurfaceProvider, compute_microscale_sectors

        return compute_microscale_sectors(lat, lon, surface_provider=RasterSurfaceProvider(), grid_cell=grid_cell)
    raise ValueError(f"unknown producer {producer!r}")


def candidate_signature(result) -> str:
    """Stable hash over the factor payload plus the revealing provenance."""
    payload = {
        "provenance": {k: v for k, v in result.provenance.items() if k != "status"},
        "sectors": [[round(s.start_deg, 3), round(s.speed_factor, 4), round(s.direction_offset_deg, 3),
                     s.confidence, s.saturated] for s in result.sectors],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _sector_note(result, sector, signature: str) -> str:
    provenance = {k: v for k, v in result.provenance.items() if k != "status"}
    return json.dumps({**provenance, "confidence": sector.confidence, "saturated": sector.saturated,
                       "candidate": True, "sig": signature}, separators=(",", ":"))[:500]


def _record_build(db, spot_id, producer, *, status, content_hash=None, version=None):
    row = db.scalar(select(ForecastSectorBuild).where(
        ForecastSectorBuild.spot_id == spot_id, ForecastSectorBuild.producer == producer))
    if row is None:
        row = ForecastSectorBuild(spot_id=spot_id, producer=producer)
        db.add(row)
    row.status = status
    row.content_hash = content_hash
    row.version = version
    row.built_at = datetime.now(timezone.utc)


def _persist_candidate(db, spot_id, producer, result) -> tuple[str, int | None]:
    """Write enabled=False candidate rows only for an ok result; hash-idempotent."""
    signature = candidate_signature(result)
    existing_build = db.scalar(select(ForecastSectorBuild).where(
        ForecastSectorBuild.spot_id == spot_id, ForecastSectorBuild.producer == producer))
    if existing_build is not None and existing_build.content_hash == signature:
        _record_build(db, spot_id, producer, status="unchanged", content_hash=signature,
                      version=existing_build.version)
        return "unchanged", existing_build.version

    profile = db.scalar(select(SpotWeatherProfile).where(SpotWeatherProfile.spot_id == spot_id))
    if profile is None:
        profile = SpotWeatherProfile(spot_id=spot_id)
        db.add(profile)
        db.flush()
    latest_version = db.scalar(select(func.max(SpotWeatherSector.version)).where(
        SpotWeatherSector.profile_id == profile.id)) or 0
    version = latest_version + 1
    for sector in result.sectors:
        db.add(SpotWeatherSector(
            profile_id=profile.id, start_deg=sector.start_deg, end_deg=sector.end_deg,
            speed_factor=sector.speed_factor, direction_offset_deg=sector.direction_offset_deg,
            version=version, enabled=False, note=_sector_note(result, sector, signature),
        ))
    _record_build(db, spot_id, producer, status="candidate_written", content_hash=signature, version=version)
    return "candidate_written", version


def _target_spots(db, *, spot_ids, producer, limit):
    query = (
        select(Spot)
        .outerjoin(ForecastSectorBuild,
                   (ForecastSectorBuild.spot_id == Spot.id) & (ForecastSectorBuild.producer == producer))
        .order_by(ForecastSectorBuild.built_at.asc().nullsfirst(), Spot.id)
    )
    if spot_ids:
        query = query.where(Spot.id.in_(list(spot_ids)))
    else:
        query = query.where(Spot.status == "published")
    if limit:
        query = query.limit(limit)
    return db.scalars(query).all()


def run_sector_producer(db, *, producer: str = "gwa", spot_ids=None, limit=None, dry_run: bool = False) -> dict:
    """Run the producer over target spots, writing candidates only (never enabled)."""
    if producer not in PRODUCERS:
        raise ValueError(f"unknown producer {producer!r}")
    spots = _target_spots(db, spot_ids=spot_ids, producer=producer, limit=limit)
    statuses: dict[str, int] = {}
    rows = []
    for spot in spots:
        try:
            result = _compute(producer, spot)
            if result.status != "ok":
                status = result.status
                version = None
                if not dry_run:
                    _record_build(db, spot.id, producer, status=status)
            elif dry_run:
                status, version = "candidate_written", None  # would write
            else:
                status, version = _persist_candidate(db, spot.id, producer, result)
        except Exception as exc:  # one spot must never abort the batch
            db.rollback()
            status, version = "error", None
            rows.append({"spot_id": str(spot.id), "status": status, "error_class": type(exc).__name__})
            statuses[status] = statuses.get(status, 0) + 1
            continue
        rows.append({"spot_id": str(spot.id), "status": status, "version": version})
        statuses[status] = statuses.get(status, 0) + 1
    if not dry_run:
        db.commit()
    return {"producer": producer, "processed": len(spots), "dry_run": dry_run,
            "statuses": statuses, "spots": rows}
