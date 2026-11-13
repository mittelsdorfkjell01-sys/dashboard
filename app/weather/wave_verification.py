"""Cost-free wave forecast archiving, matching and deterministic scoring."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from statistics import mean
from typing import Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models.wave_verification import (
    WaveForecastSample,
    WaveObservation,
    WaveObservationPlatform,
)
from app.models.weather_field import WeatherFieldRun
from app.spatial_fields.sampling import bilinear_scalar, bilinear_uv


POLICY_VERSION = "wave-verification-v1"
ACCEPTED_QC = frozenset({"good", "probably_good"})
LEAD_BUCKETS = (
    (0, 24, "0-24h"),
    (24, 48, "24-48h"),
    (48, 72, "48-72h"),
    (72, 120, "72-120h"),
    (120, 168, "120-168h"),
    (168, 241, "168-240h"),
)
PARAMETER_TOLERANCES = {
    "significant_height": 0.5,
    "period": 2.0,
    "direction": 30.0,
}


def lead_bucket(hours: int) -> str:
    if hours < 0:
        raise ValueError("lead hours must not be negative")
    for lower, upper, label in LEAD_BUCKETS:
        if lower <= hours < upper:
            return label
    return "240h+"


def forecast_semantics(model_key: str) -> tuple[str, str]:
    """Return period/direction semantics without conflating NOAA and DWD fields."""

    if model_key in {"dwd-ewam", "dwd-gwam"}:
        return "energy_period_tm10", "mean_direction_from"
    if model_key == "noaa-gfs-wave":
        return "primary_wave_mean_period", "primary_wave_direction_from"
    return "unknown", "unknown"


def load_active_wave_platforms(db, *, limit: int = 2000) -> list[WaveObservationPlatform]:
    return list(
        db.scalars(
            select(WaveObservationPlatform)
            .where(WaveObservationPlatform.active.is_(True))
            .order_by(
                WaveObservationPlatform.provider_key,
                WaveObservationPlatform.external_id,
            )
            .limit(limit)
        ).all()
    )


def _canonical_hash(payload: Mapping) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def archive_wave_source_slice(
    db,
    *,
    run,
    model,
    source,
    platforms: Sequence[WaveObservationPlatform],
) -> int:
    """Persist small point evidence while the free provider grid is in memory."""

    period_semantic, direction_semantic = forecast_semantics(model.model_key)
    period_grid = source.scalar_fields.get(
        "primary_wave_period"
        if model.model_key == "noaa-gfs-wave"
        else "total_wave_period"
    )
    rows: list[dict] = []
    for platform in platforms:
        if not (
            run.coverage["west"] <= platform.longitude <= run.coverage["east"]
            and run.coverage["south"] <= platform.latitude <= run.coverage["north"]
        ):
            continue
        vector = bilinear_uv(
            source.u.longitudes,
            source.u.latitudes,
            source.u.values,
            source.v.values,
            longitude=platform.longitude,
            latitude=platform.latitude,
        )
        if vector is None:
            continue
        period = None
        if period_grid is not None:
            period = bilinear_scalar(
                period_grid.longitudes,
                period_grid.latitudes,
                period_grid.values,
                longitude=platform.longitude,
                latitude=platform.latitude,
            )
        lead_hours = int((source.valid_time - run.model_run_at).total_seconds() // 3600)
        evidence = {
            "platform_id": str(platform.id),
            "provider": model.provider_key,
            "model": model.model_key,
            "model_run": run.model_run_at.isoformat(),
            "valid_at": source.valid_time.isoformat(),
            "processing_version": run.processing_version,
            "latitude": platform.latitude,
            "longitude": platform.longitude,
            "height_m": vector.speed_ms,
            "period_s": period,
            "period_semantic": period_semantic,
            "direction_from_deg": vector.direction_from_deg,
            "direction_semantic": direction_semantic,
            "source_urls": list(source.source_urls),
        }
        rows.append(
            {
                "platform_id": platform.id,
                "field_run_id": run.id,
                "provider_key": model.provider_key,
                "model_key": model.model_key,
                "model_run_at": run.model_run_at,
                "valid_at": source.valid_time,
                "lead_hours": lead_hours,
                "processing_version": run.processing_version,
                "latitude": platform.latitude,
                "longitude": platform.longitude,
                "significant_height_m": round(vector.speed_ms, 4),
                "period_s": round(period, 4) if period is not None else None,
                "period_semantic": period_semantic,
                "direction_from_deg": (
                    round(vector.direction_from_deg, 4)
                    if vector.direction_from_deg is not None
                    else None
                ),
                "direction_semantic": direction_semantic,
                "interpolation": "bilinear_native_grid",
                "evidence_sha256": _canonical_hash(evidence),
                "sample_metadata": {"source_urls": list(source.source_urls)},
            }
        )
    if not rows:
        return 0
    statement = (
        insert(WaveForecastSample)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_wave_forecast_sample_identity")
        .returning(WaveForecastSample.id)
    )
    return len(db.scalars(statement).all())


def _utc(value: datetime | str) -> datetime:
    instant = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("wave observation timestamps must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _optional_float(value, *, minimum: float, maximum: float) -> float | None:
    if value in (None, ""):
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise ValueError(f"wave value {parsed!r} is outside {minimum}..{maximum}")
    return parsed


def normalize_qc(value) -> str:
    normalized = str(value or "").strip().casefold()
    return {
        "1": "good",
        "2": "probably_good",
        "5": "bad",
        "8": "interpolated",
        "good": "good",
        "probably_good": "probably_good",
        "interpolated": "interpolated",
        "bad": "bad",
    }.get(normalized, "unknown")


def import_wave_observation_rows(
    db,
    rows: Iterable[Mapping],
    *,
    provider_key: str,
    region_code: str,
    source_revision: str,
    source_file: str | None = None,
    source_sha256: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Import a provider-neutral CSV-shaped stream without paid API dependencies."""

    platforms: dict[str, WaveObservationPlatform] = {}
    prepared: list[dict] = []
    rejected = 0
    for raw in rows:
        try:
            external_id = str(
                raw.get("platform_id") or raw.get("external_id") or ""
            ).strip()
            if not external_id:
                raise ValueError("platform_id is required")
            latitude = _optional_float(raw.get("latitude"), minimum=-90, maximum=90)
            longitude = _optional_float(raw.get("longitude"), minimum=-180, maximum=180)
            if latitude is None or longitude is None:
                raise ValueError("latitude and longitude are required")
            platform = platforms.get(external_id)
            if platform is None:
                platform = db.scalar(
                    select(WaveObservationPlatform).where(
                        WaveObservationPlatform.provider_key == provider_key,
                        WaveObservationPlatform.external_id == external_id,
                    )
                )
                if platform is None:
                    platform = WaveObservationPlatform(
                        provider_key=provider_key,
                        external_id=external_id,
                        name=(str(raw.get("platform_name") or "").strip() or None),
                        latitude=latitude,
                        longitude=longitude,
                        region_code=region_code,
                        location_class=str(raw.get("location_class") or "unknown"),
                        active=True,
                        platform_metadata={},
                    )
                    db.add(platform)
                    db.flush()
                else:
                    platform.latitude = latitude
                    platform.longitude = longitude
                    platform.region_code = region_code
                    if raw.get("platform_name"):
                        platform.name = str(raw["platform_name"])
                platforms[external_id] = platform
            observed_at = _utc(raw.get("observed_at") or raw.get("time"))
            height = _optional_float(
                raw.get("significant_height_m"), minimum=0, maximum=40
            )
            period = _optional_float(raw.get("period_s"), minimum=0.01, maximum=40)
            direction = _optional_float(
                raw.get("direction_from_deg"), minimum=0, maximum=359.999999
            )
            if height is None and period is None and direction is None:
                raise ValueError("observation has no wave values")
            prepared.append(
                {
                    "platform_id": platform.id,
                    "observed_at": observed_at,
                    "latitude": latitude,
                    "longitude": longitude,
                    "significant_height_m": height,
                    "period_s": period,
                    "period_semantic": (
                        str(raw.get("period_semantic") or "").strip() or None
                    ),
                    "direction_from_deg": direction,
                    "direction_semantic": (
                        str(raw.get("direction_semantic") or "").strip() or None
                    ),
                    "qc_status": normalize_qc(raw.get("qc_status")),
                    "source_revision": source_revision,
                    "source_file": source_file,
                    "source_sha256": source_sha256,
                    "raw_values": {},
                }
            )
        except (TypeError, ValueError):
            rejected += 1
    if dry_run:
        db.rollback()
        return {
            "dry_run": True,
            "platforms": len(platforms),
            "accepted": len(prepared),
            "rejected": rejected,
            "persisted": 0,
        }
    persisted = 0
    if prepared:
        statement = (
            insert(WaveObservation)
            .values(prepared)
            .on_conflict_do_nothing(constraint="uq_wave_observation_identity")
            .returning(WaveObservation.id)
        )
        persisted = len(db.scalars(statement).all())
    db.commit()
    return {
        "dry_run": False,
        "platforms": len(platforms),
        "accepted": len(prepared),
        "rejected": rejected,
        "persisted": persisted,
    }


@dataclass(frozen=True)
class WavePair:
    model_key: str
    parameter: str
    lead_bucket: str
    region_code: str
    location_class: str
    valid_at: datetime
    forecast: float
    observed: float


def _signed_direction_error(forecast: float, observed: float) -> float:
    return (forecast - observed + 180.0) % 360.0 - 180.0


def score_pairs(rows: Sequence[WavePair]) -> dict:
    if not rows:
        raise ValueError("at least one matched wave pair is required")
    parameter = rows[0].parameter
    signed_errors = [
        _signed_direction_error(row.forecast, row.observed)
        if parameter == "direction"
        else row.forecast - row.observed
        for row in rows
    ]
    absolute_errors = [abs(value) for value in signed_errors]
    observed = [row.observed for row in rows]
    forecast = [row.forecast for row in rows]
    bias = mean(signed_errors)
    rmse = math.sqrt(mean([value * value for value in signed_errors]))
    observed_mean = mean(observed)
    error_spread = math.sqrt(mean([(value - bias) ** 2 for value in signed_errors]))
    scatter_index = (
        error_spread / abs(observed_mean)
        if parameter != "direction" and abs(observed_mean) > 1e-9
        else None
    )
    correlation = None
    if parameter != "direction" and len(rows) > 1:
        forecast_mean = mean(forecast)
        numerator = sum(
            (left - forecast_mean) * (right - observed_mean)
            for left, right in zip(forecast, observed, strict=True)
        )
        denominator = math.sqrt(
            sum((value - forecast_mean) ** 2 for value in forecast)
            * sum((value - observed_mean) ** 2 for value in observed)
        )
        if denominator > 0:
            correlation = numerator / denominator
    tolerance = PARAMETER_TOLERANCES[parameter]
    return {
        "sample_count": len(rows),
        "distinct_days": len({row.valid_at.date() for row in rows}),
        "bias": bias,
        "mae": mean(absolute_errors),
        "rmse": rmse,
        "correlation": correlation,
        "scatter_index": scatter_index,
        "within_tolerance_ratio": sum(
            value <= tolerance for value in absolute_errors
        )
        / len(rows),
        "metrics": {
            "tolerance": tolerance,
            "observed_mean": observed_mean,
            "forecast_mean": mean(forecast),
        },
    }


def _nearest_observation(
    observations: Sequence[WaveObservation],
    times: Sequence[datetime],
    target: datetime,
    tolerance: timedelta,
) -> WaveObservation | None:
    index = bisect_left(times, target)
    candidates = observations[max(0, index - 1) : index + 1]
    if not candidates:
        return None
    nearest = min(candidates, key=lambda row: abs(row.observed_at - target))
    return nearest if abs(nearest.observed_at - target) <= tolerance else None


def evaluate_wave_verification(
    db,
    *,
    start: datetime,
    end: datetime,
    model_keys: Sequence[str] | None = None,
    tolerance_minutes: int = 30,
    minimum_direction_height_m: float = 0.5,
) -> dict:
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError("start/end must be ordered timezone-aware instants")
    forecast_query = (
        select(WaveForecastSample, WaveObservationPlatform)
        .join(
            WaveObservationPlatform,
            WaveObservationPlatform.id == WaveForecastSample.platform_id,
        )
        .join(WeatherFieldRun, WeatherFieldRun.id == WaveForecastSample.field_run_id)
        .where(
            WaveForecastSample.valid_at >= start,
            WaveForecastSample.valid_at <= end,
            WeatherFieldRun.status == "ready",
        )
        .order_by(WaveForecastSample.platform_id, WaveForecastSample.valid_at)
    )
    if model_keys:
        forecast_query = forecast_query.where(
            WaveForecastSample.model_key.in_(tuple(model_keys))
        )
    forecast_rows = list(db.execute(forecast_query).all())
    platform_ids = {sample.platform_id for sample, _platform in forecast_rows}
    observations: dict = defaultdict(list)
    if platform_ids:
        for observation in db.scalars(
            select(WaveObservation)
            .where(
                WaveObservation.platform_id.in_(platform_ids),
                WaveObservation.observed_at >= start - timedelta(minutes=tolerance_minutes),
                WaveObservation.observed_at <= end + timedelta(minutes=tolerance_minutes),
                WaveObservation.qc_status.in_(tuple(ACCEPTED_QC)),
            )
            .order_by(WaveObservation.platform_id, WaveObservation.observed_at)
        ).all():
            observations[observation.platform_id].append(observation)
    observation_times = {
        platform_id: [row.observed_at for row in rows]
        for platform_id, rows in observations.items()
    }
    pairs: list[WavePair] = []
    matched_platform_ids: set = set()
    skipped = defaultdict(int)
    tolerance = timedelta(minutes=tolerance_minutes)
    for sample, platform in forecast_rows:
        candidates = observations.get(sample.platform_id, ())
        observation = _nearest_observation(
            candidates,
            observation_times.get(sample.platform_id, ()),
            sample.valid_at,
            tolerance,
        )
        if observation is None:
            skipped["no_observation_in_tolerance"] += 1
            continue
        common = {
            "model_key": sample.model_key,
            "lead_bucket": lead_bucket(sample.lead_hours),
            "region_code": platform.region_code,
            "location_class": platform.location_class,
            "valid_at": sample.valid_at,
        }
        pair_count_before = len(pairs)
        if (
            sample.significant_height_m is not None
            and observation.significant_height_m is not None
        ):
            pairs.append(
                WavePair(
                    parameter="significant_height",
                    forecast=sample.significant_height_m,
                    observed=observation.significant_height_m,
                    **common,
                )
            )
        if sample.period_s is not None and observation.period_s is not None:
            if sample.period_semantic == observation.period_semantic:
                pairs.append(
                    WavePair(
                        parameter="period",
                        forecast=sample.period_s,
                        observed=observation.period_s,
                        **common,
                    )
                )
            else:
                skipped["period_semantic_mismatch"] += 1
        if (
            sample.direction_from_deg is not None
            and observation.direction_from_deg is not None
            and (observation.significant_height_m or 0) >= minimum_direction_height_m
        ):
            if sample.direction_semantic == observation.direction_semantic:
                pairs.append(
                    WavePair(
                        parameter="direction",
                        forecast=sample.direction_from_deg,
                        observed=observation.direction_from_deg,
                        **common,
                    )
                )
            else:
                skipped["direction_semantic_mismatch"] += 1
        if len(pairs) > pair_count_before:
            matched_platform_ids.add(sample.platform_id)
    grouped: dict[tuple, list[WavePair]] = defaultdict(list)
    for pair in pairs:
        grouped[
            (
                pair.model_key,
                pair.parameter,
                pair.lead_bucket,
                pair.region_code,
                pair.location_class,
            )
        ].append(pair)
    scores = []
    for key, group in sorted(grouped.items()):
        model_key, parameter, bucket, region_code, location_class = key
        scores.append(
            {
                "model_key": model_key,
                "parameter": parameter,
                "lead_bucket": bucket,
                "region_code": region_code,
                "location_class": location_class,
                **score_pairs(group),
            }
        )
    active_platforms = db.scalars(
        select(WaveObservationPlatform).where(
            WaveObservationPlatform.active.is_(True)
        )
    ).all()
    sampled_platform_ids = {
        sample.platform_id for sample, _platform in forecast_rows
    }
    coverage_by_region: dict[str, dict] = defaultdict(
        lambda: {
            "active_platforms": 0,
            "sampled_platforms": 0,
            "platforms_with_accepted_observations": 0,
            "matched_platforms": 0,
        }
    )
    platform_regions = {
        platform.id: platform.region_code for platform in active_platforms
    }
    for platform in active_platforms:
        coverage_by_region[platform.region_code]["active_platforms"] += 1
    for platform_id in sampled_platform_ids:
        region_code = platform_regions.get(platform_id)
        if region_code is not None:
            coverage_by_region[region_code]["sampled_platforms"] += 1
    for platform_id in observations:
        region_code = platform_regions.get(platform_id)
        if region_code is not None:
            coverage_by_region[region_code][
                "platforms_with_accepted_observations"
            ] += 1
    for platform_id in matched_platform_ids:
        region_code = platform_regions.get(platform_id)
        if region_code is not None:
            coverage_by_region[region_code]["matched_platforms"] += 1
    return {
        "policy_version": POLICY_VERSION,
        "dataset_start": start.isoformat(),
        "dataset_end": end.isoformat(),
        "forecast_samples": len(forecast_rows),
        "matched_values": len(pairs),
        "score_groups": len(scores),
        "skipped": dict(sorted(skipped.items())),
        "coverage": {
            "active_platforms": len(active_platforms),
            "sampled_platforms": len(sampled_platform_ids),
            "platforms_with_accepted_observations": len(observations),
            "matched_platforms": len(matched_platform_ids),
            "regions": [
                {"region_code": region_code, **counts}
                for region_code, counts in sorted(coverage_by_region.items())
            ],
        },
        "configuration": {
            "tolerance_minutes": tolerance_minutes,
            "minimum_direction_height_m": minimum_direction_height_m,
            "accepted_qc": sorted(ACCEPTED_QC),
            "model_keys": list(model_keys or []),
        },
        "scores": scores,
    }
