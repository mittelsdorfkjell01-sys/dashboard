"""Forecast verification and conservative, measurement-backed calibration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, median
import math
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import (
    ForecastVerificationScore,
    Spot,
    WeatherForecastSample,
    WeatherModelCalibration,
    WeatherObservation,
    WeatherStation,
)
from app.weather.observations import public_measurement

# 30 samples can cover only five hours at a ten-minute cadence and is too easy
# to overfit. Sixty is still deliberately modest for local preparation; an
# activation additionally needs a chronological holdout improvement.
MIN_CALIBRATION_SAMPLES = 60
CALIBRATION_DECISION_VERSION = "holdout-v1"


def lead_bucket(hours: float) -> str:
    if hours <= 24:
        return "0-24h"
    if hours <= 72:
        return "24-72h"
    return "72-240h"


# Twelve canonical 30-degree sectors aligned to the Global Wind Atlas bins so the
# verification breakdown shares the axis a future GWA sector-factor producer uses.
def direction_sector(direction_deg: float) -> int:
    """Return the 30-degree sector index (0 = [0,30) ... 11 = [330,360))."""
    return int((float(direction_deg) % 360.0) // 30.0)


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
    wind_rmse_ms: float
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
    rmse = math.sqrt(mean(value * value for value in errors))
    return VerificationMetrics(len(clean), round(mean(abs(v) for v in errors), 3), round(mean(errors), 3),
                               round(rmse, 3),
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


# ---------------------------------------------------------------------------
# WP1 validation harness: score the raw forecast against station measurements.
#
# The station wind never enters the forecast; it only produces bias/MAE/RMSE
# broken down by lead-time bucket and 30-degree direction sector. Only
# measurements passing ``observations.public_measurement`` are scored, and the
# staleness gate is neutralised for historical scoring by evaluating each
# observation at its own timestamp (``now == observed_at``).
# ---------------------------------------------------------------------------

CONSENSUS_MODEL_ID = "consensus"


def _circular_mean_deg(values: list[float]) -> float:
    xs = sum(math.cos(math.radians(float(v))) for v in values)
    ys = sum(math.sin(math.radians(float(v))) for v in values)
    return math.degrees(math.atan2(ys, xs)) % 360.0


def _sample_predictions(samples) -> list[dict]:
    return [{
        "model_id": s.model_id, "valid_at": s.valid_at, "lead_hours": s.lead_hours,
        "wind_speed_ms": s.wind_speed_ms, "wind_direction_deg": s.wind_direction_deg,
        "wind_gust_ms": s.wind_gust_ms,
    } for s in samples]


def _consensus_predictions(samples) -> list[dict]:
    """One vector-consistent consensus prediction per issued forecast run and hour."""
    by_run: dict[tuple, list] = defaultdict(list)
    for sample in samples:
        by_run[(sample.issued_at, sample.valid_at)].append(sample)
    output = []
    for (_issued_at, valid_at), members in by_run.items():
        gusts = [m.wind_gust_ms for m in members if m.wind_gust_ms is not None]
        output.append({
            "model_id": CONSENSUS_MODEL_ID, "valid_at": valid_at,
            "lead_hours": members[0].lead_hours,
            "wind_speed_ms": mean(m.wind_speed_ms for m in members),
            "wind_direction_deg": _circular_mean_deg([m.wind_direction_deg for m in members]),
            "wind_gust_ms": mean(gusts) if len(gusts) == len(members) else None,
        })
    return output


def _score_predictions(predictions: list[dict], observations: list, *, tolerance_s: int) -> list[dict]:
    """Match each prediction to the nearest gated observation and group by cohort."""
    groups: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for pred in predictions:
        nearest = min(observations, key=lambda obs: abs((obs.observed_at - pred["valid_at"]).total_seconds()), default=None)
        if nearest is None or abs((nearest.observed_at - pred["valid_at"]).total_seconds()) > tolerance_s:
            continue
        key = (pred["model_id"], lead_bucket(pred["lead_hours"]), direction_sector(pred["wind_direction_deg"]))
        groups[key].append({
            "wind_pred": pred["wind_speed_ms"], "wind_obs": nearest.wind_speed_ms,
            "direction_pred": pred["wind_direction_deg"], "direction_obs": nearest.wind_direction_deg,
            "gust_pred": pred["wind_gust_ms"], "gust_obs": nearest.wind_gust_ms,
        })
    records = []
    for (model_id, bucket, sector), rows in sorted(groups.items()):
        metrics = verification_metrics(rows)
        if metrics is None:
            continue
        records.append({
            "model_id": model_id, "lead_bucket": bucket, "direction_sector": sector,
            "sample_count": metrics.sample_count, "bias_ms": metrics.wind_bias_ms,
            "mae_ms": metrics.wind_mae_ms, "rmse_ms": metrics.wind_rmse_ms,
            "direction_mae_deg": metrics.direction_mae_deg,
        })
    return records


def gated_observations(db, spot_id, *, cutoff) -> list:
    """Observations for a spot that pass the public station/quality gate."""
    accepted = []
    stations = db.scalars(select(WeatherStation).where(
        WeatherStation.spot_id == spot_id, WeatherStation.active.is_(True))).all()
    for station in stations:
        observations = db.scalars(select(WeatherObservation).where(
            WeatherObservation.station_id == station.id,
            WeatherObservation.observed_at >= cutoff)).all()
        for observation in observations:
            ok, _reasons = public_measurement(station, observation, now=observation.observed_at.astimezone(timezone.utc))
            if ok:
                accepted.append(observation)
    return accepted


def score_spot_forecasts(db, spot_id, *, now=None, lookback_days: int = 45, tolerance_s: int = 1200) -> list[dict]:
    """Per-model and consensus bias/MAE/RMSE of the raw forecast versus gated observations."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, min(lookback_days, 365)))
    observations = gated_observations(db, spot_id, cutoff=cutoff)
    if not observations:
        return []
    samples = db.scalars(select(WeatherForecastSample).where(
        WeatherForecastSample.spot_id == spot_id,
        WeatherForecastSample.valid_at >= cutoff)).all()
    if not samples:
        return []
    records = _score_predictions(_sample_predictions(samples), observations, tolerance_s=tolerance_s)
    records += _score_predictions(_consensus_predictions(samples), observations, tolerance_s=tolerance_s)
    return records


def eligible_spot_ids(db) -> list:
    """Published spots with an approved, representative station worth scoring."""
    rows = db.execute(
        select(WeatherStation.spot_id)
        .join(Spot, Spot.id == WeatherStation.spot_id)
        .where(
            WeatherStation.active.is_(True),
            WeatherStation.approved.is_(True),
            WeatherStation.representativeness_status == "passed",
            Spot.status == "published",
        )
        .distinct()
    ).all()
    return [row[0] for row in rows]


def persist_verification_scores(db, run_id, spot_id, records, *, variant: str = "raw",
                                window_start=None, window_end=None, computed_at=None) -> int:
    if not records or not hasattr(db, "execute"):
        return 0
    computed_at = computed_at or datetime.now(timezone.utc)
    values = [{
        "run_id": run_id, "spot_id": spot_id, "model_id": r["model_id"], "variant": variant,
        "lead_bucket": r["lead_bucket"], "direction_sector": r["direction_sector"],
        "sample_count": r["sample_count"], "bias_ms": r["bias_ms"], "mae_ms": r["mae_ms"],
        "rmse_ms": r["rmse_ms"], "direction_mae_deg": r["direction_mae_deg"],
        "window_start": window_start, "window_end": window_end, "computed_at": computed_at,
    } for r in records]
    excluded = insert(ForecastVerificationScore).excluded
    stmt = insert(ForecastVerificationScore).values(values).on_conflict_do_update(
        constraint="uq_forecast_verification_score",
        set_={"sample_count": excluded.sample_count, "bias_ms": excluded.bias_ms,
              "mae_ms": excluded.mae_ms, "rmse_ms": excluded.rmse_ms,
              "direction_mae_deg": excluded.direction_mae_deg,
              "window_start": excluded.window_start, "window_end": excluded.window_end,
              "computed_at": excluded.computed_at},
    )
    db.execute(stmt)
    db.commit()
    return len(values)


def run_verification_scoring(db, *, spot_ids=None, now=None, lookback_days: int = 45,
                             tolerance_s: int = 1200, variant: str = "raw",
                             run_id=None, persist: bool = True) -> dict:
    """Score every eligible spot in one reproducible run; returns a compact summary."""
    now = now or datetime.now(timezone.utc)
    run_id = run_id or uuid.uuid4()
    window_start = now - timedelta(days=max(1, min(lookback_days, 365)))
    targets = list(spot_ids) if spot_ids is not None else eligible_spot_ids(db)
    spots_scored = 0
    total_rows = 0
    for spot_id in targets:
        records = score_spot_forecasts(db, spot_id, now=now, lookback_days=lookback_days, tolerance_s=tolerance_s)
        if not records:
            continue
        spots_scored += 1
        total_rows += len(records)
        if persist:
            persist_verification_scores(db, run_id, spot_id, records, variant=variant,
                                        window_start=window_start, window_end=now, computed_at=now)
    return {
        "run_id": str(run_id), "spots_scored": spots_scored, "rows": total_rows,
        "variant": variant, "lookback_days": lookback_days,
        "window_start": window_start.isoformat(), "window_end": now.isoformat(),
    }
