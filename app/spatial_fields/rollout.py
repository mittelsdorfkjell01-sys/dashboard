"""Evidence-based rollout gate for full-horizon weather-field publications."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import func, select

from app.models.weather_field import WeatherFieldModel, WeatherFieldRun
from app.spatial_fields.forecast_profile import forecast_hours_for_model


@dataclass(frozen=True)
class ShadowReadiness:
    ready: bool
    required_runs: int
    consecutive_runs: int
    qualified_run_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    budgets: dict[str, int]

    def model_dump(self) -> dict:
        return asdict(self)


def _forecast_hours(run: WeatherFieldRun) -> list[int]:
    return [
        int(
            (
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                - run.model_run_at
            ).total_seconds()
            // 3600
        )
        for value in run.valid_times
    ]


def _run_blockers(run: WeatherFieldRun, *, expected_hours: list[int], settings) -> list[str]:
    blockers: list[str] = []
    if run.status != "ready":
        blockers.append(f"status={run.status}")
    if _forecast_hours(run) != expected_hours:
        blockers.append("forecast horizon differs from the configured rollout profile")
    if run.bytes_downloaded > settings.weather_field_activation_max_download_bytes:
        blockers.append("source download budget exceeded")
    asset_bytes = (run.diagnostics or {}).get("asset_bytes")
    if not isinstance(asset_bytes, int):
        blockers.append("asset byte evidence is missing")
    elif asset_bytes > settings.weather_field_activation_max_asset_bytes:
        blockers.append("asset byte budget exceeded")
    if run.started_at is None or run.completed_at is None:
        blockers.append("processing duration evidence is missing")
    elif (run.completed_at - run.started_at).total_seconds() > (
        settings.weather_field_activation_max_processing_seconds
    ):
        blockers.append("processing duration budget exceeded")
    return blockers


def assess_shadow_readiness(
    db,
    *,
    candidate_run_id: uuid.UUID,
    settings,
    now: datetime | None = None,
) -> ShadowReadiness:
    instant = now or datetime.now(timezone.utc)
    candidate = db.get(WeatherFieldRun, candidate_run_id)
    required = settings.weather_field_activation_min_shadow_runs
    budgets = {
        "lookback_hours": settings.weather_field_activation_lookback_hours,
        "max_download_bytes": settings.weather_field_activation_max_download_bytes,
        "max_asset_bytes": settings.weather_field_activation_max_asset_bytes,
        "max_processing_seconds": settings.weather_field_activation_max_processing_seconds,
    }
    if candidate is None:
        return ShadowReadiness(False, required, 0, (), ("candidate run does not exist",), budgets)
    model = db.get(WeatherFieldModel, candidate.model_id)
    if model is None:  # protected by the database foreign key
        return ShadowReadiness(False, required, 0, (), ("candidate model does not exist",), budgets)

    reasons: list[str] = []
    latest_model_run = db.scalar(
        select(func.max(WeatherFieldRun.model_run_at)).where(
            WeatherFieldRun.model_id == candidate.model_id
        )
    )
    if latest_model_run != candidate.model_run_at:
        reasons.append("candidate is not the latest discovered model cycle")

    expected_hours = forecast_hours_for_model(
        model.model_key, list(settings.weather_field_forecast_hours)
    )
    candidate_blockers = _run_blockers(
        candidate, expected_hours=expected_hours, settings=settings
    )
    if candidate_blockers:
        reasons.append("candidate: " + ", ".join(candidate_blockers))

    window_start = instant - timedelta(
        hours=settings.weather_field_activation_lookback_hours
    )
    runs = db.scalars(
        select(WeatherFieldRun)
        .where(
            WeatherFieldRun.model_id == candidate.model_id,
            WeatherFieldRun.model_run_at <= candidate.model_run_at,
            WeatherFieldRun.model_run_at >= window_start,
        )
        .order_by(WeatherFieldRun.model_run_at.desc(), WeatherFieldRun.created_at.desc())
    ).all()
    cycles: dict[datetime, list[WeatherFieldRun]] = {}
    for run in runs:
        cycles.setdefault(run.model_run_at, []).append(run)

    qualified: list[str] = []
    expected_cycle_at = candidate.model_run_at
    for model_run_at, cycle_runs in cycles.items():
        if model_run_at != expected_cycle_at:
            break
        eligible = [candidate] if model_run_at == candidate.model_run_at else cycle_runs
        accepted = next(
            (
                run
                for run in eligible
                if not _run_blockers(run, expected_hours=expected_hours, settings=settings)
            ),
            None,
        )
        if accepted is None:
            break
        qualified.append(str(accepted.id))
        if len(qualified) >= required:
            break
        expected_cycle_at -= timedelta(hours=model.cadence_hours)

    if len(qualified) < required:
        reasons.append(
            f"need {required} consecutive full-horizon shadow cycles; observed {len(qualified)}"
        )
    return ShadowReadiness(
        not reasons,
        required,
        len(qualified),
        tuple(qualified),
        tuple(reasons),
        budgets,
    )
