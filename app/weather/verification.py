"""Forecast verification and conservative, measurement-backed calibration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, median
import math

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import WeatherForecastSample, WeatherModelCalibration, WeatherObservation, WeatherStation

# 30 samples can cover only five hours at a ten-minute cadence and is too easy
# to overfit. Sixty is still deliberately modest for local preparation; an
# activation additionally needs a chronological holdout improvement.
MIN_CALIBRATION_SAMPLES = 60
CALIBRATION_DECISION_VERSION = "holdout-v1"


def lead_bucket(hours: float) -> str:
    if hours <= 48:
        return "0-48h"
    if hours <= 120:
        return "49-120h"
    return "121-240h"


@dataclass(frozen=True)
class CalibrationStats:
    sample_count: int
    bias_ms: float
    mae_ms: float
    weight_multiplier: float


@dataclass(frozen=True)
class VerificationMetrics:
    sample_count: int
    wind_mae_ms: float
    wind_bias_ms: float
    direction_mae_deg: float | None
    gust_mae_ms: float | None


@dataclass(frozen=True)
class CalibrationDecision:
    approved: bool
    version: str
    reason: str
    training_count: int
    holdout_count: int
    baseline_mae_ms: float | None
    calibrated_mae_ms: float | None


@dataclass(frozen=True)
class BenchmarkMetrics:
    spot_id: str
    model_family: str
    lead_bucket: str
    candidate: VerificationMetrics
    single_model: VerificationMetrics | None
    uncalibrated_consensus: VerificationMetrics | None
    persistence: VerificationMetrics | None


def circular_error_deg(predicted: float, observed: float) -> float:
    return abs((float(predicted) - float(observed) + 180.0) % 360.0 - 180.0)


def verification_metrics(rows: list[dict]) -> VerificationMetrics | None:
    clean = [row for row in rows if all(math.isfinite(float(row[key])) for key in ("wind_pred", "wind_obs"))]
    if not clean:
        return None
    errors = [float(row["wind_pred"]) - float(row["wind_obs"]) for row in clean]
    direction = [circular_error_deg(row["direction_pred"], row["direction_obs"])
                 for row in clean if row.get("direction_pred") is not None and row.get("direction_obs") is not None]
    gust = [abs(float(row["gust_pred"]) - float(row["gust_obs"]))
            for row in clean if row.get("gust_pred") is not None and row.get("gust_obs") is not None]
    return VerificationMetrics(len(clean), round(mean(abs(v) for v in errors), 3), round(mean(errors), 3),
                               round(mean(direction), 3) if direction else None,
                               round(mean(gust), 3) if gust else None)


def evaluate_calibration_holdout(rows: list[dict], *, holdout_fraction: float = 0.25) -> CalibrationDecision:
    """Chronological split; approve only a speed improvement without direction regression."""
    ordered = sorted(rows, key=lambda row: row["valid_at"])
    split = max(1, int(len(ordered) * (1 - holdout_fraction)))
    training, holdout = ordered[:split], ordered[split:]
    if len(training) < MIN_CALIBRATION_SAMPLES or len(holdout) < 20:
        return CalibrationDecision(False, CALIBRATION_DECISION_VERSION, "insufficient_samples",
                                   len(training), len(holdout), None, None)
    baseline = verification_metrics(holdout)
    calibrated_rows = [{
        **row,
        "wind_pred": row["wind_calibrated"],
        "direction_pred": row.get("direction_calibrated", row.get("direction_pred")),
    } for row in holdout]
    calibrated = verification_metrics(calibrated_rows)
    if baseline is None or calibrated is None:
        return CalibrationDecision(False, CALIBRATION_DECISION_VERSION, "invalid_holdout", len(training), len(holdout), None, None)
    direction_regressed = (calibrated.direction_mae_deg is not None and baseline.direction_mae_deg is not None
                           and calibrated.direction_mae_deg > baseline.direction_mae_deg + 1.0)
    approved = calibrated.wind_mae_ms < baseline.wind_mae_ms and not direction_regressed
    reason = "holdout_improved" if approved else ("direction_regressed" if direction_regressed else "holdout_not_improved")
    return CalibrationDecision(approved, CALIBRATION_DECISION_VERSION, reason, len(training), len(holdout),
                               baseline.wind_mae_ms, calibrated.wind_mae_ms)


def grouped_benchmarks(rows: list[dict]) -> list[BenchmarkMetrics]:
    """Compare candidate, single-model, raw consensus and persistence by cohort."""
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (str(row["spot_id"]), str(row["model_family"]), lead_bucket(float(row["lead_hours"])))
        grouped[key].append(row)
    output = []
    for (spot_id, family, bucket), values in sorted(grouped.items()):
        def metrics_for(column: str) -> VerificationMetrics | None:
            subset = [{**row, "wind_pred": row[column]} for row in values if row.get(column) is not None]
            return verification_metrics(subset)
        candidate = metrics_for("wind_pred")
        if candidate is not None:
            output.append(BenchmarkMetrics(
                spot_id, family, bucket, candidate, metrics_for("single_model_pred"),
                metrics_for("uncalibrated_consensus_pred"), metrics_for("persistence_pred")))
    return output


def calibration_stats(errors: list[float], peer_mae: float | None = None) -> CalibrationStats | None:
    """Robust stats for errors defined as forecast minus observation."""
    clean = [float(value) for value in errors if isinstance(value, (int, float))]
    if len(clean) < MIN_CALIBRATION_SAMPLES:
        return None
    bias = median(clean)
    mae = median(abs(value) for value in clean)
    # Never let historical fitting dominate the meteorological family weights.
    multiplier = 1.0 if not peer_mae or mae <= 0 else max(0.5, min(2.0, peer_mae / mae))
    return CalibrationStats(len(clean), round(bias, 3), round(mae, 3), round(multiplier, 3))


def load_calibrations(db, spot_id) -> dict[tuple[str, str], WeatherModelCalibration]:
    if not hasattr(db, "scalars"):
        return {}
    rows = db.scalars(select(WeatherModelCalibration).where(WeatherModelCalibration.spot_id == spot_id)).all()
    return {(row.model_id, row.lead_bucket): row for row in rows
            if row.sample_count >= MIN_CALIBRATION_SAMPLES
            and getattr(row, "decision_status", "legacy_active") in {"active", "legacy_active"}}


def store_forecast_samples(db, spot_id, raw: dict, models: list[str], issued_at: datetime) -> int:
    """Persist raw per-model hourly forecasts only for spots linked to a station."""
    if not hasattr(db, "scalar") or not hasattr(db, "execute"):
        return 0
    if db.scalar(select(WeatherStation.id).where(WeatherStation.spot_id == spot_id, WeatherStation.active.is_(True)).limit(1)) is None:
        return 0
    hourly = raw.get("hourly") or {}
    times = hourly.get("time") or []
    multi = len(models) > 1
    rows = []
    for index, value in enumerate(times):
        try:
            valid_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            valid_at = valid_at.replace(tzinfo=timezone.utc) if valid_at.tzinfo is None else valid_at.astimezone(timezone.utc)
        except ValueError:
            continue
        lead = max(0, round((valid_at - issued_at).total_seconds() / 3600))
        for model in models:
            suffix = f"_{model}" if multi else ""
            speed_col = hourly.get(f"wind_speed_10m{suffix}") or []
            dir_col = hourly.get(f"wind_direction_10m{suffix}") or []
            gust_col = hourly.get(f"wind_gusts_10m{suffix}") or []
            speed = speed_col[index] if index < len(speed_col) else None
            direction = dir_col[index] if index < len(dir_col) else None
            if not isinstance(speed, (int, float)) or not isinstance(direction, (int, float)):
                continue
            rows.append({"spot_id": spot_id, "model_id": model, "issued_at": issued_at,
                         "valid_at": valid_at, "lead_hours": lead, "wind_speed_ms": float(speed),
                         "wind_gust_ms": float(gust_col[index]) if index < len(gust_col) and isinstance(gust_col[index], (int, float)) else None,
                         "wind_direction_deg": float(direction) % 360})
    if rows:
        stmt = insert(WeatherForecastSample).values(rows).on_conflict_do_nothing(
            constraint="uq_weather_forecast_sample"
        )
        db.execute(stmt)
        db.commit()
    return len(rows)


def recompute_calibrations(db, *, lookback_days: int = 90) -> int:
    """Match forecasts to observations within 20 minutes and refresh robust stats."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(7, min(lookback_days, 365)))
    stations = db.scalars(select(WeatherStation).where(WeatherStation.active.is_(True))).all()
    updated = 0
    for station in stations:
        observations = db.scalars(select(WeatherObservation).where(
            WeatherObservation.station_id == station.id, WeatherObservation.observed_at >= cutoff
        )).all()
        samples = db.scalars(select(WeatherForecastSample).where(
            WeatherForecastSample.spot_id == station.spot_id, WeatherForecastSample.valid_at >= cutoff
        )).all()
        grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
        for sample in samples:
            nearest = min(observations, key=lambda row: abs((row.observed_at - sample.valid_at).total_seconds()), default=None)
            if nearest is None or abs((nearest.observed_at - sample.valid_at).total_seconds()) > 1200:
                continue
            grouped[(sample.model_id, lead_bucket(sample.lead_hours))].append(sample.wind_speed_ms - nearest.wind_speed_ms)
        provisional = {key: calibration_stats(errors) for key, errors in grouped.items()}
        peer_mae = median(s.mae_ms for s in provisional.values() if s is not None) if any(provisional.values()) else None
        for (model_id, bucket), errors in grouped.items():
            stats = calibration_stats(errors, peer_mae)
            if stats is None:
                continue
            stmt = insert(WeatherModelCalibration).values(
                spot_id=station.spot_id, model_id=model_id, lead_bucket=bucket,
                sample_count=stats.sample_count, bias_ms=stats.bias_ms, mae_ms=stats.mae_ms,
                weight_multiplier=stats.weight_multiplier,
                decision_status="pending_review", decision_version=CALIBRATION_DECISION_VERSION,
                decision_reason="holdout_evaluation_required",
                decision_metrics={"training_samples": stats.sample_count},
            ).on_conflict_do_update(
                constraint="uq_weather_calibration",
                set_={"sample_count": stats.sample_count, "bias_ms": stats.bias_ms,
                      "mae_ms": stats.mae_ms, "weight_multiplier": stats.weight_multiplier,
                      "decision_status": "pending_review", "decision_version": CALIBRATION_DECISION_VERSION,
                      "decision_reason": "holdout_evaluation_required",
                      "decision_metrics": {"training_samples": stats.sample_count},
                      "updated_at": datetime.now(timezone.utc)},
            )
            db.execute(stmt)
            updated += 1
    db.commit()
    return updated
