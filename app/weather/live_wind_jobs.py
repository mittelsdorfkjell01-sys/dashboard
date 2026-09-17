"""Fair, resumable and idempotent shadow execution for every published spot."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import math
import time
import uuid

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.live.cache import Cache
from app.models import Region, Spot, WeatherLiveWindJob
from app.schemas.live import LiveWindRead
from app.weather.live_wind_analysis import REGIONAL_LIVE_WIND_VERSION
from app.weather.live_wind_rollout import region_key


def utc_cycle(
    value: datetime,
    *,
    minutes: int,
) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("cycle time must be timezone-aware")
    current = value.astimezone(timezone.utc)
    minute = current.minute - current.minute % minutes
    return current.replace(minute=minute, second=0, microsecond=0)


def retry_delay_seconds(
    attempt_count: int,
    *,
    initial_seconds: int,
    maximum_seconds: int,
    identity: uuid.UUID | None = None,
) -> int:
    """Bounded exponential backoff with stable per-job desynchronisation."""
    exponent = max(0, min(int(attempt_count) - 1, 20))
    base = min(int(maximum_seconds), int(initial_seconds) * (2**exponent))
    if identity is None or base >= maximum_seconds:
        return base
    jitter = int(base * 0.10 * ((identity.int % 1000) / 1000.0))
    return min(int(maximum_seconds), base + jitter)


def enqueue_live_wind_cycle(
    db,
    *,
    now: datetime | None = None,
    limit: int | None = None,
    settings: Settings | None = None,
) -> dict:
    """Queue the least-recently analyzed published spots without overlap.

    Never-run spots sort first. The partial unique index permits only one active
    job per spot, while the cycle key makes repeated scheduler calls idempotent.
    """
    cfg = settings or get_settings()
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cycle = utc_cycle(instant, minutes=cfg.live_wind_cycle_minutes)
    batch_size = max(1, min(limit or cfg.live_wind_enqueue_batch_size, 1000))

    active_job = exists(
        select(WeatherLiveWindJob.id).where(
            WeatherLiveWindJob.spot_id == Spot.id,
            WeatherLiveWindJob.status.in_(("queued", "processing", "retry_wait")),
        )
    )
    last_cycle = (
        select(func.max(WeatherLiveWindJob.cycle_at))
        .where(WeatherLiveWindJob.spot_id == Spot.id)
        .correlate(Spot)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Spot.id, Spot.region_id, Region.slug)
        .outerjoin(Region, Region.id == Spot.region_id)
        .where(Spot.status == "published", ~active_job)
        .order_by(last_cycle.asc().nullsfirst(), Spot.id)
        .limit(batch_size)
    ).all()
    if not rows:
        return {
            "cycle_at": cycle.isoformat(),
            "selected": 0,
            "enqueued": 0,
            "deduplicated": 0,
            "rollout_stage": cfg.live_wind_rollout_stage,
            "public_effect": "none" if cfg.live_wind_rollout_stage in {"shadow", "internal"} else "gated",
        }

    values = [
        {
            "spot_id": spot_id,
            "region_id": region_id,
            "region_key": str(slug).casefold() if slug else "unassigned",
            "cycle_at": cycle,
            "rollout_stage": cfg.live_wind_rollout_stage,
            "analysis_version": REGIONAL_LIVE_WIND_VERSION,
            "status": "queued",
            "available_at": instant,
        }
        for spot_id, region_id, slug in rows
    ]
    inserted = list(
        db.execute(
            insert(WeatherLiveWindJob)
            .values(values)
            .on_conflict_do_nothing()
            .returning(WeatherLiveWindJob.id)
        ).scalars()
    )
    db.commit()
    return {
        "cycle_at": cycle.isoformat(),
        "selected": len(rows),
        "enqueued": len(inserted),
        "deduplicated": len(rows) - len(inserted),
        "rollout_stage": cfg.live_wind_rollout_stage,
        "public_effect": "none" if cfg.live_wind_rollout_stage in {"shadow", "internal"} else "gated",
    }


def claim_live_wind_job(
    db,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> WeatherLiveWindJob | None:
    """Claim one due job using a database-backed distributed lease."""
    cfg = settings or get_settings()
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stale_before = instant - timedelta(seconds=cfg.live_wind_job_lease_seconds)
    job = db.scalar(
        select(WeatherLiveWindJob)
        .where(
            or_(
                (
                    (WeatherLiveWindJob.status == "queued")
                    & (WeatherLiveWindJob.available_at <= instant)
                ),
                (
                    (WeatherLiveWindJob.status == "retry_wait")
                    & (WeatherLiveWindJob.available_at <= instant)
                ),
                (
                    (WeatherLiveWindJob.status == "processing")
                    & (
                        (WeatherLiveWindJob.heartbeat_at.is_(None))
                        | (WeatherLiveWindJob.heartbeat_at < stale_before)
                    )
                ),
            )
        )
        .order_by(
            WeatherLiveWindJob.available_at,
            WeatherLiveWindJob.created_at,
            WeatherLiveWindJob.spot_id,
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = "processing"
    job.attempt_count += 1
    job.claimed_at = instant
    job.heartbeat_at = instant
    job.worker_token = uuid.uuid4()
    job.error_class = None
    db.commit()
    return job


def heartbeat_live_wind_job(
    db,
    job: WeatherLiveWindJob,
    *,
    now: datetime | None = None,
) -> bool:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    result = db.execute(
        update(WeatherLiveWindJob)
        .where(
            WeatherLiveWindJob.id == job.id,
            WeatherLiveWindJob.status == "processing",
            WeatherLiveWindJob.worker_token == job.worker_token,
        )
        .values(heartbeat_at=instant, updated_at=instant)
    )
    db.commit()
    return bool(result.rowcount)


def _parse_utc(value) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def _exclusion_counts(payload: dict, diagnostics: dict) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for contribution in payload.get("station_contributions") or []:
        if not isinstance(contribution, dict):
            continue
        for reason in contribution.get("exclusion_reasons") or []:
            counts[str(reason)] += 1
    selection = diagnostics.get("station_selection") or {}
    for candidate in selection.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        for reason in candidate.get("exclusion_reasons") or []:
            counts[str(reason)] += 1
    for reason, amount in (diagnostics.get("residual_rejection_reasons") or {}).items():
        if isinstance(amount, int) and amount > 0:
            counts[str(reason)] += amount
    return dict(sorted(counts.items()))


def _terrain_class(spot, payload: dict) -> str:
    component = payload.get("local_physics_component")
    if isinstance(component, dict):
        for key in ("terrain_class", "surface_class", "kind", "component"):
            if component.get(key):
                return str(component[key])[:48]
    profile = getattr(spot, "weather_profile", None)
    return str(getattr(profile, "quality_tier", None) or "unknown")[:48]


def _complete_job(
    db,
    job: WeatherLiveWindJob,
    payload: dict,
    *,
    cache_hit: bool,
    duration_ms: int,
    spot,
    finished_at: datetime,
    analysis_diagnostics: dict,
) -> bool:
    correction_u = payload.get("correction_u_ms")
    correction_v = payload.get("correction_v_ms")
    correction = None
    if all(isinstance(value, (int, float)) for value in (correction_u, correction_v)):
        correction = math.hypot(float(correction_u), float(correction_v))
    result = db.execute(
        update(WeatherLiveWindJob)
        .where(
            WeatherLiveWindJob.id == job.id,
            WeatherLiveWindJob.status == "processing",
            WeatherLiveWindJob.worker_token == job.worker_token,
        )
        .values(
            status="succeeded",
            finished_at=finished_at,
            heartbeat_at=finished_at,
            worker_token=None,
            error_class=None,
            region_id=getattr(spot, "region_id", None),
            region_key=region_key(spot),
            terrain_class=_terrain_class(spot, payload),
            product_status=payload.get("status"),
            analyzed_at=_parse_utc(payload.get("analyzed_at")),
            valid_at=_parse_utc(payload.get("valid_at")),
            station_count=int(payload.get("station_count") or 0),
            correction_magnitude_ms=correction,
            conflict_index=payload.get("conflict_index"),
            uncertainty_ms=payload.get("uncertainty_ms"),
            confidence=payload.get("confidence"),
            fallback_reason=payload.get("fallback_reason"),
            duration_ms=max(0, duration_ms),
            baseline_cache_hit=cache_hit,
            exclusion_reasons=_exclusion_counts(payload, analysis_diagnostics),
            result_payload=payload,
            diagnostics={
                "public_effect": "none",
                "input_product": "model_nowcast_plus_station_residuals",
                "forbidden_inputs": ["raw_station_measurement", "forecast_output"],
                "rollout_stage_at_enqueue": job.rollout_stage,
                **analysis_diagnostics,
            },
            updated_at=finished_at,
        )
    )
    db.commit()
    return bool(result.rowcount)


def _fail_job(
    db,
    job: WeatherLiveWindJob,
    exc: Exception,
    *,
    now: datetime,
    settings: Settings,
) -> dict:
    terminal = job.attempt_count >= settings.live_wind_job_max_attempts
    status = "failed" if terminal else "retry_wait"
    available_at = now
    if not terminal:
        available_at = now + timedelta(
            seconds=retry_delay_seconds(
                job.attempt_count,
                initial_seconds=settings.live_wind_retry_initial_seconds,
                maximum_seconds=settings.live_wind_retry_max_seconds,
                identity=job.id,
            )
        )
    result = db.execute(
        update(WeatherLiveWindJob)
        .where(
            WeatherLiveWindJob.id == job.id,
            WeatherLiveWindJob.status == "processing",
            WeatherLiveWindJob.worker_token == job.worker_token,
        )
        .values(
            status=status,
            available_at=available_at,
            finished_at=now if terminal else None,
            heartbeat_at=now,
            worker_token=None,
            error_class=type(exc).__name__[:120],
            updated_at=now,
        )
    )
    db.commit()
    return {
        "job_id": str(job.id),
        "status": status if result.rowcount else "lease_lost",
        "error_class": type(exc).__name__,
        "available_at": available_at.isoformat(),
    }


def process_live_wind_job(
    db,
    job: WeatherLiveWindJob,
    *,
    cache: Cache | None = None,
    settings: Settings | None = None,
) -> dict:
    """Calculate one internal shadow result without changing public products."""
    cfg = settings or get_settings()
    started = time.monotonic()
    try:
        spot = db.scalar(
            select(Spot)
            .where(Spot.id == job.spot_id)
            .options(
                selectinload(Spot.region),
                selectinload(Spot.weather_profile),
            )
        )
        if spot is None or spot.status != "published":
            raise LookupError("spot is no longer active")

        from app.live.weather_contract import unavailable_live_wind
        from app.weather.exact_run import ExactRunAssetCache, ExactRunLoader, exact_shadow_baseline

        analysis_time = datetime.now(timezone.utc)
        if cfg.live_wind_exact_run_cache_dir:
            loader = ExactRunLoader(ExactRunAssetCache(
                cfg.live_wind_exact_run_cache_dir,
                require_persistent=cfg.app_env == "production" or cfg.live_wind_canary_mode,
                expected_id=cfg.live_wind_exact_run_cache_id,
                minimum_free_bytes=cfg.live_wind_exact_run_min_free_bytes,
            ))
            baseline, bundle = exact_shadow_baseline(loader, spot, at=analysis_time)
            bundle_manifest = bundle.manifest()
        else:
            baseline = unavailable_live_wind("availability_unproven")
            bundle_manifest = {"activation_eligible": False, "status": "cache_incomplete"}
        cache_hit = baseline.get("status") == "baseline"
        model_ids = tuple(baseline.get("_model_ids") or ())
        if not heartbeat_live_wind_job(db, job):
            return {"job_id": str(job.id), "status": "lease_lost"}

        from app.live.live_wind import analyze_live_wind_for_spot

        analysis_diagnostics: dict = {}
        analysis_diagnostics["exact_run_bundle"] = bundle_manifest
        analysis_diagnostics["dataset_bundle_hash"] = baseline.get("_exact_dataset_bundle_hash")
        analysis_diagnostics["sample_hash"] = baseline.get("_exact_sample_hash")
        analysis_diagnostics["activation_eligible"] = bool(
            bundle_manifest.get("activation_eligible") and baseline.get("status") == "baseline"
        )
        analysis_diagnostics["baseline_source"] = "exact_run_bundle"
        if baseline.get("status") == "baseline":
            analyzed = analyze_live_wind_for_spot(
                db, spot, baseline, model_ids=model_ids,
                analyzed_at=analysis_time, diagnostics_out=analysis_diagnostics,
            )
        else:
            analyzed = baseline
        payload = LiveWindRead.model_validate(analyzed).model_dump(mode="json")
        finished_at = datetime.now(timezone.utc)
        duration_ms = round((time.monotonic() - started) * 1000)
        completed = _complete_job(
            db,
            job,
            payload,
            cache_hit=cache_hit,
            duration_ms=duration_ms,
            spot=spot,
            finished_at=finished_at,
            analysis_diagnostics=analysis_diagnostics,
        )
        return {
            "job_id": str(job.id),
            "status": "succeeded" if completed else "lease_lost",
            "product_status": payload["status"],
            "station_count": payload["station_count"],
            "duration_ms": duration_ms,
            "public_effect": "none",
        }
    except Exception as exc:
        db.rollback()
        return _fail_job(
            db,
            job,
            exc,
            now=datetime.now(timezone.utc),
            settings=cfg,
        )


def run_live_wind_worker(
    db=None,
    *,
    limit: int | None = None,
    cache: Cache | None = None,
    settings: Settings | None = None,
) -> dict:
    """Drain a bounded batch; each failure yields before the next retry."""
    cfg = settings or get_settings()
    owns_session = db is None
    if owns_session:
        from app.db.session import SessionLocal

        db = SessionLocal()
    batch_size = max(1, min(limit or cfg.live_wind_worker_batch_size, 200))
    items = []
    try:
        for _ in range(batch_size):
            job = claim_live_wind_job(db, settings=cfg)
            if job is None:
                break
            items.append(
                process_live_wind_job(
                    db,
                    job,
                    cache=cache,
                    settings=cfg,
                )
            )
        return {
            "processed": len(items),
            "succeeded": sum(item["status"] == "succeeded" for item in items),
            "retry_wait": sum(item["status"] == "retry_wait" for item in items),
            "failed": sum(item["status"] == "failed" for item in items),
            "lease_lost": sum(item["status"] == "lease_lost" for item in items),
            "items": items,
            "public_effect": "none" if cfg.live_wind_rollout_stage in {"shadow", "internal"} else "gated",
        }
    finally:
        if owns_session:
            db.close()
