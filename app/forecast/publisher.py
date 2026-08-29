"""Idempotent jobs and atomic public snapshot activation."""

from __future__ import annotations
import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import load_only, noload

from app.forecast import CONSENSUS_VERSION, PHYSICS_VERSION
from app.forecast.geoprofile import ensure_profile
from app.forecast.registry import public_attributions
from app.live import service as legacy
from app.live.cache import default_cache
from app.live.client import default_client
from app.live.public_cache import set_public_forecast
from app.models import ForecastProcessingJob, ForecastSnapshot, Spot
from app.schemas.live import ForecastSeriesRead
from app.live.weather_contract import WEATHER_CONTRACT_VERSION

ACTIVE = ("queued", "processing")
MAX_PUBLIC_STALE = timedelta(hours=12)


def job_key(spot_id, *, profile: bool, reason: str, coordinates_hash: str = "unknown", bucket: str | None = None) -> str:
    stable = bucket or datetime.now(timezone.utc).strftime("%Y%m%d%H")
    return hashlib.sha256(
        f"forecast:{spot_id}:{coordinates_hash}:{profile}:{reason}:{WEATHER_CONTRACT_VERSION}:{stable}".encode()
    ).hexdigest()


def enqueue(
    db, spot_id, *, requested_by=None, rebuild_profile=False, reason="automatic"
):
    spot = db.scalar(
        select(Spot)
        .where(Spot.id == spot_id)
        .options(load_only(Spot.id, Spot.location), noload(Spot.weather_profile))
    )
    coordinates_hash = "missing"
    if spot is not None:
        from geoalchemy2.shape import to_shape
        point = to_shape(spot.location)
        coordinates_hash = hashlib.sha256(f"{point.y:.6f},{point.x:.6f}".encode()).hexdigest()[:16]
    key = job_key(spot_id, profile=rebuild_profile, reason=reason, coordinates_hash=coordinates_hash)
    current = db.scalar(
        select(ForecastProcessingJob).where(
            ForecastProcessingJob.idempotency_key == key
        )
    )
    if current:
        if current.status == "failed" and current.attempt_count < 3:
            current.status = "queued"
            current.error = None
            current.progress = 0
            current.started_at = None
            current.finished_at = None
            db.commit()
            db.refresh(current)
        return current
    active = db.scalar(
        select(ForecastProcessingJob)
        .where(
            ForecastProcessingJob.spot_id == spot_id,
            ForecastProcessingJob.status.in_(ACTIVE),
        )
        .order_by(ForecastProcessingJob.created_at.desc())
    )
    if active:
        return active
    job = ForecastProcessingJob(
        spot_id=spot_id,
        kind="profile_forecast" if rebuild_profile else "forecast",
        status="queued",
        idempotency_key=key,
        requested_by=requested_by,
        options={"rebuild_profile": rebuild_profile, "reason": reason},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_job(db, job_id, *, client=None, cache=None):
    job = db.scalar(
        select(ForecastProcessingJob)
        .where(ForecastProcessingJob.id == job_id)
        .with_for_update()
    )
    if not job or job.status not in ACTIVE:
        return job
    job.status = "processing"
    job.started_at = datetime.now(timezone.utc)
    job.attempt_count += 1
    job.progress = 5
    db.commit()
    try:
        spot = db.scalar(
            select(Spot)
            .where(Spot.id == job.spot_id)
            .options(
                load_only(Spot.id, Spot.location, Spot.status),
                noload(Spot.weather_profile),
            )
        )
        if not spot:
            raise LookupError("spot not found")
        target_spot_id = spot.id
        target_spot_is_public = spot.status == "published"
        profile = ensure_profile(
            db,
            spot,
            force=bool(job.options.get("rebuild_profile")),
            allow_remote_rasters=False,
        )
        job.progress = 30
        db.commit()
        # Stable migration source. Direct adapters run in shadow until their
        # run completeness gates pass; a failed shadow source never reaches here.
        cache_backend = cache or default_cache()
        payload = legacy.get_forecast_series(
            target_spot_id,
            10,
            db=db,
            client=client or default_client(),
            cache=cache_backend,
        )
        internal_weather = dict(payload.pop("internal", {}))
        payload["model"] = "surfwinddata"
        payload["models"] = []
        payload = ForecastSeriesRead.model_validate(payload).model_dump(mode="json")
        generated = datetime.now(timezone.utc)
        quality = (
            "automatic" if profile.profile.get("corrections_enabled") else "baseline"
        )
        snapshot = ForecastSnapshot(
            spot_id=target_spot_id,
            generated_at=generated,
            valid_until=generated + timedelta(hours=3),
            consensus_version=CONSENSUS_VERSION,
            physics_version=PHYSICS_VERSION,
            geo_profile_id=profile.id,
            quality_level=quality,
            fallback_status="open_meteo_transition",
            payload=payload,
            internal={
                "source": "open-meteo",
                "geo_profile_status": profile.status,
                "geo_profile_quality": profile.quality,
                **internal_weather,
            },
            attributions=public_attributions({"open-meteo"}),
            active=False,
        )
        db.add(snapshot)
        db.flush()
        newer = db.scalar(select(ForecastSnapshot).where(
            ForecastSnapshot.spot_id == target_spot_id,
            ForecastSnapshot.active.is_(True),
            ForecastSnapshot.generated_at > generated,
        ).with_for_update())
        if newer is not None:
            job.status = "superseded"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return job
        db.execute(
            update(ForecastSnapshot)
            .where(
                ForecastSnapshot.spot_id == target_spot_id,
                ForecastSnapshot.active.is_(True),
                ForecastSnapshot.id != snapshot.id,
            )
            .values(active=False)
        )
        snapshot.active = True
        job.progress = 100
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        job.diagnostics = {
            "snapshot_id": str(snapshot.id),
            "fallback_status": snapshot.fallback_status,
            "quality_level": quality,
            "weather_contract_version": WEATHER_CONTRACT_VERSION,
            "availability": payload.get("availability", {}),
            "horizons": internal_weather.get("horizons", {}),
            "marine_grid_distance_km": (internal_weather.get("marine") or {}).get("grid_distance_km"),
        }
        cached_public_payload = public_payload(snapshot)
        cached_spot_id = target_spot_id
        cached_spot_is_public = target_spot_is_public
        cached_valid_until = snapshot.valid_until
        db.commit()
        # Publish only after the active snapshot transaction succeeds. The
        # cache helper fails open, so Redis cannot turn a successful DB publish
        # into a failed generation job.
        if cached_spot_is_public:
            set_public_forecast(
                cache_backend,
                cached_spot_id,
                cached_public_payload,
                valid_until=cached_valid_until,
            )
        return job
    except Exception as exc:
        db.rollback()
        job = db.get(ForecastProcessingJob, job_id)
        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
        job.error = str(exc)[:2000]
        db.commit()
        return job


def active_snapshot(db, spot_id, *, allow_stale=True):
    row = db.scalar(
        select(ForecastSnapshot)
        .where(ForecastSnapshot.spot_id == spot_id, ForecastSnapshot.active.is_(True))
        .order_by(ForecastSnapshot.generated_at.desc())
    )
    if row:
        now = datetime.now(timezone.utc)
        if row.valid_until >= now:
            return row
        if allow_stale and row.valid_until >= now - MAX_PUBLIC_STALE:
            return row
    return None


def public_payload(snapshot):
    data = dict(snapshot.payload)
    data["model"] = "surfwinddata"
    data["models"] = []
    data["product"] = "Surfwinddata Forecast"
    data["updated_at"] = snapshot.generated_at.isoformat()
    data["confidence_note"] = "Berechneter Forecast mit modellabhängiger Unsicherheit."
    data["attributions"] = snapshot.attributions
    data["stale"] = snapshot.valid_until < datetime.now(timezone.utc)
    if data["stale"]:
        data["availability"] = {
            key: "available_stale" if value == "available" else value
            for key, value in (data.get("availability") or {}).items()
        }
    return data
