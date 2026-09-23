"""Offline recommendation backtest over archived forecast and truth hours."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import math
from statistics import median
from typing import Iterable, Mapping

from sqlalchemy import select

from app.scoring.params import get_params
from app.scoring.rider.band import PersonalBand, personal_band
from app.recommendations.engine import condition_fit

KNOTS_PER_MS = 1.9438444924406
SURFACES = ("now", "next_week", "season", "region", "search")


@dataclass(frozen=True, slots=True)
class HistoricalHour:
    spot_id: str
    valid_at: datetime
    surface: str
    forecast_wind_kt: float
    truth_wind_kt: float
    confidence: float


@dataclass(frozen=True, slots=True)
class TruthHour:
    spot_id: str
    observed_at: datetime
    wind_kt: float


@dataclass(frozen=True, slots=True)
class SeasonPrediction:
    spot_id: str
    iso_week: int
    probability: float
    archive_end_year: int


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    surface: str
    archetype: str
    precision_at_k: float | None
    confidence_brier: float | None
    confidence_calibration_error: float | None
    coverage: float
    diversity: float
    evaluated_days: int
    recommendation_count: int
    available: bool


def profile_archetypes(params: Mapping) -> dict[str, dict]:
    default = dict(params["default_rider"]["kitesurf"])
    return {
        "average": default,
        "light_large_quiver": {
            **default, "weight_kg": 55, "level": "advanced",
            "quiver": [
                {"kind": "kite", "size": 8}, {"kind": "kite", "size": 11},
                {"kind": "kite", "size": 14},
                {"kind": "board", "board_type": "twintip"},
            ],
        },
        "heavy_small_quiver": {
            **default, "weight_kg": 105, "level": "expert",
            "quiver": [
                {"kind": "kite", "size": 7}, {"kind": "kite", "size": 9},
                {"kind": "board", "board_type": "bigair_twintip"},
            ],
        },
        "foil": {
            **default, "weight_kg": 75,
            "quiver": [
                {"kind": "kite", "size": 8}, {"kind": "kite", "size": 11},
                {"kind": "foil", "board_type": "foil"},
            ],
        },
        "beginner": {
            **default, "weight_kg": 78, "level": "beginner",
            "quiver": [
                {"kind": "kite", "size": 10}, {"kind": "kite", "size": 13},
                {"kind": "board", "board_type": "twintip"},
            ],
        },
    }


def _has_session(values: list[tuple[datetime, float]], band: PersonalBand) -> bool:
    run = 0
    previous: datetime | None = None
    for instant, wind in sorted(values):
        consecutive = previous is not None and 0 < (instant - previous).total_seconds() <= 5400
        run = run + 1 if consecutive and band.min_kt <= wind <= band.max_kt else int(
            band.min_kt <= wind <= band.max_kt
        )
        if run >= 3:
            return True
        previous = instant
    return False


def evaluate_backtest(
    hours: Iterable[HistoricalHour],
    *,
    profiles: Mapping[str, Mapping],
    params: Mapping,
    k: int = 5,
) -> list[BacktestMetrics]:
    records = list(hours)
    results: list[BacktestMetrics] = []
    for surface in SURFACES:
        surface_rows = [row for row in records if row.surface == surface]
        for archetype, profile in profiles.items():
            band = personal_band(profile, "kitesurf", params)
            grouped: dict[date, dict[str, list[HistoricalHour]]] = {}
            for row in surface_rows:
                grouped.setdefault(row.valid_at.date(), {}).setdefault(row.spot_id, []).append(row)
            correct = total = 0
            brier: list[float] = []
            calibration: list[tuple[float, bool]] = []
            recommended_spots: set[str] = set()
            nonempty_days = 0
            for spots in grouped.values():
                ranked: list[tuple[str, float, float, bool]] = []
                for spot_id, spot_hours in spots.items():
                    forecast_values = [(row.valid_at, row.forecast_wind_kt) for row in spot_hours]
                    if not _has_session(forecast_values, band):
                        continue
                    fit = sum(
                        condition_fit(row.forecast_wind_kt, band) for row in spot_hours
                    ) / len(spot_hours)
                    confidence = sum(row.confidence for row in spot_hours) / len(spot_hours)
                    truth = _has_session(
                        [(row.valid_at, row.truth_wind_kt) for row in spot_hours], band
                    )
                    ranked.append((spot_id, fit * confidence, confidence, truth))
                chosen = sorted(ranked, key=lambda item: (-item[1], item[0]))[:k]
                if chosen:
                    nonempty_days += 1
                for spot_id, _score, confidence, truth in chosen:
                    total += 1
                    correct += int(truth)
                    brier.append((confidence - float(truth)) ** 2)
                    calibration.append((confidence, truth))
                    recommended_spots.add(spot_id)
            days = len(grouped)
            calibration_error = None
            if calibration:
                weighted_error = 0.0
                for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
                    bucket = [
                        (confidence, truth)
                        for confidence, truth in calibration
                        if (
                            (lower <= confidence <= 1.0)
                            if lower == 0.8
                            else (lower <= confidence < lower + 0.2)
                        )
                    ]
                    if bucket:
                        predicted = sum(value for value, _truth in bucket) / len(bucket)
                        observed = sum(float(truth) for _value, truth in bucket) / len(bucket)
                        weighted_error += abs(predicted - observed) * len(bucket)
                calibration_error = round(weighted_error / len(calibration), 4)
            results.append(BacktestMetrics(
                surface=surface,
                archetype=archetype,
                precision_at_k=round(correct / total, 4) if total else None,
                confidence_brier=round(sum(brier) / len(brier), 4) if brier else None,
                confidence_calibration_error=calibration_error,
                coverage=round(nonempty_days / days, 4) if days else 0.0,
                diversity=round(len(recommended_spots) / total, 4) if total else 0.0,
                evaluated_days=days,
                recommendation_count=total,
                available=bool(surface_rows),
            ))
    return results


def _calibration_error(rows: list[tuple[float, bool]]) -> float | None:
    if not rows:
        return None
    weighted_error = 0.0
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        bucket = [
            (confidence, truth)
            for confidence, truth in rows
            if (
                (lower <= confidence <= 1.0)
                if lower == 0.8
                else (lower <= confidence < lower + 0.2)
            )
        ]
        if bucket:
            predicted = sum(value for value, _truth in bucket) / len(bucket)
            observed = sum(float(truth) for _value, truth in bucket) / len(bucket)
            weighted_error += abs(predicted - observed) * len(bucket)
    return round(weighted_error / len(rows), 4)


def evaluate_season_backtest(
    predictions: Mapping[str, Iterable[SeasonPrediction]],
    truth_hours: Iterable[TruthHour],
    *,
    profiles: Mapping[str, Mapping],
    params: Mapping,
    k: int = 5,
) -> list[BacktestMetrics]:
    """Evaluate V3 weekly archive probabilities against later observations.

    A V3 archive may only predict observations from years after its training
    window. That keeps a regenerated climatology artifact from leaking the
    evaluated year into its own backtest.
    """
    truth_records = list(truth_hours)
    results: list[BacktestMetrics] = []
    for archetype, profile in profiles.items():
        rows = list(predictions.get(archetype) or [])
        by_week: dict[int, dict[str, SeasonPrediction]] = {}
        for row in rows:
            by_week.setdefault(row.iso_week, {})[row.spot_id] = row

        band = personal_band(profile, "kitesurf", params)
        daily: dict[tuple[int, int, str, date], list[tuple[datetime, float]]] = {}
        for hour in truth_records:
            prediction = by_week.get(hour.observed_at.isocalendar().week, {}).get(hour.spot_id)
            if (
                prediction is None
                or hour.observed_at.isocalendar().year <= prediction.archive_end_year
            ):
                continue
            iso = hour.observed_at.isocalendar()
            key = (iso.year, iso.week, hour.spot_id, hour.observed_at.date())
            daily.setdefault(key, []).append((hour.observed_at, hour.wind_kt))

        weekly_truth: dict[tuple[int, int], dict[str, bool]] = {}
        for (year, week, spot_id, _day), values in daily.items():
            if _has_session(values, band):
                weekly_truth.setdefault((year, week), {})[spot_id] = True
            else:
                weekly_truth.setdefault((year, week), {}).setdefault(spot_id, False)

        correct = total = nonempty = 0
        brier: list[float] = []
        calibration: list[tuple[float, bool]] = []
        recommended_spots: set[str] = set()
        for (_year, week), spot_truth in weekly_truth.items():
            candidates = [
                row for row in by_week.get(week, {}).values()
                if row.spot_id in spot_truth and row.probability > 0
            ]
            chosen = sorted(candidates, key=lambda row: (-row.probability, row.spot_id))[:k]
            if chosen:
                nonempty += 1
            for row in chosen:
                outcome = bool(spot_truth.get(row.spot_id))
                total += 1
                correct += int(outcome)
                brier.append((row.probability - float(outcome)) ** 2)
                calibration.append((row.probability, outcome))
                recommended_spots.add(row.spot_id)

        periods = len(weekly_truth)
        results.append(BacktestMetrics(
            surface="season",
            archetype=archetype,
            precision_at_k=round(correct / total, 4) if total else None,
            confidence_brier=round(sum(brier) / len(brier), 4) if brier else None,
            confidence_calibration_error=_calibration_error(calibration),
            coverage=round(nonempty / periods, 4) if periods else 0.0,
            diversity=round(len(recommended_spots) / total, 4) if total else 0.0,
            evaluated_days=periods,
            recommendation_count=total,
            available=bool(rows and periods),
        ))
    return results


def load_observation_hours(db, start: datetime, end: datetime) -> list[TruthHour]:
    """Load accepted observations, collapsed to one value per spot and hour."""
    from app.models import WeatherObservation, WeatherStation

    observations = db.execute(
        select(
            WeatherStation.spot_id,
            WeatherObservation.observed_at,
            WeatherObservation.wind_speed_ms,
        )
        .join(WeatherStation, WeatherStation.id == WeatherObservation.station_id)
        .where(
            WeatherObservation.observed_at >= start,
            WeatherObservation.observed_at < end,
            WeatherObservation.import_status == "accepted",
            WeatherStation.active.is_(True),
        )
    ).all()
    grouped: dict[tuple[object, datetime], list[float]] = {}
    for spot_id, observed_at, wind_ms in observations:
        instant = observed_at.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        grouped.setdefault((spot_id, instant), []).append(float(wind_ms) * KNOTS_PER_MS)
    return [
        TruthHour(spot_id=str(spot_id), observed_at=instant, wind_kt=median(values))
        for (spot_id, instant), values in grouped.items()
    ]


def load_v3_season_predictions(
    db,
    *,
    profiles: Mapping[str, Mapping],
    params: Mapping,
) -> dict[str, list[SeasonPrediction]]:
    """Load the V3 variant nearest each archetype's Personal Band.

    V3 contains every integer wind window. Reviewed usable-direction variants
    are preferred; the all-direction variant remains the deterministic fallback.
    """
    from app.models import WindClimatologyV3Run, WindClimatologyV3Variant
    from app.wind_climatology.v3_artifact import decode_cube

    output: dict[str, list[SeasonPrediction]] = {}
    for archetype, profile in profiles.items():
        band = personal_band(profile, "kitesurf", params)
        low = max(5, min(40, math.floor(band.ideal_lo_kt)))
        requested_high = math.ceil(band.ideal_hi_kt)
        high = None if requested_high > 40 or low == 40 else max(low + 1, requested_high)
        max_window = (
            WindClimatologyV3Variant.max_wind_kn.is_(None)
            if high is None
            else WindClimatologyV3Variant.max_wind_kn == high
        )
        variants = db.execute(
            select(WindClimatologyV3Run, WindClimatologyV3Variant)
            .join(
                WindClimatologyV3Variant,
                WindClimatologyV3Variant.run_id == WindClimatologyV3Run.id,
            )
            .where(
                WindClimatologyV3Run.is_active.is_(True),
                WindClimatologyV3Run.status == "ready",
                WindClimatologyV3Variant.min_wind_kn == low,
                max_window,
                WindClimatologyV3Variant.direction_mode.in_(("usable", "all")),
            )
        ).all()
        selected: dict[object, tuple[object, object]] = {}
        for run, variant in variants:
            current = selected.get(run.spot_id)
            if current is None or (
                variant.direction_mode == "usable"
                and current[1].direction_mode != "usable"
            ):
                selected[run.spot_id] = (run, variant)

        predictions: list[SeasonPrediction] = []
        for spot_id, (run, variant) in selected.items():
            payload = decode_cube(variant.payload_blob)
            for week in payload.get("weeks") or []:
                if week.get("quality_status") == "insufficient":
                    continue
                probability = week.get("probability_at_least_1_day")
                if probability is None:
                    continue
                predictions.append(SeasonPrediction(
                    spot_id=str(spot_id),
                    iso_week=int(week["week"]),
                    probability=max(0.0, min(1.0, float(probability) / 100.0)),
                    archive_end_year=int(run.end_year),
                ))
        output[archetype] = predictions
    return output


def load_archived_hours(db, start: datetime, end: datetime) -> list[HistoricalHour]:
    """Join archived forecast features to exact-hour approved observations."""
    from app.models import WeatherForecastSample

    forecasts = db.scalars(
        select(WeatherForecastSample).where(
            WeatherForecastSample.valid_at >= start,
            WeatherForecastSample.valid_at < end,
        )
    ).all()
    truth: dict[tuple[object, datetime], list[float]] = {}
    for observation in load_observation_hours(db, start, end):
        truth.setdefault((observation.spot_id, observation.observed_at), []).append(
            observation.wind_kt
        )

    grouped: dict[tuple[object, datetime, str], list] = {}
    for sample in forecasts:
        instant = sample.valid_at.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        surface = "now" if sample.lead_hours <= 48 else "next_week"
        grouped.setdefault((sample.spot_id, instant, surface), []).append(sample)
    rows: list[HistoricalHour] = []
    for (spot_id, instant, surface), samples in grouped.items():
        observed = truth.get((str(spot_id), instant))
        if not observed:
            continue
        forecast_kt = median(float(sample.wind_speed_ms) * KNOTS_PER_MS for sample in samples)
        lead = median(sample.lead_hours for sample in samples)
        rows.append(HistoricalHour(
            spot_id=str(spot_id), valid_at=instant, surface=surface,
            forecast_wind_kt=forecast_kt,
            truth_wind_kt=median(observed),
            confidence=max(0.35, min(0.95, 0.95 - lead / 500)),
        ))
    # Region and search use the same short-range condition evidence as `now`;
    # their candidate pool differs at request time. Duplicating the archived
    # hours keeps the metric definition identical while reporting each public
    # surface separately. Season stays unavailable unless an explicit
    # climatology archive/fixture supplies season rows.
    short_range = [row for row in rows if row.surface == "now"]
    rows.extend(
        HistoricalHour(
            spot_id=row.spot_id,
            valid_at=row.valid_at,
            surface=surface,
            forecast_wind_kt=row.forecast_wind_kt,
            truth_wind_kt=row.truth_wind_kt,
            confidence=row.confidence,
        )
        for row in short_range
        for surface in ("region", "search")
    )
    return rows


def run_database_backtest(db, *, days: int, k: int = 5) -> dict:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = get_params("kitesurf", db=db)
    profiles = profile_archetypes(params)
    hours = load_archived_hours(db, start, end)
    metrics = evaluate_backtest(
        hours,
        profiles=profiles,
        params=params,
        k=k,
    )
    truth_hours = load_observation_hours(db, start, end)
    season_predictions = load_v3_season_predictions(
        db, profiles=profiles, params=params
    )
    season_metrics = evaluate_season_backtest(
        season_predictions,
        truth_hours,
        profiles=profiles,
        params=params,
        k=k,
    )
    metrics = [row for row in metrics if row.surface != "season"] + season_metrics
    season_archive_rows = len({
        (row.spot_id, row.iso_week, row.archive_end_year)
        for predictions in season_predictions.values()
        for row in predictions
    })
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "k": k,
        "data_availability": {
            surface: (
                season_archive_rows
                if surface == "season"
                else sum(1 for row in hours if row.surface == surface)
            )
            for surface in SURFACES
        },
        "metrics": [asdict(row) for row in metrics],
    }
