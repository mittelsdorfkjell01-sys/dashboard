"""Forecast verification and conservative, measurement-backed calibration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import WeatherForecastSample, WeatherModelCalibration, WeatherObservation, WeatherStation

MIN_CALIBRATION_SAMPLES = 30


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
    return {(row.model_id, row.lead_bucket): row for row in rows if row.sample_count >= MIN_CALIBRATION_SAMPLES}


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
            ).on_conflict_do_update(
                constraint="uq_weather_calibration",
                set_={"sample_count": stats.sample_count, "bias_ms": stats.bias_ms,
                      "mae_ms": stats.mae_ms, "weight_multiplier": stats.weight_multiplier,
                      "updated_at": datetime.now(timezone.utc)},
            )
            db.execute(stmt)
            updated += 1
    db.commit()
    return updated
