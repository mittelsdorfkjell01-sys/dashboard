"""Operational metrics, health checks and rollout readiness for LiveWind."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import math
from statistics import median

from sqlalchemy import func, select

from app.config import Settings, get_settings
from app.models import (
    Region,
    Spot,
    WeatherLiveWindJob,
    WeatherLiveWindHoldoutCase,
    WeatherLiveWindVerificationEvidence,
    WeatherObservation,
    WeatherObservationImportState,
    WeatherProviderHttpResource,
    WeatherStation,
    WeatherStationCatalogState,
    WeatherStationModelResidual,
)
from app.weather.coverage import build_database_coverage_report
from app.weather.live_wind_verification import candidate_policy_hash


def _utc(value: datetime | None, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(float(ordered[index]), 4)


def _distribution(values: list[float]) -> dict:
    return {
        "count": len(values),
        "mean": _mean(values),
        "median": round(float(median(values)), 4) if values else None,
        "p95": _percentile(values, 0.95),
        "max": round(max(values), 4) if values else None,
    }


def _wind_sector(payload: dict) -> int | None:
    value = payload.get("wind_direction_from_deg")
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return int((float(value) % 360 + 22.5) // 45) % 8


def summarize_live_wind_jobs(
    jobs: list,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> dict:
    """Deterministic metrics over persisted shadow evidence."""
    cfg = settings or get_settings()
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    completed = [job for job in jobs if job.status == "succeeded"]
    terminal_failures = [job for job in jobs if job.status == "failed"]
    fallbacks = [
        job
        for job in completed
        if job.product_status in {"baseline", "unavailable"}
    ]
    cache_values = [job.baseline_cache_hit for job in completed if job.baseline_cache_hit is not None]
    days = {
        _utc(job.analyzed_at or job.finished_at or job.cycle_at, generated_at).date()
        for job in completed
    }
    sectors = {
        sector
        for job in completed
        if (sector := _wind_sector(job.result_payload or {})) is not None
    }
    exclusion_reasons: Counter[str] = Counter()
    for job in completed:
        exclusion_reasons.update(
            {
                str(reason): int(count)
                for reason, count in (job.exclusion_reasons or {}).items()
            }
        )

    grouped = {
        "terrain": defaultdict(list),
        "region": defaultdict(list),
    }
    for job in jobs:
        grouped["terrain"][job.terrain_class or "unknown"].append(job)
        grouped["region"][job.region_key or "unassigned"].append(job)

    def group_metrics(rows: list) -> dict:
        successes = [row for row in rows if row.status == "succeeded"]
        group_fallbacks = [
            row
            for row in successes
            if row.product_status in {"baseline", "unavailable"}
        ]
        return {
            "analyses": len(successes),
            "failed_jobs": sum(row.status == "failed" for row in rows),
            "fallback_rate": (
                round(len(group_fallbacks) / len(successes), 4)
                if successes
                else None
            ),
            "mean_uncertainty_ms": _mean(
                [float(row.uncertainty_ms) for row in successes if row.uncertainty_ms is not None]
            ),
            "mean_correction_ms": _mean(
                [
                    float(row.correction_magnitude_ms)
                    for row in successes
                    if row.correction_magnitude_ms is not None
                ]
            ),
        }

    fallback_rate = len(fallbacks) / len(completed) if completed else 1.0
    exact_jobs = [job for job in completed if (
        getattr(job, "diagnostics", None) or {}
    ).get("activation_eligible") is True and (
        getattr(job, "diagnostics", None) or {}
    ).get("baseline_source") == "exact_run_bundle" and (
        getattr(job, "diagnostics", None) or {}
    ).get("dataset_bundle_hash") and (
        getattr(job, "diagnostics", None) or {}
    ).get("sample_hash")]
    exact_days = {job.analyzed_at.date().isoformat() for job in exact_jobs if job.analyzed_at}
    exact_sectors = {
        sector for job in exact_jobs
        if (sector := _wind_sector(job.result_payload or {})) is not None
    }
    exact_fallback_rate = (
        sum(job.product_status != "station_adjusted" for job in exact_jobs) / len(exact_jobs)
        if exact_jobs else 1.0
    )
    readiness_checks = {
        "minimum_distinct_days": len(exact_days) >= cfg.live_wind_readiness_min_days,
        "minimum_analyses": len(exact_jobs) >= cfg.live_wind_readiness_min_analyses,
        "minimum_weather_sectors": len(exact_sectors) >= cfg.live_wind_readiness_min_wind_sectors,
        "fallback_rate": bool(exact_jobs) and exact_fallback_rate <= cfg.live_wind_readiness_max_fallback_rate,
        "station_adjusted_evidence": any(
            job.product_status == "station_adjusted" for job in exact_jobs
        ),
        "exact_run_evidence": bool(exact_jobs),
        "no_terminal_job_failures": not terminal_failures,
    }
    return {
        "generated_at": generated_at.isoformat(),
        "jobs": {
            status: sum(job.status == status for job in jobs)
            for status in ("queued", "processing", "retry_wait", "succeeded", "failed")
        },
        "product_status": dict(
            sorted(Counter(job.product_status or "none" for job in completed).items())
        ),
        "exact_run_activation_eligible_jobs": len(exact_jobs),
        "legacy_capture_time_jobs": len(completed) - len(exact_jobs),
        "distinct_analysis_days": len(days),
        "weather_sector_count": len(sectors),
        "weather_sectors": sorted(sectors),
        "stations_per_analysis": _distribution(
            [float(job.station_count) for job in completed]
        ),
        "correction_magnitude_ms": _distribution(
            [
                float(job.correction_magnitude_ms)
                for job in completed
                if job.correction_magnitude_ms is not None
            ]
        ),
        "conflict_index": _distribution(
            [float(job.conflict_index) for job in completed if job.conflict_index is not None]
        ),
        "uncertainty_ms": _distribution(
            [float(job.uncertainty_ms) for job in completed if job.uncertainty_ms is not None]
        ),
        "duration_ms": _distribution(
            [float(job.duration_ms) for job in completed if job.duration_ms is not None]
        ),
        "fallback_rate": round(fallback_rate, 4),
        "cache_hit_rate": (
            round(sum(bool(value) for value in cache_values) / len(cache_values), 4)
            if cache_values
            else None
        ),
        "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
        "operational_results_by_terrain_class": {
            key: group_metrics(rows)
            for key, rows in sorted(grouped["terrain"].items())
        },
        "operational_results_by_region": {
            key: group_metrics(rows)
            for key, rows in sorted(grouped["region"].items())
        },
        "rollout_readiness": {
            "checks": readiness_checks,
            "ready_for_pilot_review": False,
            "accuracy_validation": "holdout_evidence_not_checked",
        },
    }


def _holdout_readiness(db, *, candidate_version: str, settings: Settings) -> dict:
    ranked = select(
        WeatherLiveWindHoldoutCase.eligibility_status.label("eligibility_status"),
        WeatherLiveWindHoldoutCase.model_valid_at.label("model_valid_at"),
        WeatherLiveWindHoldoutCase.target_station_id.label("target_station_id"),
        WeatherLiveWindHoldoutCase.payload["country"].astext.label("country"),
        WeatherLiveWindHoldoutCase.payload["terrain_class"].astext.label("terrain_class"),
        WeatherLiveWindHoldoutCase.payload["coastal_class"].astext.label("coastal_class"),
        WeatherLiveWindHoldoutCase.payload["wind_strength"].astext.label("wind_strength"),
        WeatherLiveWindHoldoutCase.payload["weather_regime"].astext.label("weather_regime"),
        WeatherLiveWindHoldoutCase.payload["wind_sector"].astext.label("wind_sector"),
        func.row_number().over(
            partition_by=WeatherLiveWindHoldoutCase.target_observation_id,
            order_by=(WeatherLiveWindHoldoutCase.created_at.desc(),
                      WeatherLiveWindHoldoutCase.id.desc()),
        ).label("rank"),
    ).where(WeatherLiveWindHoldoutCase.candidate_version == candidate_version).subquery()
    latest = db.execute(select(ranked).where(ranked.c.rank == 1)).all()
    counts = dict(Counter(row.eligibility_status for row in latest))
    eligible = counts.get("eligible", 0)
    eligible_rows = [row for row in latest if row.eligibility_status == "eligible"]
    evidence = db.scalar(
        select(WeatherLiveWindVerificationEvidence)
        .where(WeatherLiveWindVerificationEvidence.candidate_version == candidate_version)
        .order_by(WeatherLiveWindVerificationEvidence.computed_at.desc(),
                  WeatherLiveWindVerificationEvidence.id.desc())
        .limit(1)
    )
    gate_failures = list((evidence.metrics or {}).get("activation", {}).get("gate_reasons", [])) if evidence else []
    if not sum(counts.values()):
        status, reason = "no_cases", "holdout_cases_missing"
    elif not eligible:
        status, reason = "not_activation_eligible", "eligible_cases_missing"
    elif eligible < settings.live_wind_verification_min_samples:
        status, reason = "insufficient_evidence", "samples_low"
    elif evidence is None:
        status, reason = "verification_pending", "aggregate_evidence_missing"
    elif (evidence.policy or {}).get("leakage_audit") != "passed":
        status, reason = "gate_blocked", "leakage_audit_failed"
    elif "improvement_low" in gate_failures:
        status, reason = "gate_blocked", "statistical_improvement_not_reached"
    elif "confidence_interval_nonpositive" in gate_failures:
        status, reason = "gate_blocked", "confidence_bound_not_positive"
    elif evidence.status != "passed":
        status, reason = "insufficient_evidence" if evidence.status == "collecting" else "gate_blocked", evidence.reason
    elif (settings.live_wind_verification_max_subgroup_regression_ms is None
          or not settings.live_wind_verification_subgroup_policy_version):
        status, reason = "gate_blocked", "subgroup_regression_policy_missing"
    elif ((evidence.policy or {}).get("subgroup_policy_version")
          != settings.live_wind_verification_subgroup_policy_version
          or (evidence.policy or {}).get("maximum_subgroup_regression_ms")
          != settings.live_wind_verification_max_subgroup_regression_ms):
        status, reason = "gate_blocked", "subgroup_regression_policy_mismatch"
    elif (evidence.policy or {}).get("candidate_policy_hash") != candidate_policy_hash(
        candidate_version, settings.live_wind_verification_subgroup_policy_version,
        settings.live_wind_verification_max_subgroup_regression_ms):
        status, reason = "gate_blocked", "subgroup_regression_policy_mismatch"
    else:
        status, reason = "evidence_passed", "passed"
    return {
        "status": status, "reason": reason,
        "candidate_version": candidate_version,
        "case_counts": counts,
        "eligible_coverage": {
            "days": len({row.model_valid_at.date() for row in eligible_rows}),
            "stations": len({row.target_station_id for row in eligible_rows}),
            "countries": dict(Counter(row.country or "unknown" for row in eligible_rows)),
            "terrain_classes": dict(Counter(row.terrain_class or "unknown" for row in eligible_rows)),
            "coastal_classes": dict(Counter(row.coastal_class or "unknown" for row in eligible_rows)),
            "wind_strength": dict(Counter(row.wind_strength or "unknown" for row in eligible_rows)),
            "weather_regime": dict(Counter(row.weather_regime or "unknown" for row in eligible_rows)),
            "wind_sectors": dict(Counter(row.wind_sector or "unknown" for row in eligible_rows)),
        },
        "minimum_cases": settings.live_wind_verification_min_samples,
        "cases_remaining": max(0, settings.live_wind_verification_min_samples - eligible),
        "evidence_status": evidence.status if evidence else None,
        "evidence_gate_reasons": gate_failures,
        "evidence_context_hash": evidence.context_hash if evidence else None,
        "technical_readiness": "prepared" if sum(counts.values()) else "collection_missing",
        "pilot_readiness": "evidence_passed" if status == "evidence_passed" else "evidence_incomplete",
        "europe_seasonal_readiness": "evidence_incomplete",
    }


def _provider_doctor(db, *, now: datetime, settings: Settings) -> dict:
    from app.weather.observation_worker import provider_fetchers

    configured = set(provider_fetchers())
    rows = db.execute(
        select(WeatherStation, WeatherObservationImportState, Region.country)
        .join(Spot, Spot.id == WeatherStation.spot_id)
        .outerjoin(Region, Region.id == Spot.region_id)
        .outerjoin(
            WeatherObservationImportState,
            WeatherObservationImportState.station_id == WeatherStation.id,
        )
        .where(WeatherStation.active.is_(True))
    ).all()
    providers = {}
    alerts = []
    catalog_states = {
        item.provider: item
        for item in db.scalars(select(WeatherStationCatalogState)).all()
    }
    dwd_resources = db.scalars(select(WeatherProviderHttpResource).where(
        WeatherProviderHttpResource.provider == "dwd"
    )).all()
    for provider in sorted({station.provider for station, _, _ in rows} | configured):
        items = [
            (station, state, country)
            for station, state, country in rows
            if station.provider == provider
        ]
        current_by_country: Counter[str] = Counter()
        for station, _, country in items:
            if (
                station.last_observation_at
                and _utc(station.last_observation_at, now)
                >= now - timedelta(minutes=settings.live_wind_import_late_minutes * 2)
            ):
                current_by_country[str(country or "unknown").upper()] += 1
        current = sum(current_by_country.values())
        attempts = [
            _utc(state.last_attempt_at, now)
            for _, state, _ in items
            if state is not None and state.last_attempt_at is not None
        ]
        errors = sum(
            state is not None and state.status == "error"
            for _, state, _ in items
        )
        status = "ok"
        if provider not in configured:
            status = "not_configured"
            alerts.append({"severity": "critical", "code": "provider_not_configured", "provider": provider})
        elif items and not attempts:
            status = "never_imported"
            alerts.append({"severity": "critical", "code": "provider_never_imported", "provider": provider})
        elif attempts and max(attempts) < now - timedelta(minutes=settings.live_wind_import_late_minutes):
            status = "late"
            alerts.append({"severity": "critical", "code": "provider_import_late", "provider": provider})
        elif errors:
            status = "degraded"
            alerts.append({"severity": "warning", "code": "provider_import_errors", "provider": provider, "count": errors})
        providers[provider] = {
            "configured": provider in configured,
            "active_station_records": len(items),
            "current_stations": current,
            "current_stations_by_country": dict(sorted(current_by_country.items())),
            "last_import_attempt_at": max(attempts).isoformat() if attempts else None,
            "stations_in_error": errors,
            "status": status,
            "catalog_last_success_at": (
                catalog_states[provider].last_success_at.isoformat()
                if provider in catalog_states
                and catalog_states[provider].last_success_at else None
            ),
            "catalog_last_error_class": (
                catalog_states[provider].last_error_class
                if provider in catalog_states else None
            ),
        }
        catalog = catalog_states.get(provider)
        if provider not in {"dwd", "dmi"}:
            continue
        if catalog is None or catalog.last_success_at is None:
            alerts.append({
                "severity": "critical", "code": "station_catalog_never_succeeded",
                "provider": provider,
            })
        elif _utc(catalog.last_success_at, now) < now - timedelta(
            hours=settings.weather_station_catalog_late_hours
        ):
            alerts.append({
                "severity": "critical", "code": "station_catalog_late",
                "provider": provider,
            })
        elif catalog.last_error_class:
            alerts.append({
                "severity": "warning", "code": "station_catalog_error",
                "provider": provider,
                "error_class": catalog.last_error_class,
            })
    invalid_resources = sum(
        len(bytes(item.payload)) != item.payload_size_bytes
        or hashlib.sha256(bytes(item.payload)).hexdigest() != item.payload_sha256
        for item in dwd_resources
    )
    if not dwd_resources:
        alerts.append({"severity": "critical", "code": "dwd_validator_state_missing"})
    if invalid_resources:
        alerts.append({
            "severity": "critical", "code": "dwd_validator_payload_corrupt",
            "count": invalid_resources,
        })
    return {
        "ok": not any(item["severity"] == "critical" for item in alerts),
        "providers": providers,
        "dwd_validators": {
            "resources": len(dwd_resources),
            "with_etag": sum(bool(item.etag) for item in dwd_resources),
            "with_last_modified": sum(bool(item.last_modified) for item in dwd_resources),
            "invalid_payloads": invalid_resources,
            "last_checked_at": max(
                (item.last_checked_at for item in dwd_resources), default=None
            ).isoformat() if dwd_resources else None,
        },
        "alerts": alerts,
    }


def _scheduler_doctor(db, *, now: datetime, settings: Settings) -> dict:
    latest_job = db.scalar(select(func.max(WeatherLiveWindJob.created_at)))
    latest_success = db.scalar(
        select(func.max(WeatherLiveWindJob.finished_at)).where(
            WeatherLiveWindJob.status == "succeeded"
        )
    )
    oldest_due = db.scalar(
        select(func.min(WeatherLiveWindJob.available_at)).where(
            WeatherLiveWindJob.status.in_(("queued", "retry_wait")),
            WeatherLiveWindJob.available_at <= now,
        )
    )
    latest_import = db.scalar(select(func.max(WeatherObservationImportState.last_attempt_at)))
    failed_recent = int(
        db.scalar(
            select(func.count())
            .select_from(WeatherLiveWindJob)
            .where(
                WeatherLiveWindJob.status == "failed",
                WeatherLiveWindJob.finished_at >= now - timedelta(hours=24),
            )
        )
        or 0
    )
    stale_processing = int(
        db.scalar(
            select(func.count())
            .select_from(WeatherLiveWindJob)
            .where(
                WeatherLiveWindJob.status == "processing",
                WeatherLiveWindJob.heartbeat_at
                < now - timedelta(seconds=settings.live_wind_job_lease_seconds),
            )
        )
        or 0
    )
    alerts = []
    job_cutoff = now - timedelta(minutes=settings.live_wind_job_late_minutes)
    import_cutoff = now - timedelta(minutes=settings.live_wind_import_late_minutes)
    if latest_job is None:
        alerts.append({"severity": "critical", "code": "live_wind_scheduler_never_ran"})
    elif _utc(latest_job, now) < job_cutoff:
        alerts.append({"severity": "critical", "code": "live_wind_scheduler_late"})
    if latest_success is None:
        alerts.append({"severity": "critical", "code": "live_wind_worker_never_succeeded"})
    elif _utc(latest_success, now) < job_cutoff:
        alerts.append({"severity": "critical", "code": "live_wind_worker_late"})
    if latest_import is None:
        alerts.append({"severity": "critical", "code": "station_import_never_ran"})
    elif _utc(latest_import, now) < import_cutoff:
        alerts.append({"severity": "critical", "code": "station_import_late"})
    if oldest_due is not None and _utc(oldest_due, now) < job_cutoff:
        alerts.append({"severity": "critical", "code": "live_wind_queue_starved"})
    if failed_recent:
        alerts.append({"severity": "critical", "code": "live_wind_terminal_jobs", "count": failed_recent})
    if stale_processing:
        alerts.append({"severity": "warning", "code": "live_wind_stale_leases", "count": stale_processing})
    return {
        "ok": not alerts,
        "latest_job_at": _utc(latest_job, now).isoformat() if latest_job else None,
        "latest_success_at": _utc(latest_success, now).isoformat() if latest_success else None,
        "latest_station_import_at": _utc(latest_import, now).isoformat() if latest_import else None,
        "oldest_due_job_at": _utc(oldest_due, now).isoformat() if oldest_due else None,
        "failed_jobs_last_24h": failed_recent,
        "stale_processing_jobs": stale_processing,
        "alerts": alerts,
    }


def _raster_doctor(db, *, settings: Settings) -> dict:
    from pathlib import Path

    from app.forecast.gwa_producer import gwa_raster_doctor
    from app.forecast.microscale import microscale_raster_doctor

    probe = None
    spot = db.scalar(select(Spot).where(Spot.status == "published").order_by(Spot.id).limit(1))
    if spot is not None:
        try:
            from app.live.service import _spot_coords

            probe = _spot_coords(spot)
        except Exception:
            probe = None
    dem_path = Path(settings.glo30_dem_raster_dir) if settings.glo30_dem_raster_dir else None
    dem_files = (
        list(dem_path.glob("*.tif")) + list(dem_path.glob("*.tiff"))
        if dem_path is not None and dem_path.is_dir()
        else []
    )
    dem_problems = []
    if dem_path is None:
        dem_problems.append("GLO30_DEM_RASTER_DIR is not set")
    elif not dem_path.is_dir():
        dem_problems.append("GLO30_DEM_RASTER_DIR is not a readable directory")
    elif not dem_files:
        dem_problems.append("no GLO-30 DEM GeoTIFF files found")
    return {
        "gwa": gwa_raster_doctor(
            settings.gwa_raster_dir,
            filename_template=settings.gwa_raster_filename_template,
        ),
        "microscale": microscale_raster_doctor(
            settings.worldcover_raster_dir,
            settings.glo30_wbm_raster_dir,
            probe=probe,
        ),
        "glo30_dem": {
            "ok": not dem_problems,
            "mounted": dem_path is not None and dem_path.is_dir(),
            "file_count": len(dem_files),
            "problems": dem_problems,
        },
    }


def _product_boundary_audit(jobs: list) -> dict:
    violations = []
    for job in jobs:
        payload = job.result_payload or {}
        if payload.get("product_type") not in {None, "live_wind"}:
            violations.append({"job_id": str(job.id), "reason": "wrong_product_type"})
        source_types = {
            source.get("source_type")
            for source in payload.get("sources") or []
            if isinstance(source, dict)
        }
        if "station_measurement" in source_types:
            violations.append({"job_id": str(job.id), "reason": "raw_measurement_source"})
        if "forecast" in source_types or "adaptive_forecast" in source_types:
            violations.append({"job_id": str(job.id), "reason": "forecast_source"})
    return {
        "ok": not violations,
        "checked_jobs": len(jobs),
        "violations": violations[:100],
        "invariants": {
            "live_wind_is_not_measurement": not any(
                item["reason"] == "wrong_product_type" for item in violations
            ),
            "raw_measurement_is_not_live_wind_input": not any(
                item["reason"] == "raw_measurement_source" for item in violations
            ),
            "forecast_is_not_live_wind_input": not any(
                item["reason"] == "forecast_source" for item in violations
            ),
        },
    }


def build_live_wind_operations_report(
    db,
    *,
    days: int = 14,
    include_rasters: bool = True,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> dict:
    cfg = settings or get_settings()
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window_start = generated_at - timedelta(days=max(1, min(days, 180)))
    jobs = list(
        db.scalars(
            select(WeatherLiveWindJob)
            .where(WeatherLiveWindJob.created_at >= window_start)
            .order_by(WeatherLiveWindJob.created_at, WeatherLiveWindJob.id)
        ).all()
    )
    residual_count = int(
        db.scalar(
            select(func.count())
            .select_from(WeatherStationModelResidual)
            .where(
                WeatherStationModelResidual.qc_status.in_(("accepted", "degraded")),
                WeatherStationModelResidual.analyzed_at >= window_start,
            )
        )
        or 0
    )
    exact_residual_count = int(
        db.scalar(
            select(func.count())
            .select_from(WeatherStationModelResidual)
            .where(
                WeatherStationModelResidual.qc_status.in_(("accepted", "degraded")),
                WeatherStationModelResidual.analyzed_at >= window_start,
                WeatherStationModelResidual.baseline_version == "exact-run-bundle-v2",
                WeatherStationModelResidual.activation_eligible.is_(True),
                WeatherStationModelResidual.dataset_bundle_hash.is_not(None),
            )
        )
        or 0
    )
    residual_yield_rows = db.execute(
        select(
            WeatherStation.provider,
            Region.country,
            WeatherStationModelResidual.qc_status,
            func.count(WeatherStationModelResidual.id),
        )
        .select_from(WeatherStationModelResidual)
        .join(WeatherStation, WeatherStation.id == WeatherStationModelResidual.station_id)
        .join(Spot, Spot.id == WeatherStation.spot_id)
        .join(Region, Region.id == Spot.region_id)
        .where(
            WeatherStationModelResidual.analyzed_at >= window_start,
            WeatherStationModelResidual.baseline_version == "exact-run-bundle-v2",
        )
        .group_by(WeatherStation.provider, Region.country, WeatherStationModelResidual.qc_status)
        .order_by(WeatherStation.provider, Region.country, WeatherStationModelResidual.qc_status)
    ).all()
    recent_exact = db.scalars(
        select(WeatherStationModelResidual)
        .where(
            WeatherStationModelResidual.analyzed_at >= window_start,
            WeatherStationModelResidual.baseline_version == "exact-run-bundle-v2",
        )
        .order_by(WeatherStationModelResidual.analyzed_at.desc())
        .limit(2000)
    ).all()
    failure_reasons = Counter(
        str(reason)
        for row in recent_exact if row.qc_status not in {"accepted", "degraded"}
        for reason in (row.qc_reasons or [])
    )
    model_runs = Counter(
        f"{item.get('model_id')}:{item.get('model_run_at')}"
        for row in recent_exact
        for item in (row.model_runs or [])
        if isinstance(item, dict) and item.get("model_id") and item.get("model_run_at")
    )
    observation_delays = db.execute(
        select(WeatherObservation.observed_at, WeatherObservation.received_at,
               WeatherObservation.imported_at)
        .join(WeatherStationModelResidual,
              WeatherStationModelResidual.observation_id == WeatherObservation.id)
        .where(
            WeatherStationModelResidual.analyzed_at >= window_start,
            WeatherStationModelResidual.baseline_version == "exact-run-bundle-v2",
        )
        .order_by(WeatherStationModelResidual.analyzed_at.desc())
        .limit(2000)
    ).all()
    received_delays = [max(0.0, (received-observed).total_seconds()/60)
                       for observed, received, _ in observation_delays if received]
    imported_delays = [max(0.0, (imported-observed).total_seconds()/60)
                       for observed, _, imported in observation_delays if imported]
    metrics = summarize_live_wind_jobs(jobs, now=generated_at, settings=cfg)
    holdouts = _holdout_readiness(db, candidate_version=cfg.live_wind_candidate_version, settings=cfg)
    metrics["rollout_readiness"]["accuracy_validation"] = holdouts["status"]
    metrics["rollout_readiness"]["ready_for_pilot_review"] = (
        all(metrics["rollout_readiness"]["checks"].values())
        and holdouts["status"] == "evidence_passed"
    )
    provider = _provider_doctor(db, now=generated_at, settings=cfg)
    scheduler = _scheduler_doctor(db, now=generated_at, settings=cfg)
    boundary = _product_boundary_audit(jobs)
    report = {
        "generated_at": generated_at.isoformat(),
        "window": {"start": window_start.isoformat(), "end": generated_at.isoformat(), "days": days},
        "last_successful_shadow_cycle_at": (
            max((job.finished_at for job in jobs
                 if job.status == "succeeded" and job.finished_at), default=None).isoformat()
            if any(job.status == "succeeded" and job.finished_at for job in jobs) else None
        ),
        "operational_acceptance": {
            "migration": "not_verified_on_staging",
            "runner": "not_verified",
            "mount_persistence": "not_verified",
            "canary": "not_tracked_by_database",
            "pilot_evidence": "incomplete" if holdouts["status"] != "evidence_passed" else "review_required",
            "europe_evidence": "incomplete",
        },
        "rollout": {
            "stage": cfg.live_wind_rollout_stage,
            "force_baseline": cfg.live_wind_force_baseline,
            "enabled_regions": list(cfg.live_wind_enabled_region_slugs),
            "station_adjustment_public": (
                not cfg.live_wind_force_baseline
                and cfg.live_wind_rollout_stage in {"pilot", "regional", "global"}
            ),
        },
        "coverage": build_database_coverage_report(db, now=generated_at),
        "metrics": metrics,
        "holdout_verification": holdouts,
        "model_residual_evidence": {
            "accepted_or_degraded_in_window": residual_count,
            "exact_run_eligible_in_window": exact_residual_count,
            "production_baseline_loader": (
                "exact-run-loader-v2" if cfg.live_wind_exact_run_cache_dir else "not_configured"
            ),
            "persistent_cache_configured": bool(cfg.live_wind_exact_run_cache_dir),
            "activation_blocker": exact_residual_count == 0,
            "yield_by_station_provider_country": [
                {"provider": provider_name, "country": country, "qc_status": status,
                 "count": count}
                for provider_name, country, status, count in residual_yield_rows
            ],
            "missing_reasons_recent_sample": dict(failure_reasons.most_common(20)),
            "model_runs_recent_sample": dict(model_runs.most_common(20)),
            "recent_sample_size": len(recent_exact),
            "station_age_at_receipt_minutes": _distribution(received_delays),
            "station_age_at_import_minutes": _distribution(imported_delays),
        },
        "doctors": {"providers": provider, "scheduler": scheduler},
        "product_boundary_audit": boundary,
        "adaptive_forecast": {
            "allowed": False,
            "recommendation": "do_not_start",
            "reasons": [
                ("held_out_live_wind_accuracy_evaluation_missing"
                 if holdouts["status"] != "evidence_passed" else "uncertainty_calibration_missing"),
                "forecast_impulse_contract_not_implemented",
                *(["reproducible_station_baseline_loader_missing"] if not cfg.live_wind_exact_run_cache_dir else []),
                *(["exact_run_station_residual_evidence_missing"] if exact_residual_count == 0 else []),
            ],
        },
    }
    if include_rasters:
        report["doctors"]["rasters"] = _raster_doctor(db, settings=cfg)
    return report
