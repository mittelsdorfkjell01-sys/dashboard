"""Reproducible station-minus-model wind residuals in vector space.

This module consumes only the immutable raw-model baseline contract.  It does
not calculate LiveWind and it never feeds a residual back into a forecast.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert

from app.forecast.contracts import NormalizedModelValue
from app.models import (
    WeatherObservation,
    WeatherStation,
    WeatherStationModelResidual,
    WeatherStationPhysicsProfile,
)
from app.weather.catalog import family_for
from app.weather.contracts import ModelFamily
from app.weather.physics import apply_local_physics
from app.weather.physics.blend import family_blend
from app.weather.profiles import QUALITY_TIERS, ResolvedWeatherProfile
from app.weather.station_selection import provider_quality_acceptable
from app.weather.vectors import uv_to_wind, wind_to_uv
from app.weather.weights import normalized_model_weights

RAW_MODEL_BASELINE_VERSION = "raw-model-baseline-v1"
MODEL_ERROR_CALCULATION_VERSION = "station-model-error-uv-v1"
NO_STATION_PHYSICS_VERSION = "none"
EXACT_SAMPLE_VERSION = "exact-run-sample-v1"


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must use UTC")
    return value


class ModelWindPoint(BaseModel):
    """One immutable model vector before calibration, physics or observations."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    baseline_version: str = Field(default=RAW_MODEL_BASELINE_VERSION, min_length=1)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    dataset_version: str | None = None
    model_run_id: str = Field(min_length=1)
    model_run_at: datetime
    model_run_quality: Literal["exact", "provider-reported", "capture-time-only"]
    valid_at: datetime
    fetched_at: datetime
    available_at: datetime | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    grid_distance_km: float = Field(ge=0)
    u_ms: float
    v_ms: float
    gust_ms: float | None = Field(default=None, ge=0, le=150)
    source_key: str = Field(min_length=1)
    source_product: Literal[
        "raw_model", "station_adjusted", "adaptive_forecast"
    ] = "raw_model"
    source_observation_ids: tuple[str, ...] = ()
    asset_hashes: tuple[str, ...] = ()
    asset_content_hashes: tuple[str, ...] = ()
    sample_hash: str | None = None
    sampling_version: str | None = None
    sampling_method: str | None = None
    source_cells: dict = Field(default_factory=dict)
    grid_definition: str | None = None
    model_height_m: float | None = None

    @field_validator("model_run_at", "valid_at", "fetched_at", "available_at")
    @classmethod
    def utc_times(cls, value: datetime, info):
        if value is None and info.field_name == "available_at":
            return None
        return _require_utc(value, info.field_name)

    @model_validator(mode="after")
    def coherent_model_time(self):
        if self.valid_at < self.model_run_at:
            raise ValueError("model valid_at must not precede model_run_at")
        if not math.isfinite(self.u_ms) or not math.isfinite(self.v_ms):
            raise ValueError("model u/v must be finite")
        if math.hypot(self.u_ms, self.v_ms) > 100:
            raise ValueError("model wind vector exceeds supported range")
        return self

    @classmethod
    def from_normalized(
        cls,
        value: NormalizedModelValue,
        *,
        model_run_quality: Literal["exact", "provider-reported"] = "exact",
        baseline_version: str = RAW_MODEL_BASELINE_VERSION,
    ) -> "ModelWindPoint":
        """Bridge direct official model adapters into the shared baseline."""
        run_id = (
            f"{value.source_key}:{value.model}:"
            f"{value.model_run.astimezone(timezone.utc).isoformat()}"
        )
        return cls(
            baseline_version=baseline_version,
            provider=value.provider,
            model_id=value.model,
            dataset_version=value.dataset_version,
            model_run_id=run_id,
            model_run_at=value.model_run.astimezone(timezone.utc),
            model_run_quality=model_run_quality,
            valid_at=value.valid_at.astimezone(timezone.utc),
            fetched_at=value.fetched_at.astimezone(timezone.utc),
            latitude=value.grid_point.latitude,
            longitude=value.grid_point.longitude,
            grid_distance_km=value.grid_point.distance_km,
            u_ms=value.u_ms,
            v_ms=value.v_ms,
            gust_ms=value.gust_ms,
            source_key=value.source_key,
        )


@dataclass(frozen=True)
class StationModelBaseline:
    """The same raw model-state bundle a future LiveWind engine may consume."""

    points: tuple[ModelWindPoint, ...]
    expected_model_ids: tuple[str, ...]
    baseline_version: str = RAW_MODEL_BASELINE_VERSION
    bundle_hash: str | None = None
    bundle_manifest: dict | None = None
    dataset_bundle_hash: str | None = None
    dataset_manifest: dict | None = None
    activation_eligible: bool = False
    member_statuses: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.baseline_version:
            raise ValueError("baseline version is required")
        if len(set(self.expected_model_ids)) != len(self.expected_model_ids):
            raise ValueError("expected model ids must be unique")


class StationModelBaselineLoader(Protocol):
    def __call__(self, station, observation) -> StationModelBaseline: ...


def baseline_from_normalized_values(
    values: list[NormalizedModelValue] | tuple[NormalizedModelValue, ...],
    *,
    expected_model_ids: tuple[str, ...] = (),
    baseline_version: str = RAW_MODEL_BASELINE_VERSION,
) -> StationModelBaseline:
    """Adapt exact-run direct-provider output to the LiveWind/raw baseline."""
    points = tuple(
        ModelWindPoint.from_normalized(
            value,
            baseline_version=baseline_version,
        )
        for value in values
    )
    expected = expected_model_ids or tuple(
        sorted({point.model_id for point in points})
    )
    return StationModelBaseline(
        points=points,
        expected_model_ids=expected,
        baseline_version=baseline_version,
    )


@dataclass(frozen=True)
class StationPhysicsSector:
    start_deg: float
    end_deg: float
    speed_factor: float
    direction_offset_deg: float = 0.0
    enabled: bool = True
    note: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        values = (
            self.start_deg,
            self.end_deg,
            self.speed_factor,
            self.direction_offset_deg,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("station physics sector values must be finite")
        if not 0 <= self.start_deg < 360 or not 0 <= self.end_deg <= 360:
            raise ValueError("station physics sector bounds are invalid")
        if not 0.25 <= self.speed_factor <= 4.0 or self.version < 1:
            raise ValueError("station physics sector factor/version is invalid")


@dataclass(frozen=True)
class ReviewedStationPhysics:
    profile_id: str
    version: int
    physics_version: str
    reviewed_at: datetime
    profile: ResolvedWeatherProfile

    def __post_init__(self) -> None:
        _require_utc(self.reviewed_at, "reviewed_at")
        if not self.profile_id or self.version < 1 or not self.physics_version:
            raise ValueError("reviewed station physics identity is incomplete")


@dataclass(frozen=True)
class ModelErrorPolicy:
    version: str = MODEL_ERROR_CALCULATION_VERSION
    consensus_version: str = "family-uv-v1"
    max_interpolation_span_minutes: int = 180
    max_grid_distance_km: float = 50.0
    max_model_lead_hours: float = 48.0
    minimum_model_members: int = 1
    vector_speed_tolerance_ms: float = 0.20
    vector_direction_tolerance_deg: float = 2.0

    def __post_init__(self) -> None:
        if self.max_interpolation_span_minutes <= 0:
            raise ValueError("interpolation span must be positive")
        if self.max_grid_distance_km <= 0 or self.max_model_lead_hours <= 0:
            raise ValueError("model distance and lead limits must be positive")
        if self.minimum_model_members < 1:
            raise ValueError("at least one model member is required")

    def snapshot(self) -> dict:
        return asdict(self)


DEFAULT_MODEL_ERROR_POLICY = ModelErrorPolicy()


@dataclass(frozen=True)
class StationModelErrorResult:
    analysis_id: str
    calculation_version: str
    baseline_version: str
    analyzed_at: datetime
    station_id: str
    observation_id: str
    observed_at: datetime
    expected_model_ids: tuple[str, ...]
    model_runs: tuple[dict, ...]
    model_members: tuple[dict, ...]
    raw_model_vector: dict
    expected_station_vector: dict
    measurement_vector: dict
    residual_vector: dict
    gust_evidence: dict
    station_profile_id: str | None
    station_profile_version: int | None
    physics_version: str
    physics_applied: bool
    representativeness_uncertainty: str
    qc_status: Literal["accepted", "degraded", "rejected", "unavailable"]
    qc_reasons: tuple[str, ...]
    configuration: dict
    baseline_bundle_hash: str | None = None
    dataset_bundle_hash: str | None = None
    dataset_manifest: dict | None = None
    sample_hash: str | None = None
    sample_manifest: dict | None = None
    activation_eligible: bool = False

    def payload(self) -> dict:
        payload = asdict(self)
        payload["analyzed_at"] = self.analyzed_at.isoformat()
        payload["observed_at"] = self.observed_at.isoformat()
        return payload


@dataclass(frozen=True)
class _InterpolatedMember:
    model_id: str
    model_run_id: str
    model_run_at: datetime
    provider: str
    dataset_version: str | None
    source_key: str
    fetched_at: datetime
    lower: ModelWindPoint
    upper: ModelWindPoint
    fraction: float
    u_ms: float
    v_ms: float
    gust_ms: float | None


def exact_sample_identity(
    baseline: StationModelBaseline,
    members: list[_InterpolatedMember] | tuple[_InterpolatedMember, ...],
    *,
    latitude: float,
    longitude: float,
    valid_at: datetime,
) -> tuple[str, dict]:
    """Hash the spatial and temporal u/v sampling separately from the dataset."""
    if not baseline.dataset_bundle_hash or not baseline.dataset_manifest:
        raise ValueError("exact dataset identity is missing")
    if not members or any(not m.lower.sample_hash or not m.upper.sample_hash for m in members):
        raise ValueError("exact endpoint sample identity is missing")
    manifest = {
        "sampling_version": EXACT_SAMPLE_VERSION,
        "dataset_bundle_hash": baseline.dataset_bundle_hash,
        "coordinate": {"latitude": float(latitude), "longitude": float(longitude)},
        "valid_at": _require_utc(valid_at, "valid_at").isoformat(),
        "members": [
            {
                "model": member.model_id,
                "run_id": member.model_run_id,
                "lower_valid_at": member.lower.valid_at.isoformat(),
                "upper_valid_at": member.upper.valid_at.isoformat(),
                "temporal_weight_upper": round(member.fraction, 9),
                "lower_sample_hash": member.lower.sample_hash,
                "upper_sample_hash": member.upper.sample_hash,
                "asset_content_hashes": sorted({
                    *member.lower.asset_content_hashes,
                    *member.upper.asset_content_hashes,
                }),
                "source_cells": {
                    "lower": member.lower.source_cells,
                    "upper": member.upper.source_cells,
                },
                "u_ms": round(member.u_ms, 9),
                "v_ms": round(member.v_ms, 9),
            }
            for member in sorted(members, key=lambda item: item.model_id)
        ],
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), manifest


def _finite(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _aware_utc(value) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def _direction_difference(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def _vector_payload(u_ms: float, v_ms: float) -> dict:
    speed, direction = uv_to_wind(u_ms, v_ms)
    return {
        "u_ms": round(u_ms, 9),
        "v_ms": round(v_ms, 9),
        "speed_ms": round(speed, 9),
        "direction_from_deg": None if direction is None else round(direction, 9),
    }


def _observation_gate_reasons(
    station,
    observation,
    *,
    analyzed_at: datetime,
    policy: ModelErrorPolicy,
) -> list[str]:
    reasons = []
    if not getattr(station, "active", False):
        reasons.append("station_inactive")
    if not getattr(station, "approved", False):
        reasons.append("station_unapproved")
    if not getattr(station, "residual_approved", False):
        reasons.append("station_residual_scope_unapproved")
    if getattr(station, "identity_review_status", "unreviewed") != "passed":
        reasons.append("station_identity_unreviewed")
    if not getattr(station, "physical_station_group", None) or not getattr(station, "correlation_group", None):
        reasons.append("station_dependency_group_unreviewed")
    if getattr(station, "blocked", False):
        reasons.append("station_blocked")
    if getattr(station, "representativeness_status", "unreviewed") != "passed":
        reasons.append("representativeness_unpassed")
    if getattr(observation, "station_id", None) != getattr(station, "id", None):
        reasons.append("observation_station_mismatch")
    if getattr(observation, "import_status", None) != "accepted":
        reasons.append("observation_not_accepted")
    from app.weather.observation_quality import QC_VERSION
    if getattr(observation, "qc_version", None) != QC_VERSION or getattr(observation, "qc_flags", None):
        reasons.append("observation_qc_unqualified")
    if getattr(observation, "qc_stage", None) not in {"eligible_for_residuals", "eligible_for_holdout"}:
        reasons.append("observation_qc_stage_unqualified")
    received_at = _aware_utc(getattr(observation, "received_at", None))
    imported_at = _aware_utc(getattr(observation, "imported_at", None))
    if received_at is None or imported_at is None or received_at > analyzed_at or imported_at > analyzed_at:
        reasons.append("observation_not_available_at_cutoff")
    if not provider_quality_acceptable(observation):
        reasons.append("provider_quality_rejected")

    observed_at = _aware_utc(getattr(observation, "observed_at", None))
    if observed_at is None:
        reasons.append("observation_time_invalid")
    elif observed_at > analyzed_at + timedelta(minutes=2):
        reasons.append("observation_future")
    u_ms = _finite(getattr(observation, "wind_u_ms", None))
    v_ms = _finite(getattr(observation, "wind_v_ms", None))
    speed = _finite(getattr(observation, "wind_speed_ms", None))
    direction = _finite(getattr(observation, "wind_direction_deg", None))
    if u_ms is None or v_ms is None or speed is None or not 0 <= speed <= 75:
        reasons.append("measurement_vector_invalid")
    else:
        vector_speed, vector_direction = uv_to_wind(u_ms, v_ms)
        if abs(vector_speed - speed) > policy.vector_speed_tolerance_ms:
            reasons.append("measurement_vector_inconsistent")
        if speed > policy.vector_speed_tolerance_ms:
            if direction is None or not 0 <= direction < 360:
                reasons.append("measurement_direction_invalid")
            elif vector_direction is None or _direction_difference(
                vector_direction, direction
            ) > policy.vector_direction_tolerance_deg:
                reasons.append("measurement_vector_inconsistent")
    return list(dict.fromkeys(reasons))


def resolve_reviewed_station_physics(record) -> ReviewedStationPhysics | None:
    """Resolve a DB/profile-like row only after its explicit review gate."""
    if (
        record is None
        or not getattr(record, "active", False)
        or getattr(record, "status", None) != "reviewed"
    ):
        return None
    reviewed_at = _aware_utc(getattr(record, "reviewed_at", None))
    payload = getattr(record, "profile", None)
    if reviewed_at is None or not isinstance(payload, dict):
        return None
    try:
        sectors = tuple(
            StationPhysicsSector(
                start_deg=float(item["start_deg"]),
                end_deg=float(item["end_deg"]),
                speed_factor=float(item["speed_factor"]),
                direction_offset_deg=float(item.get("direction_offset_deg", 0.0)),
                enabled=bool(item.get("enabled", True)),
                note=item.get("note"),
                version=int(item.get("version", getattr(record, "version"))),
            )
            for item in payload.get("sectors", ())
            if isinstance(item, dict)
        )
        version = int(getattr(record, "version"))
        physics_version = str(getattr(record, "physics_version"))
        if version < 1 or not physics_version:
            return None
        quality_tier = str(getattr(record, "quality_tier", "coordinates"))
        if quality_tier not in QUALITY_TIERS:
            return None
        profile = ResolvedWeatherProfile(
            active=True,
            quality_tier=quality_tier,
            coastal_normal_deg=(
                float(record.coastal_normal_deg)
                if getattr(record, "coastal_normal_deg", None) is not None
                else None
            ),
            reviewed_at=reviewed_at,
            sectors=sectors,
        )
    except (KeyError, TypeError, ValueError):
        return None
    return ReviewedStationPhysics(
        profile_id=str(getattr(record, "id")),
        version=version,
        physics_version=physics_version,
        reviewed_at=reviewed_at,
        profile=profile,
    )


def load_reviewed_station_physics(db, station_id) -> ReviewedStationPhysics | None:
    record = db.scalar(
        select(WeatherStationPhysicsProfile).where(
            WeatherStationPhysicsProfile.station_id == station_id,
            WeatherStationPhysicsProfile.active.is_(True),
            WeatherStationPhysicsProfile.status == "reviewed",
        )
    )
    return resolve_reviewed_station_physics(record)


def _interpolate_run(
    points: list[ModelWindPoint],
    observed_at: datetime,
    *,
    policy: ModelErrorPolicy,
) -> tuple[_InterpolatedMember | None, str | None]:
    by_time: dict[datetime, ModelWindPoint] = {}
    for point in sorted(
        points,
        key=lambda item: (item.valid_at, item.fetched_at, item.source_key),
    ):
        previous = by_time.get(point.valid_at)
        if previous is not None:
            same_value = (
                previous.baseline_version == point.baseline_version
                and previous.provider == point.provider
                and previous.dataset_version == point.dataset_version
                and math.isclose(previous.latitude, point.latitude, abs_tol=1e-9)
                and math.isclose(previous.longitude, point.longitude, abs_tol=1e-9)
                and math.isclose(
                    previous.grid_distance_km, point.grid_distance_km, abs_tol=1e-9
                )
                and math.isclose(previous.u_ms, point.u_ms, abs_tol=1e-9)
                and math.isclose(previous.v_ms, point.v_ms, abs_tol=1e-9)
                and (
                    previous.gust_ms is None
                    and point.gust_ms is None
                    or previous.gust_ms is not None
                    and point.gust_ms is not None
                    and math.isclose(previous.gust_ms, point.gust_ms, abs_tol=1e-9)
                )
                and previous.source_product == point.source_product
                and previous.source_observation_ids == point.source_observation_ids
            )
            if not same_value:
                return None, "model_time_conflict"
        by_time[point.valid_at] = point
    ordered = list(by_time.values())
    exact = next((point for point in ordered if point.valid_at == observed_at), None)
    if exact is not None:
        lower = upper = exact
        fraction = 0.0
    else:
        lowers = [point for point in ordered if point.valid_at < observed_at]
        uppers = [point for point in ordered if point.valid_at > observed_at]
        if not lowers or not uppers:
            return None, "model_time_not_bracketed"
        lower, upper = lowers[-1], uppers[0]
        span = upper.valid_at - lower.valid_at
        if span > timedelta(minutes=policy.max_interpolation_span_minutes):
            return None, "model_interpolation_span_exceeded"
        fraction = (observed_at - lower.valid_at).total_seconds() / span.total_seconds()
    u_ms = lower.u_ms + (upper.u_ms - lower.u_ms) * fraction
    v_ms = lower.v_ms + (upper.v_ms - lower.v_ms) * fraction
    gust_ms = None
    if lower.gust_ms is not None and upper.gust_ms is not None:
        gust_ms = lower.gust_ms + (upper.gust_ms - lower.gust_ms) * fraction
    return _InterpolatedMember(
        model_id=lower.model_id,
        model_run_id=lower.model_run_id,
        model_run_at=lower.model_run_at,
        provider=lower.provider,
        dataset_version=lower.dataset_version,
        source_key=lower.source_key,
        fetched_at=max(lower.fetched_at, upper.fetched_at),
        lower=lower,
        upper=upper,
        fraction=fraction,
        u_ms=u_ms,
        v_ms=v_ms,
        gust_ms=gust_ms,
    ), None


def _interpolate_member(
    points: list[ModelWindPoint],
    observed_at: datetime,
    *,
    policy: ModelErrorPolicy,
) -> tuple[_InterpolatedMember | None, str | None]:
    if not points:
        return None, "model_member_missing"
    safe = [
        point
        for point in points
        if point.model_run_at < observed_at
        and (observed_at - point.model_run_at).total_seconds() / 3600
        <= policy.max_model_lead_hours
        and point.grid_distance_km <= policy.max_grid_distance_km
    ]
    if not safe:
        if any(point.model_run_at >= observed_at for point in points):
            return None, "model_run_not_prior_to_observation"
        if any(point.grid_distance_km > policy.max_grid_distance_km for point in points):
            return None, "model_grid_too_distant"
        return None, "model_lead_exceeded"
    runs: dict[tuple[str, datetime], list[ModelWindPoint]] = {}
    for point in safe:
        runs.setdefault((point.model_run_id, point.model_run_at), []).append(point)
    errors = []
    for _, run_points in sorted(
        runs.items(), key=lambda item: item[0][1], reverse=True
    ):
        interpolated, error = _interpolate_run(
            run_points, observed_at, policy=policy
        )
        if interpolated is not None:
            return interpolated, None
        if error:
            errors.append(error)
    return None, errors[0] if errors else "model_member_missing"


def _analysis_id(
    station,
    observation,
    baseline: StationModelBaseline,
    profile: ReviewedStationPhysics | None,
    policy: ModelErrorPolicy,
    blend_overrides: dict[str, float] | None,
) -> str:
    ordered_points = sorted(
        baseline.points,
        key=lambda point: json.dumps(
            point.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    payload = {
        "station": _station_snapshot(station),
        "observation": _observation_snapshot(observation),
        "baseline_version": baseline.baseline_version,
        "bundle_hash": baseline.bundle_hash,
        "bundle_manifest": baseline.bundle_manifest,
        "dataset_bundle_hash": baseline.dataset_bundle_hash,
        "dataset_manifest": baseline.dataset_manifest,
        "activation_eligible": baseline.activation_eligible,
        "member_statuses": baseline.member_statuses,
        "expected_model_ids": sorted(baseline.expected_model_ids),
        "points": [point.model_dump(mode="json") for point in ordered_points],
        "station_profile": _station_profile_snapshot(profile),
        "configuration": policy.snapshot(),
        "physics_blend": _blend_snapshot(blend_overrides),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _station_profile_snapshot(
    profile: ReviewedStationPhysics | None,
) -> dict | None:
    if profile is None:
        return None
    return {
        "id": profile.profile_id,
        "version": profile.version,
        "physics_version": profile.physics_version,
        "reviewed_at": profile.reviewed_at.isoformat(),
        "quality_tier": profile.profile.quality_tier,
        "coastal_normal_deg": profile.profile.coastal_normal_deg,
        "sectors": [
            {
                "start_deg": sector.start_deg,
                "end_deg": sector.end_deg,
                "speed_factor": sector.speed_factor,
                "direction_offset_deg": sector.direction_offset_deg,
                "enabled": sector.enabled,
                "note": sector.note,
                "version": sector.version,
            }
            for sector in profile.profile.sectors
        ],
    }


def _station_snapshot(station) -> dict:
    return {
        "id": str(getattr(station, "id", "")),
        "active": bool(getattr(station, "active", False)),
        "approved": bool(getattr(station, "approved", False)),
        "blocked": bool(getattr(station, "blocked", False)),
        "representativeness_status": getattr(
            station, "representativeness_status", None
        ),
    }


def _observation_snapshot(observation) -> dict:
    observed_at = _aware_utc(getattr(observation, "observed_at", None))
    return {
        "id": str(getattr(observation, "id", "")),
        "station_id": str(getattr(observation, "station_id", "")),
        "observed_at": observed_at.isoformat() if observed_at else None,
        "wind_speed_ms": _finite(getattr(observation, "wind_speed_ms", None)),
        "wind_direction_deg": _finite(
            getattr(observation, "wind_direction_deg", None)
        ),
        "wind_u_ms": _finite(getattr(observation, "wind_u_ms", None)),
        "wind_v_ms": _finite(getattr(observation, "wind_v_ms", None)),
        "wind_gust_ms": _finite(getattr(observation, "wind_gust_ms", None)),
        "gust_period_seconds": getattr(observation, "gust_period_seconds", None),
        "provider_quality": getattr(observation, "provider_quality", None),
        "import_status": getattr(observation, "import_status", None),
    }


def _blend_snapshot(blend_overrides: dict[str, float] | None) -> dict[str, float]:
    return {
        str(family): family_blend(family, blend_overrides)
        for family in ModelFamily
    }


def calculate_station_model_error(
    station,
    observation,
    baseline: StationModelBaseline,
    *,
    station_physics: ReviewedStationPhysics | None = None,
    analyzed_at: datetime | None = None,
    policy: ModelErrorPolicy = DEFAULT_MODEL_ERROR_POLICY,
    blend_overrides: dict[str, float] | None = None,
) -> StationModelErrorResult:
    """Calculate ``measurement_uv - expected_station_model_uv`` once."""
    analysis_time = _require_utc(
        analyzed_at or datetime.now(timezone.utc), "analyzed_at"
    )
    observed_at = _aware_utc(getattr(observation, "observed_at", None))
    if observed_at is None:
        observed_at = analysis_time
    station_id = str(getattr(station, "id", ""))
    observation_id = str(getattr(observation, "id", ""))
    analysis_id = _analysis_id(
        station,
        observation,
        baseline,
        station_physics,
        policy,
        blend_overrides,
    )
    gate_reasons = _observation_gate_reasons(
        station, observation, analyzed_at=analysis_time, policy=policy
    )
    lineage_reasons = []
    if any(point.source_product != "raw_model" for point in baseline.points):
        lineage_reasons.append("adjusted_model_input_forbidden")
    if any(point.source_observation_ids for point in baseline.points):
        lineage_reasons.append("observation_derived_model_input_forbidden")
    if any(
        point.model_run_quality not in {"exact", "provider-reported"}
        for point in baseline.points
    ):
        lineage_reasons.append("model_run_identity_not_verified")
    if any(point.baseline_version != baseline.baseline_version for point in baseline.points):
        lineage_reasons.append("baseline_version_mismatch")
    if baseline.baseline_version == "exact-run-bundle-v1":
        lineage_reasons.append("legacy_capture_time_baseline")
    if baseline.baseline_version == "exact-run-bundle-v2":
        if not baseline.activation_eligible or not baseline.dataset_bundle_hash or not baseline.dataset_manifest:
            lineage_reasons.append("not_activation_eligible")
        elif hashlib.sha256(json.dumps(
            baseline.dataset_manifest, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest() != baseline.dataset_bundle_hash:
            lineage_reasons.append("dataset_bundle_hash_mismatch")
        else:
            from app.weather.exact_run import compatible_dataset_manifests

            manifest = baseline.dataset_manifest
            if (not compatible_dataset_manifests(manifest, manifest)
                    or tuple(manifest["required_models"]) != baseline.expected_model_ids):
                lineage_reasons.append("dataset_manifest_incompatible")
            else:
                for point in baseline.points:
                    member = manifest["members"].get(point.model_id)
                    if (not isinstance(member, dict)
                            or point.provider != member.get("provider")
                            or point.model_run_at.isoformat() != member.get("run_at")
                            or point.dataset_version != member.get("dataset_version")
                            or point.valid_at.isoformat() not in member.get("valid_times", ())
                            or point.sampling_version != EXACT_SAMPLE_VERSION):
                        lineage_reasons.append("dataset_point_mismatch")
                        break
        if any(point.available_at is None or point.available_at > observed_at for point in baseline.points):
            lineage_reasons.append("run_not_available_as_of_observation")
        if any(not point.sample_hash or not point.asset_content_hashes for point in baseline.points):
            lineage_reasons.append("sample_identity_unavailable")

    uncertainty = (
        "reviewed_station_profile"
        if station_physics is not None
        else "elevated_no_reviewed_station_profile"
    )
    input_model_runs = tuple(
        {
            "model_id": point.model_id,
            "provider": point.provider,
            "model_run_id": point.model_run_id,
            "model_run_at": point.model_run_at.isoformat(),
            "model_run_quality": point.model_run_quality,
            "valid_at": point.valid_at.isoformat(),
            "fetched_at": point.fetched_at.isoformat(),
            "dataset_version": point.dataset_version,
            "source_key": point.source_key,
            "latitude": point.latitude,
            "longitude": point.longitude,
            "grid_distance_km": point.grid_distance_km,
            "source_product": point.source_product,
            "source_observation_ids": list(point.source_observation_ids),
            "available_at": point.available_at.isoformat() if point.available_at else None,
            "asset_hashes": list(point.asset_hashes),
            "asset_content_hashes": list(point.asset_content_hashes),
            "sample_hash": point.sample_hash,
            "sampling_version": point.sampling_version,
            "sampling_method": point.sampling_method,
            "source_cells": point.source_cells,
            "grid_definition": point.grid_definition,
            "model_height_m": point.model_height_m,
        }
        for point in baseline.points
    )
    measured_u = _finite(getattr(observation, "wind_u_ms", None))
    measured_v = _finite(getattr(observation, "wind_v_ms", None))
    measurement_vector = (
        _vector_payload(measured_u, measured_v)
        if measured_u is not None and measured_v is not None
        else {}
    )
    empty = {
        "analysis_id": analysis_id,
        "calculation_version": policy.version,
        "baseline_version": baseline.baseline_version,
        "analyzed_at": analysis_time,
        "station_id": station_id,
        "observation_id": observation_id,
        "observed_at": observed_at,
        "expected_model_ids": baseline.expected_model_ids,
        "model_runs": input_model_runs,
        "model_members": (),
        "raw_model_vector": {},
        "expected_station_vector": {},
        "measurement_vector": measurement_vector,
        "residual_vector": {},
        "gust_evidence": {"status": "unavailable"},
        "station_profile_id": (
            station_physics.profile_id if station_physics else None
        ),
        "station_profile_version": (
            station_physics.version if station_physics else None
        ),
        "physics_version": (
            station_physics.physics_version
            if station_physics
            else NO_STATION_PHYSICS_VERSION
        ),
        "physics_applied": False,
        "representativeness_uncertainty": uncertainty,
        "configuration": {
            "policy": policy.snapshot(),
            "physics_blend": _blend_snapshot(blend_overrides),
            "station": _station_snapshot(station),
            "observation": _observation_snapshot(observation),
            "station_profile": _station_profile_snapshot(station_physics),
            "baseline_bundle": baseline.bundle_manifest,
            "dataset_bundle": baseline.dataset_manifest,
            "member_statuses": baseline.member_statuses or {},
        },
        "baseline_bundle_hash": baseline.bundle_hash,
        "dataset_bundle_hash": baseline.dataset_bundle_hash,
        "dataset_manifest": baseline.dataset_manifest,
        "sample_hash": None,
        "sample_manifest": None,
        "activation_eligible": (
            baseline.activation_eligible and baseline.baseline_version == "exact-run-bundle-v2"
        ),
    }
    blocking = list(dict.fromkeys([*gate_reasons, *lineage_reasons]))
    if blocking:
        return StationModelErrorResult(
            **{**empty, "activation_eligible": False},
            qc_status="unavailable" if "not_activation_eligible" in blocking else "rejected",
            qc_reasons=tuple(dict.fromkeys([*blocking, *(baseline.member_statuses or {}).values()])),
        )

    model_ids = tuple(sorted(
        baseline.expected_model_ids
        or {point.model_id for point in baseline.points}
    ))
    members = []
    missing_reasons = []
    for model_id in model_ids:
        interpolated, error = _interpolate_member(
            [point for point in baseline.points if point.model_id == model_id],
            observed_at,
            policy=policy,
        )
        if interpolated is None:
            missing_reasons.append(f"{error or 'model_member_missing'}:{model_id}")
        else:
            members.append(interpolated)
    if len(members) < policy.minimum_model_members or (
        baseline.baseline_version == "exact-run-bundle-v2" and len(members) != len(model_ids)
    ):
        return StationModelErrorResult(
            **{**empty, "activation_eligible": False},
            qc_status="unavailable",
            qc_reasons=tuple(missing_reasons or ["model_members_unavailable"]),
        )

    if baseline.baseline_version == "exact-run-bundle-v2":
        try:
            sample_hash, sample_manifest = exact_sample_identity(
                baseline, members,
                latitude=float(station.latitude), longitude=float(station.longitude),
                valid_at=observed_at,
            )
        except (AttributeError, TypeError, ValueError):
            return StationModelErrorResult(
                **{**empty, "activation_eligible": False},
                qc_status="unavailable", qc_reasons=("sample_identity_unavailable",),
            )
        empty["sample_hash"] = sample_hash
        empty["sample_manifest"] = sample_manifest

    lead_hours = max(
        (observed_at - member.model_run_at).total_seconds() / 3600
        for member in members
    )
    weights = normalized_model_weights(
        ((member.model_id, family_for(member.model_id)) for member in members),
        lead_hours,
    )
    raw_u = sum(member.u_ms * weights[member.model_id] for member in members)
    raw_v = sum(member.v_ms * weights[member.model_id] for member in members)
    expected_u = expected_v = 0.0
    physics_applied = False
    member_evidence = []
    for member in members:
        expected_member_u, expected_member_v = member.u_ms, member.v_ms
        component = None
        blend = 0.0
        if station_physics is not None:
            speed, direction = uv_to_wind(member.u_ms, member.v_ms)
            if direction is not None:
                blend = family_blend(
                    family_for(member.model_id), blend_overrides
                )
                applied = apply_local_physics(
                    speed,
                    direction,
                    station_physics.profile,
                    blend=blend,
                )
                expected_member_u, expected_member_v = wind_to_uv(
                    applied.speed_ms, applied.direction_deg
                )
                component = applied.applied_component
                physics_applied = physics_applied or applied.corrected
        weight = weights[member.model_id]
        expected_u += expected_member_u * weight
        expected_v += expected_member_v * weight
        member_evidence.append({
            "model_id": member.model_id,
            "provider": member.provider,
            "dataset_version": member.dataset_version,
            "source_key": member.source_key,
            "available_at": member.lower.available_at.isoformat() if member.lower.available_at else None,
            "asset_hashes": sorted({*member.lower.asset_hashes, *member.upper.asset_hashes}),
            "asset_content_hashes": sorted({
                *member.lower.asset_content_hashes, *member.upper.asset_content_hashes,
            }),
            "endpoint_sample_hashes": [member.lower.sample_hash, member.upper.sample_hash],
            "sampling_method": member.lower.sampling_method,
            "source_cells": {"lower": member.lower.source_cells, "upper": member.upper.source_cells},
            "grid_definition": member.lower.grid_definition,
            "model_height_m": member.lower.model_height_m,
            "model_run_id": member.model_run_id,
            "model_run_at": member.model_run_at.isoformat(),
            "valid_at": observed_at.isoformat(),
            "fetched_at": member.fetched_at.isoformat(),
            "interpolation": {
                "space": "u/v",
                "lower_valid_at": member.lower.valid_at.isoformat(),
                "upper_valid_at": member.upper.valid_at.isoformat(),
                "fraction": round(member.fraction, 9),
                "lower": {
                    "valid_at": member.lower.valid_at.isoformat(),
                    "vector": _vector_payload(
                        member.lower.u_ms, member.lower.v_ms
                    ),
                    "gust_ms": member.lower.gust_ms,
                    "latitude": member.lower.latitude,
                    "longitude": member.lower.longitude,
                    "grid_distance_km": member.lower.grid_distance_km,
                },
                "upper": {
                    "valid_at": member.upper.valid_at.isoformat(),
                    "vector": _vector_payload(
                        member.upper.u_ms, member.upper.v_ms
                    ),
                    "gust_ms": member.upper.gust_ms,
                    "latitude": member.upper.latitude,
                    "longitude": member.upper.longitude,
                    "grid_distance_km": member.upper.grid_distance_km,
                },
            },
            "raw_vector": _vector_payload(member.u_ms, member.v_ms),
            "expected_station_vector": _vector_payload(
                expected_member_u, expected_member_v
            ),
            "raw_gust_ms": member.gust_ms,
            "consensus_weight": round(weight, 9),
            "physics_blend": round(blend, 9),
            "physics_component": component,
        })

    measured_u = float(observation.wind_u_ms)
    measured_v = float(observation.wind_v_ms)
    residual_u = measured_u - expected_u
    residual_v = measured_v - expected_v
    gust_members = [member for member in members if member.gust_ms is not None]
    gust_weight = sum(weights[member.model_id] for member in gust_members)
    raw_gust = (
        sum(
            float(member.gust_ms) * weights[member.model_id]
            for member in gust_members
        )
        / gust_weight
        if gust_weight
        else None
    )
    measured_gust = _finite(getattr(observation, "wind_gust_ms", None))
    gust_evidence = {
        "status": (
            "calculated"
            if raw_gust is not None and measured_gust is not None
            else "unavailable"
        ),
        "raw_model_gust_ms": raw_gust,
        # No mean-wind vector correction is silently reused for gusts.
        "expected_station_gust_ms": raw_gust,
        "measurement_gust_ms": measured_gust,
        "measurement_gust_period_seconds": getattr(
            observation, "gust_period_seconds", None
        ),
        "residual_gust_ms": (
            measured_gust - raw_gust
            if raw_gust is not None and measured_gust is not None
            else None
        ),
        "physics_applied": False,
        "method": "separate_scalar_gust_residual",
    }
    qc_reasons = list(missing_reasons)
    if station_physics is None:
        qc_reasons.append("station_profile_missing")
    if len(members) == 1:
        qc_reasons.append("single_model_member")
    qc_status = "degraded" if qc_reasons else "accepted"
    model_runs = tuple(
        {
            "model_id": member.model_id,
            "provider": member.provider,
            "model_run_id": member.model_run_id,
            "model_run_at": member.model_run_at.isoformat(),
            "model_run_quality": member.lower.model_run_quality,
            "valid_at": observed_at.isoformat(),
        }
        for member in members
    )
    return StationModelErrorResult(**{
        **empty,
        "expected_model_ids": model_ids,
        "model_runs": model_runs,
        "model_members": tuple(member_evidence),
        "raw_model_vector": _vector_payload(raw_u, raw_v),
        "expected_station_vector": _vector_payload(expected_u, expected_v),
        "measurement_vector": _vector_payload(measured_u, measured_v),
        "residual_vector": _vector_payload(residual_u, residual_v),
        "gust_evidence": gust_evidence,
        "physics_applied": physics_applied,
        "qc_status": qc_status,
        "qc_reasons": tuple(dict.fromkeys(qc_reasons)),
    })


def persist_station_model_error(db, result: StationModelErrorResult) -> None:
    """Idempotently persist immutable evidence; transaction ownership stays outside."""
    values = {
        "station_id": result.station_id,
        "observation_id": result.observation_id,
        "station_profile_id": result.station_profile_id,
        "analysis_id": result.analysis_id,
        "calculation_version": result.calculation_version,
        "baseline_version": result.baseline_version,
        "analyzed_at": result.analyzed_at,
        "observed_at": result.observed_at,
        "model_runs": list(result.model_runs),
        "model_members": list(result.model_members),
        "raw_model_vector": result.raw_model_vector,
        "expected_station_vector": result.expected_station_vector,
        "measurement_vector": result.measurement_vector,
        "residual_vector": result.residual_vector,
        "gust_evidence": result.gust_evidence,
        "station_profile_version": result.station_profile_version,
        "physics_version": result.physics_version,
        "physics_applied": result.physics_applied,
        "model_member_count": len(result.model_members),
        "representativeness_uncertainty": result.representativeness_uncertainty,
        "qc_status": result.qc_status,
        "qc_reasons": list(result.qc_reasons),
        "configuration": result.configuration,
        "baseline_bundle_hash": result.baseline_bundle_hash,
        "dataset_bundle_hash": result.dataset_bundle_hash,
        "dataset_manifest": result.dataset_manifest,
        "sample_hash": result.sample_hash,
        "sample_manifest": result.sample_manifest,
        "activation_eligible": result.activation_eligible,
    }
    db.execute(
        insert(WeatherStationModelResidual)
        .values(values)
        .on_conflict_do_nothing(
            constraint="uq_weather_station_model_residual_evidence"
        )
    )


def calculate_and_persist_station_model_error(
    db,
    station,
    observation,
    baseline: StationModelBaseline,
    *,
    analyzed_at: datetime | None = None,
    policy: ModelErrorPolicy = DEFAULT_MODEL_ERROR_POLICY,
    blend_overrides: dict[str, float] | None = None,
) -> StationModelErrorResult:
    station_physics = load_reviewed_station_physics(db, station.id)
    result = calculate_station_model_error(
        station,
        observation,
        baseline,
        station_physics=station_physics,
        analyzed_at=analyzed_at,
        policy=policy,
        blend_overrides=blend_overrides,
    )
    from app.weather.station_approval import scope_valid
    if not scope_valid(db, station, observation, scope="residual_source",
                       analyzed_at=result.analyzed_at):
        result = replace(result, qc_status="rejected", activation_eligible=False,
                         qc_reasons=tuple(dict.fromkeys((*result.qc_reasons,
                             "epoch_scope_or_dossier_unqualified"))))
    persist_station_model_error(db, result)
    return result


def run_station_model_error_analysis(
    db,
    baseline_loader: StationModelBaselineLoader,
    *,
    limit: int = 25,
    analyzed_at: datetime | None = None,
    policy: ModelErrorPolicy = DEFAULT_MODEL_ERROR_POLICY,
    blend_overrides: dict[str, float] | None = None,
    dry_run: bool = False,
    recent_hours: int | None = None,
    skip_exact_attempted: bool = False,
    require_exact: bool = False,
) -> dict:
    """Drain suitable observations without coupling imports to model I/O.

    A caller supplies the same immutable baseline loader intended for LiveWind.
    Only an accepted/degraded residual marks an observation complete; an
    unavailable model result may therefore be retried with a later baseline.
    The exact-run scheduled worker limits itself to recent observations and
    skips previously attempted exact evidence: a first-seen timestamp cannot
    be backdated to rescue an unavailable historical observation.
    Provider failures are isolated per observation.
    """
    analysis_time = _require_utc(
        analyzed_at or datetime.now(timezone.utc), "analyzed_at"
    )
    completed = exists(
        select(WeatherStationModelResidual.id).where(
            WeatherStationModelResidual.observation_id == WeatherObservation.id,
            WeatherStationModelResidual.qc_status.in_(("accepted", "degraded")),
            *([WeatherStationModelResidual.baseline_version == "exact-run-bundle-v2"] if require_exact else []),
        )
    )
    exact_attempted = exists(
        select(WeatherStationModelResidual.id).where(
            WeatherStationModelResidual.observation_id == WeatherObservation.id,
            WeatherStationModelResidual.baseline_version == "exact-run-bundle-v2",
        )
    )
    rows = db.execute(
        select(WeatherStation, WeatherObservation)
        .join(
            WeatherObservation,
            WeatherObservation.station_id == WeatherStation.id,
        )
        .where(
            WeatherStation.active.is_(True),
            WeatherStation.approved.is_(True),
            WeatherStation.residual_approved.is_(True),
            WeatherStation.identity_review_status == "passed",
            WeatherStation.physical_station_group.is_not(None),
            WeatherStation.correlation_group.is_not(None),
            WeatherStation.blocked.is_(False),
            WeatherStation.representativeness_status == "passed",
            WeatherObservation.import_status == "accepted",
            WeatherObservation.qc_version == "station-observation-qc-v1",
            WeatherObservation.qc_stage.in_(("eligible_for_residuals", "eligible_for_holdout")),
            WeatherObservation.qc_flags == [],
            WeatherObservation.availability_class == "captured_operationally",
            WeatherObservation.epoch_id == WeatherStation.current_epoch_id,
            WeatherObservation.received_at <= analysis_time,
            WeatherObservation.imported_at <= analysis_time,
            WeatherObservation.wind_u_ms.is_not(None),
            WeatherObservation.wind_v_ms.is_not(None),
            *(
                [WeatherObservation.observed_at >= analysis_time - timedelta(hours=recent_hours),
                 WeatherObservation.observed_at <= analysis_time]
                if recent_hours is not None else []
            ),
            ~completed,
            *([~exact_attempted] if skip_exact_attempted else []),
        )
        .order_by(WeatherObservation.observed_at, WeatherObservation.id)
        .limit(max(1, limit))
    ).all()
    report = {
        "selected": len(rows),
        "accepted": 0,
        "degraded": 0,
        "rejected": 0,
        "unavailable": 0,
        "errors": 0,
        "dry_run": dry_run,
        "calculation_version": policy.version,
        "items": [],
    }
    for station, observation in rows:
        try:
            from app.weather.station_approval import scope_valid
            if not scope_valid(db, station, observation, scope="residual_source",
                               analyzed_at=analysis_time):
                report["rejected"] += 1
                report["items"].append({"station_id": str(station.id),
                                        "observation_id": str(observation.id),
                                        "reason": "epoch_scope_or_dossier_unqualified"})
                continue
            baseline = baseline_loader(station, observation)
            station_physics = load_reviewed_station_physics(db, station.id)
            result = calculate_station_model_error(
                station,
                observation,
                baseline,
                station_physics=station_physics,
                analyzed_at=analysis_time,
                policy=policy,
                blend_overrides=blend_overrides,
            )
            if not dry_run:
                persist_station_model_error(db, result)
                db.commit()
            report[result.qc_status] += 1
            report["items"].append({
                "station_id": str(station.id),
                "observation_id": str(observation.id),
                "analysis_id": result.analysis_id,
                "qc_status": result.qc_status,
                "qc_reasons": list(result.qc_reasons),
            })
        except Exception as exc:
            rollback = getattr(db, "rollback", None)
            if rollback is not None:
                rollback()
            report["errors"] += 1
            report["items"].append({
                "station_id": str(station.id),
                "observation_id": str(observation.id),
                "error_class": type(exc).__name__,
            })
    return report
