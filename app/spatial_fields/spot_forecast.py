"""Evidence-gated Phase-6 wind baseline for public spot snapshots.

The adapter deliberately changes only wind values. Open-Meteo remains the
temporary source for air, solar and marine fields, and also supplies the tail
outside the active ICON-EU horizon. A failed or incomplete field replacement
returns the original payload unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math

from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    Region,
    Spot,
    SpotWeatherProfile,
    SpotWeatherSector,
    WeatherObservation,
    WeatherStation,
)
from app.models.weather_field import WeatherFieldRun
from app.models.weather_field_shadow import WeatherFieldShadowRun, WeatherFieldShadowSample
from app.spatial_fields.publication import active_publication_state
from app.spatial_fields.forecast_profile import wave_model_keys
from app.spatial_fields.serving import FieldSampleUnavailable, sample_active_field
from app.weather.catalog import family_for
from app.weather.physics import apply_local_physics
from app.weather.physics.blend import family_blend
from app.weather.profiles import resolve_weather_profile
from app.weather.units import WindSpeedUnit, convert_wind_speed
from app.weather.vectors import wind_to_uv


@dataclass(frozen=True)
class SpotFieldEvidence:
    shadow_cycles: int
    shadow_samples: int
    observation_samples: int
    speed_mae_ms: float | None
    direction_mae_deg: float | None
    gust_mae_ms: float | None
    observed_speed_mae_ms: float | None
    observed_direction_mae_deg: float | None
    observed_gust_mae_ms: float | None
    legacy_observed_speed_mae_ms: float | None
    freshness: str | None


@dataclass(frozen=True)
class SpotFieldDecision:
    enabled: bool
    unverified_override: bool
    stage: str
    region_slug: str | None
    reasons: tuple[str, ...]
    evidence: SpotFieldEvidence

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SpotFieldResult:
    payload: dict
    applied: bool
    diagnostics: dict


def active_wave_publication_ids(db, *, settings, now=None) -> tuple[str, ...]:
    """Return the active publication set used by the spot-wave adapter."""
    if not getattr(settings, "wave_field_public_enabled", False):
        return ()

    from app.spatial_fields.scopes import model_scope

    publication_ids: set[str] = set()
    for model_key in wave_model_keys(settings):
        scope_key = model_scope(
            settings.wave_field_scope_key,
            model_key,
            primary_model=settings.wave_field_primary_model,
        )
        active = active_publication_state(db, scope_key, now=now)
        if active is not None:
            publication_ids.add(str(active.publication_id))
    return tuple(sorted(publication_ids))


def apply_spot_wave_baseline(
    db,
    *,
    spot: Spot,
    payload: dict,
    settings,
    storage=None,
) -> SpotFieldResult:
    """Overlay the active DWD wave field and retain point-provider data as tail fallback."""
    if not getattr(settings, "wave_field_public_enabled", False):
        return SpotFieldResult(payload, False, {"reason": "wave_field_not_public"})
    active_publications = active_wave_publication_ids(db, settings=settings)
    from app.spatial_fields.scopes import model_scope
    from app.spatial_fields.storage import configured_field_storage

    storage = storage or configured_field_storage()
    point = to_shape(spot.location)
    candidate = deepcopy(payload)
    replaced = 0
    publication_ids: set[str] = set()
    for day in candidate.get("days", []):
        for hour in day.get("hours", []):
            try:
                valid_at = datetime.fromisoformat(str(hour["time"]).replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                continue
            if valid_at.tzinfo is None:
                continue
            field = None
            for model_key in wave_model_keys(settings):
                scope_key = model_scope(
                    settings.wave_field_scope_key,
                    model_key,
                    primary_model=settings.wave_field_primary_model,
                )
                try:
                    field = sample_active_field(
                        db,
                        storage=storage,
                        scope_key=scope_key,
                        latitude=float(point.y),
                        longitude=float(point.x),
                        valid_at=valid_at.astimezone(timezone.utc),
                        model_key=model_key,
                        nearest_valid_radius_pixels=8,
                    )
                    break
                except (FieldSampleUnavailable, ValueError):
                    continue
            if field is None:
                continue
            height = field.get("total_wave_height_m")
            period = field.get("total_wave_period_s")
            direction = field.get("total_wave_direction_from_deg")
            if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in (height, period, direction)):
                continue
            primary_height = field.get("primary_swell_height_m")
            primary_period = field.get("primary_swell_period_s")
            primary_direction = field.get("primary_swell_direction_from_deg")
            field_model = str(field["model"])
            marine_provider = (
                "NOAA/NCEP" if field_model == "noaa-gfs-wave" else "Deutscher Wetterdienst"
            )
            marine_source = (
                "NOAA GFS-Wave"
                if field_model == "noaa-gfs-wave"
                else "DWD EWAM/GWAM"
            )
            hour.update(
                swell=round(float(primary_height), 2) if isinstance(primary_height, (int, float)) else None,
                period=round(float(primary_period), 1) if isinstance(primary_period, (int, float)) else None,
                swell_dir=round(float(primary_direction) % 360.0, 1) if isinstance(primary_direction, (int, float)) else None,
                waves={
                    "total_wave": {
                        "significant_height_m": round(float(height), 2),
                        "mean_period_s": round(float(period), 1),
                        "mean_direction_from_deg": round(float(direction) % 360.0, 1),
                        "source": marine_source,
                        "quality_tier": "model_field",
                    },
                    "wind_sea": {
                        "significant_height_m": field.get("wind_sea_height_m"),
                        "mean_period_s": field.get("wind_sea_period_s"),
                        "mean_direction_from_deg": field.get("wind_sea_direction_from_deg"),
                        "source": marine_source,
                        "quality_tier": "model_field",
                    },
                    "primary_swell": {
                        "significant_height_m": field.get("primary_swell_height_m"),
                        "mean_period_s": field.get("primary_swell_period_s"),
                        "mean_direction_from_deg": field.get("primary_swell_direction_from_deg"),
                        "source": marine_source,
                        "quality_tier": "model_field",
                    },
                    "secondary_swell": None,
                },
            )
            hour["provenance"] = {
                **dict(hour.get("provenance") or {}),
                "marine_source": "weather_field",
                "marine_provider": marine_provider,
                "marine_model": field_model,
                "marine_model_run_at": field["model_run"],
                "marine_publication_id": field["publication_id"],
            }
            publication_ids.add(str(field["publication_id"]))
            replaced += 1
    if replaced == 0:
        return SpotFieldResult(
            payload,
            False,
            {
                "reason": "wave_field_horizon_unavailable",
                "active_publication_ids": list(active_publications),
            },
        )
    return SpotFieldResult(
        candidate,
        True,
        {
            "source": "weather-field",
            "active_publication_ids": list(active_publications),
            "publication_ids": sorted(publication_ids),
            "replaced_hours": replaced,
            "tail_fallback": "open-meteo-marine",
        },
    )


def _allowed_regions(settings) -> set[str]:
    return {
        value.strip().casefold()
        for value in settings.weather_field_spot_rollout_region_slugs.split(",")
        if value.strip()
    }


def _mae(values: list[float | None]) -> float | None:
    present = [abs(float(value)) for value in values if value is not None]
    return sum(present) / len(present) if present else None


def _direction_error(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return abs((float(left) - float(right) + 180.0) % 360.0 - 180.0)


def assess_spot_field_readiness(
    db, *, spot: Spot, settings, now: datetime | None = None
) -> SpotFieldDecision:
    """Return a fail-closed, per-spot rollout decision.

    Divergence evidence guards against accidental product regressions. The
    independent observation minimum is intentionally mandatory because Phase 5
    forbids a cutover based only on agreement with the legacy forecast.
    """

    instant = now or datetime.now(timezone.utc)
    stage = settings.weather_field_spot_rollout_stage
    region_slug = getattr(getattr(spot, "region", None), "slug", None)
    if region_slug is None and getattr(spot, "region_id", None) is not None:
        region_slug = db.scalar(select(Region.slug).where(Region.id == spot.region_id))
    empty = SpotFieldEvidence(
        0, 0, 0, None, None, None, None, None, None, None, None
    )
    if stage == "shadow":
        return SpotFieldDecision(
            False, False, stage, region_slug, ("rollout_stage_shadow",), empty
        )
    if stage in {"pilot", "regional"}:
        allowed = _allowed_regions(settings)
        if not allowed:
            return SpotFieldDecision(
                False, False, stage, region_slug, ("region_allowlist_empty",), empty
            )
        if not region_slug or region_slug.casefold() not in allowed:
            return SpotFieldDecision(
                False, False, stage, region_slug, ("region_not_enabled",), empty
            )

    active = active_publication_state(db, settings.weather_field_scope_key, now=instant)
    if active is None:
        return SpotFieldDecision(
            False, False, stage, region_slug, ("active_field_missing",), empty
        )

    cutoff = instant - timedelta(hours=settings.weather_field_spot_evidence_lookback_hours)
    active_run = db.get(WeatherFieldRun, active.run_id)
    if active_run is None:
        return SpotFieldDecision(
            False, False, stage, region_slug, ("active_field_run_missing",), empty
        )
    sample_rows = list(
        db.execute(
            select(WeatherFieldShadowSample, WeatherFieldShadowRun.field_run_id)
            .join(
                WeatherFieldShadowRun,
                WeatherFieldShadowRun.id == WeatherFieldShadowSample.shadow_run_id,
            )
            .join(WeatherFieldRun, WeatherFieldRun.id == WeatherFieldShadowRun.field_run_id)
            .where(
                WeatherFieldShadowSample.spot_id == spot.id,
                WeatherFieldShadowRun.status == "succeeded",
                WeatherFieldShadowRun.completed_at >= cutoff,
                WeatherFieldRun.model_key == active_run.model_key,
                WeatherFieldRun.processing_version == active_run.processing_version,
            )
        ).all()
    )
    samples = [row[0] for row in sample_rows]
    cycle_ids = {row[1] for row in sample_rows}
    observations = list(
        db.scalars(
            select(WeatherObservation)
            .join(WeatherStation, WeatherStation.id == WeatherObservation.station_id)
            .where(
                WeatherStation.spot_id == spot.id,
                WeatherStation.active.is_(True),
                WeatherStation.approved.is_(True),
                WeatherObservation.import_status == "accepted",
                WeatherObservation.availability_class == "captured_operationally",
                WeatherObservation.observed_at >= cutoff,
            )
        ).all()
    )
    observation_matches: list[tuple[WeatherFieldShadowSample, WeatherObservation]] = []
    for sample_row in samples:
        nearby = [
            observation
            for observation in observations
            if abs((observation.observed_at - sample_row.valid_at).total_seconds())
            <= 30 * 60
        ]
        if nearby:
            observation_matches.append(
                (
                    sample_row,
                    min(
                        nearby,
                        key=lambda row: abs(
                            (row.observed_at - sample_row.valid_at).total_seconds()
                        ),
                    ),
                )
            )
    observed_speed_mae = _mae(
        [sample.field_speed_ms - observation.wind_speed_ms for sample, observation in observation_matches]
    )
    legacy_observed_speed_mae = _mae(
        [sample.legacy_speed_ms - observation.wind_speed_ms for sample, observation in observation_matches]
    )
    observed_direction_mae = _mae(
        [
            _direction_error(sample.field_direction_deg, observation.wind_direction_deg)
            for sample, observation in observation_matches
        ]
    )
    observed_gust_mae = _mae(
        [
            sample.field_gust_ms - observation.wind_gust_ms
            if sample.field_gust_ms is not None and observation.wind_gust_ms is not None
            else None
            for sample, observation in observation_matches
        ]
    )
    evidence = SpotFieldEvidence(
        shadow_cycles=len(cycle_ids),
        shadow_samples=len(samples),
        observation_samples=len(observation_matches),
        speed_mae_ms=_mae([row.speed_delta_ms for row in samples]),
        direction_mae_deg=_mae([row.direction_delta_deg for row in samples]),
        gust_mae_ms=_mae([row.gust_delta_ms for row in samples]),
        observed_speed_mae_ms=observed_speed_mae,
        observed_direction_mae_deg=observed_direction_mae,
        observed_gust_mae_ms=observed_gust_mae,
        legacy_observed_speed_mae_ms=legacy_observed_speed_mae,
        freshness=active.freshness,
    )
    if (
        settings.weather_field_spot_allow_unverified
        and active.freshness in {"fresh", "delayed"}
    ):
        return SpotFieldDecision(True, True, stage, region_slug, (), evidence)
    reasons: list[str] = []
    if active.freshness != "fresh":
        reasons.append(f"active_field_{active.freshness}")
    if evidence.shadow_cycles < settings.weather_field_spot_min_shadow_cycles:
        reasons.append("insufficient_shadow_cycles")
    if evidence.shadow_samples < settings.weather_field_spot_min_shadow_samples:
        reasons.append("insufficient_shadow_samples")
    if evidence.observation_samples < settings.weather_field_spot_min_observations:
        reasons.append("insufficient_operational_observations")
    if evidence.speed_mae_ms is None or evidence.speed_mae_ms > settings.weather_field_spot_max_speed_mae_ms:
        reasons.append("speed_divergence_gate_failed")
    if evidence.direction_mae_deg is None or evidence.direction_mae_deg > settings.weather_field_spot_max_direction_mae_deg:
        reasons.append("direction_divergence_gate_failed")
    if evidence.gust_mae_ms is None or evidence.gust_mae_ms > settings.weather_field_spot_max_gust_mae_ms:
        reasons.append("gust_divergence_gate_failed")
    if (
        evidence.observed_speed_mae_ms is None
        or evidence.observed_speed_mae_ms
        > settings.weather_field_spot_max_observed_speed_mae_ms
    ):
        reasons.append("observed_speed_gate_failed")
    if (
        evidence.observed_direction_mae_deg is None
        or evidence.observed_direction_mae_deg
        > settings.weather_field_spot_max_observed_direction_mae_deg
    ):
        reasons.append("observed_direction_gate_failed")
    if (
        evidence.observed_gust_mae_ms is None
        or evidence.observed_gust_mae_ms
        > settings.weather_field_spot_max_observed_gust_mae_ms
    ):
        reasons.append("observed_gust_gate_failed")
    if (
        evidence.observed_speed_mae_ms is not None
        and evidence.legacy_observed_speed_mae_ms is not None
        and evidence.observed_speed_mae_ms
        > evidence.legacy_observed_speed_mae_ms
        + settings.weather_field_spot_max_speed_regression_ms
    ):
        reasons.append("observed_speed_regression")
    return SpotFieldDecision(
        not reasons, False, stage, region_slug, tuple(reasons), evidence
    )


def _knots(value_ms: float | None) -> float | None:
    if value_ms is None:
        return None
    return round(
        convert_wind_speed(
            value_ms, WindSpeedUnit.METRES_PER_SECOND, WindSpeedUnit.KNOTS
        ),
        1,
    )


def _refresh_day_wind_summary(day: dict) -> None:
    hours = day.get("hours") or []
    winds = [float(row["wind"]) for row in hours if isinstance(row.get("wind"), (int, float))]
    gusts = [float(row["gust"]) for row in hours if isinstance(row.get("gust"), (int, float))]
    summary = day.setdefault("summary", {})
    summary.update(
        wind_avg=round(sum(winds) / len(winds), 1) if winds else None,
        wind_max=round(max(winds), 1) if winds else None,
        gust_max=round(max(gusts), 1) if gusts else None,
        wind_low=None,
        wind_high=None,
    )
    day["confidence_source"] = "calendar"


def apply_field_wind_to_payload(
    payload: dict,
    *,
    latitude: float,
    longitude: float,
    profile,
    sample,
    settings,
) -> tuple[dict, dict]:
    """Replace every available field hour atomically and retain the tail fallback."""

    candidate = deepcopy(payload)
    replaced = 0
    publication_ids: set[str] = set()
    run_ids: set[str] = set()
    model_keys: set[str] = set()
    first_valid_at: str | None = None
    last_valid_at: str | None = None
    for day in candidate.get("days", []):
        day_replaced = 0
        for hour in day.get("hours", []):
            try:
                valid_at = datetime.fromisoformat(str(hour["time"]).replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                continue
            if valid_at.tzinfo is None:
                continue
            valid_at = valid_at.astimezone(timezone.utc)
            try:
                field = sample(valid_at)
            except FieldSampleUnavailable:
                continue
            direction = field.get("direction_from_deg")
            speed = field.get("speed_ms")
            if direction is None or not isinstance(speed, (int, float)) or not math.isfinite(speed):
                continue
            blend = family_blend(
                family_for(str(field["model"])), settings.wind_sector_blend
            )
            corrected = apply_local_physics(float(speed), float(direction), profile, blend=blend)
            gust = field.get("gust_ms")
            corrected_gust = None
            if isinstance(gust, (int, float)) and math.isfinite(gust):
                factor = corrected.speed_ms / float(speed) if speed > 0 else 1.0
                corrected_gust = max(corrected.speed_ms, float(gust) * factor)
            u_ms, v_ms = wind_to_uv(corrected.speed_ms, corrected.direction_deg)
            hour.update(
                wind=_knots(corrected.speed_ms),
                gust=_knots(corrected_gust),
                wind_ms=round(corrected.speed_ms, 3),
                gust_ms=round(corrected_gust, 3) if corrected_gust is not None else None,
                dir=round(corrected.direction_deg, 1),
                wind_u_ms=round(u_ms, 3),
                wind_v_ms=round(v_ms, 3),
                wind_spread=None,
            )
            previous = dict(hour.get("provenance") or {})
            hour["provenance"] = {
                **previous,
                "source_type": "forecast",
                "observation_type": "forecast",
                "source": "weather_field",
                "provider": "Deutscher Wetterdienst",
                "model": field["model"],
                "model_family": family_for(str(field["model"])),
                "model_run_at": field["model_run"],
                "model_run_quality": "exact",
                "valid_at": field["valid_at"],
                "used_coordinate": {"latitude": latitude, "longitude": longitude},
                "spatial_resolution_km": 7.0,
                "temporal_resolution_minutes": 60,
                "stale": field.get("freshness") != "fresh",
                "uncertainty": "not_determined",
                "attribution": [
                    {
                        "provider": "Deutscher Wetterdienst",
                        "text": "Forecast data © Deutscher Wetterdienst",
                    }
                ],
            }
            replaced += 1
            day_replaced += 1
            publication_ids.add(str(field["publication_id"]))
            run_ids.add(str(field["run_id"]))
            model_keys.add(str(field["model"]))
            first_valid_at = first_valid_at or valid_at.isoformat()
            last_valid_at = valid_at.isoformat()
        if day_replaced:
            _refresh_day_wind_summary(day)
    if replaced == 0 or len(publication_ids) != 1 or len(run_ids) != 1 or len(model_keys) != 1:
        raise FieldSampleUnavailable("no coherent weather-field horizon was available")
    return candidate, {
        "source": "weather-field",
        "publication_id": publication_ids.pop(),
        "run_id": run_ids.pop(),
        "model": model_keys.pop(),
        "replaced_hours": replaced,
        "first_valid_at": first_valid_at,
        "last_valid_at": last_valid_at,
        "tail_fallback": "open-meteo",
    }


def apply_spot_field_baseline(
    db,
    *,
    spot: Spot,
    payload: dict,
    settings,
    storage=None,
    now: datetime | None = None,
) -> SpotFieldResult:
    decision = assess_spot_field_readiness(db, spot=spot, settings=settings, now=now)
    if not decision.enabled:
        return SpotFieldResult(payload, False, {"decision": decision.model_dump()})
    if storage is None:
        from app.spatial_fields.storage import configured_field_storage

        storage = configured_field_storage()
    point = to_shape(spot.location)
    weather_profile = db.scalar(
        select(SpotWeatherProfile)
        .where(SpotWeatherProfile.spot_id == spot.id)
        .options(selectinload(SpotWeatherProfile.sectors).load_only(
            SpotWeatherSector.start_deg,
            SpotWeatherSector.end_deg,
            SpotWeatherSector.speed_factor,
            SpotWeatherSector.direction_offset_deg,
            SpotWeatherSector.version,
            SpotWeatherSector.enabled,
            SpotWeatherSector.note,
        ))
    )
    profile = resolve_weather_profile(weather_profile)

    def sample(valid_at: datetime) -> dict:
        return sample_active_field(
            db,
            storage=storage,
            scope_key=settings.weather_field_scope_key,
            latitude=float(point.y),
            longitude=float(point.x),
            valid_at=valid_at,
        )

    try:
        candidate, lineage = apply_field_wind_to_payload(
            payload,
            latitude=float(point.y),
            longitude=float(point.x),
            profile=profile,
            sample=sample,
            settings=settings,
        )
    except (FieldSampleUnavailable, KeyError, TypeError, ValueError) as exc:
        return SpotFieldResult(
            payload,
            False,
            {
                "decision": decision.model_dump(),
                "fallback_reason": type(exc).__name__,
            },
        )
    return SpotFieldResult(
        candidate,
        True,
        {"decision": decision.model_dump(), "lineage": lineage},
    )
