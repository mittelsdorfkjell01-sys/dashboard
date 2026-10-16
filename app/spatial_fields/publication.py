"""Transactional activation and rollback for weather-field publications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from sqlalchemy import func, select, text

from app.models.weather_field import (
    WeatherFieldAsset,
    WeatherFieldPublication,
    WeatherFieldQualityEvent,
    WeatherFieldRun,
)
from app.spatial_fields.contracts_v2 import classify_freshness


REQUIRED_HARD_GATES = frozenset(
    {
        "uv_pair",
        "utc_times",
        "coverage",
        "grid_continuity",
        "value_ranges",
        "asset_integrity",
        "grib_tile_comparison",
        "tile_border_continuity",
        "processing_version",
        "attribution",
        "near_term_completeness",
    }
)


class PublicationNotReady(RuntimeError):
    def __init__(self, reasons: tuple[str, ...]):
        self.reasons = reasons
        super().__init__("weather-field publication is not ready: " + "; ".join(reasons))


@dataclass(frozen=True)
class PublicationReadiness:
    ready: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ActivePublicationState:
    publication_id: uuid.UUID
    run_id: uuid.UUID
    generation: int
    manifest_object_key: str
    model_run_at: datetime
    age_seconds: int
    freshness: str


def assess_publication_readiness(
    *,
    run_status: str,
    asset_statuses: list[str],
    manifest_verified: bool,
    hard_gates: dict[str, bool],
) -> PublicationReadiness:
    reasons: list[str] = []
    if run_status != "ready":
        reasons.append(f"run status is {run_status!r}, expected 'ready'")
    if not asset_statuses:
        reasons.append("run has no registered assets")
    elif any(status != "verified" for status in asset_statuses):
        reasons.append("all registered assets must be verified")
    if not manifest_verified:
        reasons.append("manifest asset is not verified")
    missing = sorted(REQUIRED_HARD_GATES - hard_gates.keys())
    if missing:
        reasons.append("missing hard gates: " + ", ".join(missing))
    failed = sorted(key for key in REQUIRED_HARD_GATES if hard_gates.get(key) is False)
    if failed:
        reasons.append("failed hard gates: " + ", ".join(failed))
    return PublicationReadiness(not reasons, tuple(reasons))


def stage_publication(
    db,
    *,
    scope_key: str,
    run_id: uuid.UUID,
    manifest_asset_id: uuid.UUID,
    publication_id: uuid.UUID | None = None,
    actor: str | None = None,
    reason: str | None = None,
) -> WeatherFieldPublication:
    publication = WeatherFieldPublication(
        id=publication_id or uuid.uuid4(),
        scope_key=scope_key,
        run_id=run_id,
        manifest_asset_id=manifest_asset_id,
        status="staged",
        active=False,
        actor=actor,
        reason=reason,
    )
    db.add(publication)
    db.flush()
    return publication


def _lock_scope(db, scope_key: str) -> None:
    # A transaction-scoped advisory lock also serializes the first activation,
    # where no existing publication row is available for SELECT FOR UPDATE.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope_key, 0))"),
        {"scope_key": scope_key},
    )


def _readiness_for(db, publication: WeatherFieldPublication) -> PublicationReadiness:
    run = db.scalar(
        select(WeatherFieldRun)
        .where(WeatherFieldRun.id == publication.run_id)
        .with_for_update()
    )
    if run is None:
        return PublicationReadiness(False, ("field run does not exist",))
    assets = db.scalars(
        select(WeatherFieldAsset).where(WeatherFieldAsset.run_id == run.id)
    ).all()
    manifest_verified = any(
        asset.id == publication.manifest_asset_id
        and asset.asset_type == "manifest"
        and asset.status == "verified"
        for asset in assets
    )
    events = db.scalars(
        select(WeatherFieldQualityEvent).where(
            WeatherFieldQualityEvent.run_id == run.id,
            WeatherFieldQualityEvent.hard_gate.is_(True),
        )
    ).all()
    gates = {event.gate_key: bool(event.passed) for event in events}
    return assess_publication_readiness(
        run_status=run.status,
        asset_statuses=[asset.status for asset in assets],
        manifest_verified=manifest_verified,
        hard_gates=gates,
    )


def activate_publication(
    db,
    publication_id: uuid.UUID,
    *,
    actor: str | None = None,
    reason: str | None = None,
    now: datetime | None = None,
    previous_status: str = "superseded",
    rollout_policy=None,
) -> WeatherFieldPublication:
    scope_key = db.scalar(
        select(WeatherFieldPublication.scope_key).where(
            WeatherFieldPublication.id == publication_id
        )
    )
    if scope_key is None:
        raise LookupError("weather-field publication not found")
    _lock_scope(db, scope_key)
    publication = db.scalar(
        select(WeatherFieldPublication)
        .where(WeatherFieldPublication.id == publication_id)
        .with_for_update()
    )
    if publication is None:  # pragma: no cover - deleted in the same transaction race
        raise LookupError("weather-field publication not found")
    if publication.active and publication.status == "active":
        return publication
    if publication.status != "staged":
        raise ValueError("only a staged weather-field publication can be activated")

    readiness = _readiness_for(db, publication)
    if not readiness.ready:
        raise PublicationNotReady(readiness.reasons)
    if rollout_policy is not None:
        from app.spatial_fields.rollout import assess_shadow_readiness

        rollout = assess_shadow_readiness(
            db,
            candidate_run_id=publication.run_id,
            settings=rollout_policy,
            now=now,
        )
        if not rollout.ready:
            raise PublicationNotReady(
                tuple(f"shadow rollout: {reason}" for reason in rollout.reasons)
            )

    activated_at = now or datetime.now(timezone.utc)
    if activated_at.tzinfo is None or activated_at.utcoffset() != timezone.utc.utcoffset(
        activated_at
    ):
        raise ValueError("publication activation time must be timezone-aware UTC")
    current = db.scalar(
        select(WeatherFieldPublication)
        .where(
            WeatherFieldPublication.scope_key == publication.scope_key,
            WeatherFieldPublication.active.is_(True),
        )
        .with_for_update()
    )
    maximum_generation = db.scalar(
        select(func.max(WeatherFieldPublication.generation)).where(
            WeatherFieldPublication.scope_key == publication.scope_key
        )
    )
    if current is not None and current.id != publication.id:
        current.active = False
        current.status = previous_status
        current.deactivated_at = activated_at
        publication.supersedes_publication_id = current.id
        # Satisfy the partial unique index before promoting the replacement.
        # Both writes remain invisible until the surrounding transaction commits.
        db.flush([current])
    publication.status = "active"
    publication.active = True
    publication.activated_at = activated_at
    publication.deactivated_at = None
    publication.generation = int(maximum_generation or 0) + 1
    publication.actor = actor or publication.actor
    publication.reason = reason or publication.reason
    db.flush()
    return publication


def active_publication_state(
    db, scope_key: str, *, now: datetime | None = None
) -> ActivePublicationState | None:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() != timezone.utc.utcoffset(instant):
        raise ValueError("freshness evaluation time must be timezone-aware UTC")
    row = db.execute(
        select(WeatherFieldPublication, WeatherFieldRun, WeatherFieldAsset)
        .join(WeatherFieldRun, WeatherFieldRun.id == WeatherFieldPublication.run_id)
        .join(
            WeatherFieldAsset,
            WeatherFieldAsset.id == WeatherFieldPublication.manifest_asset_id,
        )
        .where(
            WeatherFieldPublication.scope_key == scope_key,
            WeatherFieldPublication.active.is_(True),
        )
    ).one_or_none()
    if row is None:
        return None
    publication, run, manifest = row
    age_seconds = max(0, int((instant - run.model_run_at).total_seconds()))
    return ActivePublicationState(
        publication_id=publication.id,
        run_id=run.id,
        generation=int(publication.generation),
        manifest_object_key=manifest.object_key,
        model_run_at=run.model_run_at,
        age_seconds=age_seconds,
        freshness=classify_freshness(age_seconds),
    )


def rollback_publication(
    db,
    *,
    scope_key: str,
    restore_publication_id: uuid.UUID,
    actor: str,
    reason: str,
    now: datetime | None = None,
) -> WeatherFieldPublication:
    source = db.scalar(
        select(WeatherFieldPublication).where(
            WeatherFieldPublication.id == restore_publication_id,
            WeatherFieldPublication.scope_key == scope_key,
        )
    )
    if source is None:
        raise LookupError("rollback source publication not found in scope")
    if source.status not in {"active", "superseded", "rolled_back"}:
        raise ValueError("rollback source has never been an active publication")
    rollback = stage_publication(
        db,
        scope_key=scope_key,
        run_id=source.run_id,
        manifest_asset_id=source.manifest_asset_id,
        actor=actor,
        reason=reason,
    )
    return activate_publication(
        db,
        rollback.id,
        actor=actor,
        reason=reason,
        now=now,
        previous_status="rolled_back",
    )
