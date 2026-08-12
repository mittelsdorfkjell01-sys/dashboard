"""Atomic, idempotent persistence for internal shadow profiles."""

from __future__ import annotations
from sqlalchemy import select, update
from app.forecast.shadow import SHADOW_VERSION, input_hash
from app.models import SpotGeoShadowProfile, SpotGeoShadowSector

RANK = {"A": 4, "B": 3, "C": 2, "D": 1}


def persist_shadow(
    db,
    *,
    spot_id,
    coordinate_hash: str,
    dataset_versions: list[str],
    asset_hashes: list[str],
    analysis: dict,
    sectors: list[dict],
    profile_class: str,
    status: str = "ready",
    metrics: dict | None = None,
    warnings: list | None = None,
):
    digest = input_hash(spot_id, coordinate_hash, dataset_versions, asset_hashes)
    existing = db.scalar(
        select(SpotGeoShadowProfile).where(
            SpotGeoShadowProfile.spot_id == spot_id,
            SpotGeoShadowProfile.input_hash == digest,
        )
    )
    if existing:
        return existing
    current = db.scalar(
        select(SpotGeoShadowProfile).where(
            SpotGeoShadowProfile.spot_id == spot_id,
            SpotGeoShadowProfile.active_shadow.is_(True),
        )
    )
    activate = (
        status == "ready"
        and profile_class != "D"
        and (current is None or RANK[profile_class] >= RANK[current.profile_class])
    )
    row = SpotGeoShadowProfile(
        spot_id=spot_id,
        input_hash=digest,
        algorithm_version=SHADOW_VERSION,
        status=status,
        profile_class=profile_class,
        active_shadow=activate,
        analysis={
            **analysis,
            "dataset_versions": dataset_versions,
            "asset_hashes": asset_hashes,
            "physics_enabled": False,
        },
        metrics=metrics or {},
        warnings=warnings or [],
    )
    db.add(row)
    db.flush()
    for item in sectors:
        db.add(
            SpotGeoShadowSector(
                shadow_profile_id=row.id,
                sector_index=item["sector_index"],
                center_deg=item["center_deg"],
                status=item["status"],
                features=item["features"],
                quality=item["quality"],
            )
        )
    if activate:
        db.execute(
            update(SpotGeoShadowProfile)
            .where(
                SpotGeoShadowProfile.spot_id == spot_id,
                SpotGeoShadowProfile.active_shadow.is_(True),
                SpotGeoShadowProfile.id != row.id,
            )
            .values(active_shadow=False)
        )
    db.flush()
    return row


def blocked_shadow(db, *, spot_id, coordinate_hash: str, status: str, reason: str):
    return persist_shadow(
        db,
        spot_id=spot_id,
        coordinate_hash=coordinate_hash,
        dataset_versions=["cop-dem:2024_1", "worldcover:v200"],
        asset_hashes=[],
        analysis={"block_reason": reason},
        sectors=[],
        profile_class="D",
        status=status,
        warnings=[reason],
    )
