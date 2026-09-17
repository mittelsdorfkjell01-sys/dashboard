"""Serving integration for the regional LiveWind analysis product."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import asdict
import hashlib
import json
import math
import uuid

from sqlalchemy import select

from app.models import WeatherStationModelResidual
from app.weather.live_wind_analysis import (
    REGIONAL_LIVE_WIND_VERSION,
    StationResidualInput,
    TargetModelState,
    analyze_regional_live_wind,
)
from app.weather.model_error import (
    MODEL_ERROR_CALCULATION_VERSION,
    RAW_MODEL_BASELINE_VERSION,
)
from app.weather.physics import apply_local_physics
from app.weather.profiles import resolve_weather_profile
from app.weather.station_selection import select_stations_for_spot
from app.weather.vectors import uv_to_wind, wind_to_uv

LIVE_WIND_ANALYSIS_TTL_MINUTES = 15
PUBLIC_DIRECTION_MIN_SPEED_MS = 1.5
UNCERTAINTY_INTERVAL_Z = 1.645  # central 90% interval


def _manifest_hash(value: dict | None) -> str | None:
    if not isinstance(value, dict):
        return None
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _finite(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _utc(value) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _canonical_model_id(model_id: str) -> str:
    aliases = {
        "gfs-0p25": "ncep_gfs_global",
        "icon-d2": "icon_d2",
        "icon-eu": "icon_eu",
        "icon-global": "icon_global",
    }
    return aliases.get(model_id, model_id)


def _component_score(candidate, name: str, default: float = 0.5) -> float:
    component = candidate.component_weights.get(name) or {}
    value = _finite(component.get("score"))
    return default if value is None else max(0.0, min(1.0, value))


def _residual_model_ids(row) -> set[str]:
    members = row.model_members if isinstance(row.model_members, list) else []
    runs = row.model_runs if isinstance(row.model_runs, list) else []
    return {
        _canonical_model_id(str(item["model_id"]))
        for item in [*members, *runs]
        if isinstance(item, dict) and item.get("model_id")
    }


def _residual_uncertainty(row) -> float:
    uncertainty = (
        1.0
        if row.representativeness_uncertainty == "reviewed_station_profile"
        else 1.8
    )
    if row.qc_status == "degraded":
        uncertainty *= 1.25
    if row.model_member_count <= 1:
        uncertainty *= 1.20
    return uncertainty


def live_wind_context_id(spot, baseline: dict, *, gate_configuration: dict | None = None) -> str:
    """Stable cache identity for model, analysis, physics/profile and gate versions."""
    raw_profile = getattr(spot, "weather_profile", None)
    sectors = []
    for sector in getattr(raw_profile, "sectors", None) or ():
        sectors.append(
            {
                "start": getattr(sector, "start_deg", None),
                "end": getattr(sector, "end_deg", None),
                "factor": getattr(sector, "speed_factor", None),
                "offset": getattr(sector, "direction_offset_deg", None),
                "version": getattr(sector, "version", None),
                "enabled": bool(getattr(sector, "enabled", False)),
            }
        )
    model_source = next(
        (
            source
            for source in baseline.get("sources", ())
            if isinstance(source, dict) and source.get("source_type") == "model_nowcast"
        ),
        {},
    )
    identity = {
        "analysis_version": REGIONAL_LIVE_WIND_VERSION,
        "model_version": baseline.get("model_version"),
        "model_valid_at": baseline.get("valid_at"),
        "model_captured_at": model_source.get("captured_at"),
        "model_u_ms": baseline.get("model_baseline_u_ms"),
        "model_v_ms": baseline.get("model_baseline_v_ms"),
        "model_spread_ms": baseline.get("model_spread_ms"),
        "model_ids": sorted(baseline.get("_model_ids") or ()),
        "physics_version": getattr(raw_profile, "physics_version", None),
        "profile_reviewed_at": getattr(raw_profile, "reviewed_at", None),
        "profile_active": bool(getattr(raw_profile, "active", False)),
        "sectors": sorted(sectors, key=lambda item: json.dumps(item, sort_keys=True, default=str)),
        "gate_configuration": gate_configuration or {},
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def _serialize_residual_input(item: StationResidualInput) -> dict:
    payload = asdict(item)
    payload["observed_at"] = item.observed_at.astimezone(timezone.utc).isoformat()
    return payload


def _deserialize_residual_input(payload: dict) -> StationResidualInput | None:
    try:
        observed_at = _utc(payload.get("observed_at"))
        if observed_at is None:
            return None
        return StationResidualInput(
            **{
                **payload,
                "observed_at": observed_at,
            }
        )
    except (TypeError, ValueError):
        return None


def load_station_residual_inputs(
    db,
    selection,
    *,
    target_model_ids: tuple[str, ...],
    target_dataset_bundle_hash: str | None = None,
    target_dataset_manifest: dict | None = None,
    as_of: datetime | None = None,
    diagnostics_out: dict | None = None,
) -> tuple[StationResidualInput, ...]:
    """Load one newest quality-checked residual for each selected observation."""
    eligible = [
        candidate
        for candidate in selection.candidates
        if candidate.eligible and candidate.observation_id
    ]
    observation_ids = []
    for candidate in eligible:
        try:
            observation_ids.append(uuid.UUID(candidate.observation_id))
        except (TypeError, ValueError):
            continue
    if not observation_ids:
        return ()
    conditions = [
        WeatherStationModelResidual.observation_id.in_(observation_ids),
        WeatherStationModelResidual.qc_status.in_(("accepted", "degraded")),
    ]
    if as_of is not None:
        cutoff = _utc(as_of)
        if cutoff is None:
            raise ValueError("as_of must be timezone-aware")
        conditions.extend((
            WeatherStationModelResidual.created_at <= cutoff,
            WeatherStationModelResidual.analyzed_at <= cutoff,
            WeatherStationModelResidual.observed_at <= cutoff,
        ))
    rows = db.scalars(
        select(WeatherStationModelResidual)
        .where(*conditions)
        .order_by(
            WeatherStationModelResidual.observation_id,
            WeatherStationModelResidual.analyzed_at.desc(),
            WeatherStationModelResidual.analysis_id,
        )
    ).all()
    from app.weather.exact_run import compatible_dataset_manifests

    newest = {}
    rejection_reasons: dict[str, int] = {}

    def reject(reason: str) -> None:
        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

    for row in rows:
        if target_dataset_bundle_hash is not None:
            if row.baseline_version != "exact-run-bundle-v2":
                reject("legacy_or_nonexact_baseline")
                continue
            if not row.activation_eligible:
                reject("not_activation_eligible")
                continue
            if row.dataset_bundle_hash != target_dataset_bundle_hash:
                reject("dataset_bundle_hash_mismatch")
                continue
            if not compatible_dataset_manifests(row.dataset_manifest, target_dataset_manifest):
                reject("dataset_manifest_incompatible")
                continue
            # Both manifests must independently prove their claimed identity.
            if (_manifest_hash(row.dataset_manifest) != row.dataset_bundle_hash
                    or _manifest_hash(target_dataset_manifest) != target_dataset_bundle_hash):
                reject("dataset_manifest_hash_mismatch")
                continue
            if (not isinstance(row.sample_manifest, dict)
                    or not row.sample_hash
                    or _manifest_hash(row.sample_manifest) != row.sample_hash
                    or row.sample_manifest.get("dataset_bundle_hash") != target_dataset_bundle_hash):
                reject("sample_hash_mismatch")
                continue
        elif row.baseline_version != RAW_MODEL_BASELINE_VERSION:
            # Old exact-run rows are legacy evidence, never public fallback input.
            reject("product_mismatch")
            continue
        newest.setdefault(str(row.observation_id), row)
    if diagnostics_out is not None:
        diagnostics_out["residual_rejection_reasons"] = rejection_reasons
        diagnostics_out["compatible_residual_count"] = len(newest)

    target_ids = {_canonical_model_id(model_id) for model_id in target_model_ids}
    inputs = []
    for candidate in eligible:
        row = newest.get(candidate.observation_id)
        if row is None:
            continue
        vector = row.residual_vector if isinstance(row.residual_vector, dict) else {}
        u_ms = _finite(vector.get("u_ms"))
        v_ms = _finite(vector.get("v_ms"))
        if u_ms is None or v_ms is None:
            continue
        surface_similarity = _component_score(candidate, "surface_context")
        mountain_similarity = _component_score(candidate, "mountain_side")
        inputs.append(
            StationResidualInput(
                residual_id=str(row.id),
                analysis_id=row.analysis_id,
                station_id=candidate.station_id or candidate.station_identity,
                observation_id=candidate.observation_id,
                provider=candidate.provider,
                observed_at=row.observed_at,
                residual_u_ms=u_ms,
                residual_v_ms=v_ms,
                selection_weight=candidate.total_weight,
                residual_uncertainty_ms=_residual_uncertainty(row),
                qc_status=row.qc_status,
                correlation_group=candidate.correlation_group,
                terrain_similarity=_component_score(candidate, "terrain_similarity"),
                coastal_similarity=surface_similarity,
                elevation_similarity=_component_score(
                    candidate, "elevation_difference"
                ),
                air_mass_similarity=min(surface_similarity, mountain_similarity),
                station_air_mass_id=candidate.air_mass_id,
                mountain_barrier=mountain_similarity < 0.25,
                distance_km=candidate.distance_km,
                model_compatible=(
                    row.baseline_version == (
                        "exact-run-bundle-v2" if target_dataset_bundle_hash is not None
                        else RAW_MODEL_BASELINE_VERSION
                    )
                    and row.calculation_version == MODEL_ERROR_CALCULATION_VERSION
                    and (
                        target_ids == _residual_model_ids(row)
                        if target_dataset_bundle_hash is not None
                        else bool(target_ids & _residual_model_ids(row))
                    )
                ),
            )
        )
    return tuple(inputs)


def _source_model(
    *,
    model_version: str,
    valid_at: datetime,
    captured_at: datetime,
) -> dict:
    return {
        "source_type": "model_nowcast",
        "source": "current_model_baseline",
        "provider": "Surfwinddata · Open-Meteo",
        "model_version": model_version,
        "valid_at": valid_at,
        "captured_at": captured_at,
    }


def compose_live_wind(
    target: TargetModelState,
    regional,
    *,
    profile=None,
    physics_version: str | None = None,
    captured_at: datetime,
    model_source: dict | None = None,
) -> dict:
    """Apply local spot physics after regional analysis and serialize the product."""
    if regional.status == "unavailable":
        from app.live.weather_contract import unavailable_live_wind

        return unavailable_live_wind(
            regional.fallback_reason or "model_baseline_unavailable"
        )
    regional_speed, regional_direction = uv_to_wind(
        regional.regional_u_ms, regional.regional_v_ms
    )
    if regional_direction is None:
        final_speed = regional_speed
        final_direction = None
        final_u, final_v = regional.regional_u_ms, regional.regional_v_ms
        physics_applied = False
        physics_component = None
    else:
        applied = apply_local_physics(
            regional_speed,
            regional_direction,
            profile,
            blend=1.0,
        )
        final_speed = applied.speed_ms
        final_direction = applied.direction_deg
        final_u, final_v = wind_to_uv(final_speed, final_direction)
        physics_applied = applied.corrected
        physics_component = applied.applied_component

    covariance_uu = regional.covariance_uu_ms2
    covariance_uv = regional.covariance_uv_ms2
    covariance_vv = regional.covariance_vv_ms2
    uncertainty_components = dict(regional.uncertainty_components)
    local_physics_uncertainty = 0.0
    if None not in (covariance_uu, covariance_uv, covariance_vv):
        regional_magnitude = math.hypot(regional.regional_u_ms, regional.regional_v_ms)
        scale = final_speed / regional_magnitude if regional_magnitude > 1e-9 else 1.0
        covariance_uu *= scale * scale
        covariance_uv *= scale * scale
        covariance_vv *= scale * scale
        if physics_applied:
            local_physics_uncertainty = abs(final_speed - regional_magnitude) * 0.20
        elif profile is not None and (
            not isinstance(physics_component, dict)
            or physics_component.get("status") == "unavailable"
        ):
            local_physics_uncertainty = 0.8
        if local_physics_uncertainty > 0:
            physics_variance = local_physics_uncertainty**2 / 2.0
            covariance_uu += physics_variance
            covariance_vv += physics_variance
    uncertainty_components["local_physics"] = local_physics_uncertainty
    uncertainty = (
        math.sqrt(max(0.0, covariance_uu + covariance_vv))
        if None not in (covariance_uu, covariance_vv)
        else regional.uncertainty_ms
    )
    speed_band, direction_uncertainty = _public_uncertainty(
        final_u,
        final_v,
        covariance_uu,
        covariance_uv,
        covariance_vv,
    )

    contributions = [item.payload() for item in regional.station_contributions]
    included = [item for item in regional.station_contributions if item.included]
    oldest_source_at = min((item.observed_at for item in included), default=captured_at)
    max_station_age_seconds = (
        max(
            0,
            int((regional.analyzed_at - oldest_source_at).total_seconds()),
        )
        if included
        else None
    )
    sources = [
        model_source or _source_model(
            model_version=target.model_version,
            valid_at=target.valid_at,
            captured_at=captured_at,
        ),
        *[
            {
                "source_type": "station_residual",
                "source": f"station_residual:{item.analysis_id}",
                "provider": item.provider,
                "model_version": regional.analysis_version,
                "observed_at": item.observed_at,
                "valid_at": target.valid_at,
                "captured_at": regional.analyzed_at,
            }
            for item in included
        ],
    ]
    if physics_applied:
        sources.append(
            {
                "source_type": "local_physics",
                "source": "reviewed_spot_physics",
                "model_version": physics_version or "unknown",
                "valid_at": target.valid_at,
                "captured_at": regional.analyzed_at,
            }
        )
    return {
        "contract_version": "live-wind-v1",
        "product_type": "live_wind",
        "status": regional.status,
        "fallback_level": (
            "station_adjusted"
            if regional.status == "station_adjusted"
            else "model_with_local_physics"
            if profile is not None
            and isinstance(physics_component, dict)
            and physics_component.get("status") != "unavailable"
            else "raw_model"
        ),
        "analyzed_at": regional.analyzed_at,
        "valid_at": target.valid_at,
        "expires_at": regional.analyzed_at + timedelta(minutes=LIVE_WIND_ANALYSIS_TTL_MINUTES),
        "oldest_source_at": oldest_source_at,
        "max_station_age_seconds": max_station_age_seconds,
        "wind_speed_ms": round(final_speed, 9),
        "wind_direction_from_deg": (
            None if final_direction is None else round(final_direction, 9)
        ),
        "wind_u_ms": round(final_u, 9),
        "wind_v_ms": round(final_v, 9),
        "gust": None,
        "model_version": target.model_version,
        "analysis_version": regional.analysis_version,
        "station_count": len(included),
        "uncertainty_ms": uncertainty,
        "speed_uncertainty_band_ms": speed_band,
        "direction_uncertainty_deg": direction_uncertainty,
        "uncertainty_components": uncertainty_components,
        "confidence": regional.confidence,
        "sources": sources,
        "applied_physics_version": (
            physics_version if physics_applied and physics_version else "none"
        ),
        "fallback_reason": regional.fallback_reason,
        "model_baseline_u_ms": target.u_ms,
        "model_baseline_v_ms": target.v_ms,
        "regional_wind_u_ms": regional.regional_u_ms,
        "regional_wind_v_ms": regional.regional_v_ms,
        "correction_u_ms": regional.correction_u_ms,
        "correction_v_ms": regional.correction_v_ms,
        "model_spread_ms": target.model_spread_ms,
        "conflict_index": regional.conflict_index,
        "covariance": {
            "uu_ms2": covariance_uu,
            "uv_ms2": covariance_uv,
            "vv_ms2": covariance_vv,
        },
        "evidence_strength": regional.evidence_strength,
        "effective_station_count": regional.effective_station_count,
        "station_contributions": contributions,
        "analysis_configuration": regional.configuration,
        "local_physics_component": physics_component,
    }


def _public_uncertainty(
    u_ms: float,
    v_ms: float,
    covariance_uu: float | None,
    covariance_uv: float | None,
    covariance_vv: float | None,
) -> tuple[dict | None, float | None]:
    """Project the internal u/v covariance onto speed and direction."""
    if None in (covariance_uu, covariance_uv, covariance_vv):
        return None, None
    speed = math.hypot(u_ms, v_ms)
    if speed <= 1e-9:
        radial_variance = max(covariance_uu, covariance_vv)
        tangential_variance = radial_variance
    else:
        along_u, along_v = u_ms / speed, v_ms / speed
        cross_u, cross_v = -along_v, along_u
        radial_variance = (
            along_u * along_u * covariance_uu
            + 2.0 * along_u * along_v * covariance_uv
            + along_v * along_v * covariance_vv
        )
        tangential_variance = (
            cross_u * cross_u * covariance_uu
            + 2.0 * cross_u * cross_v * covariance_uv
            + cross_v * cross_v * covariance_vv
        )
    speed_radius = UNCERTAINTY_INTERVAL_Z * math.sqrt(max(0.0, radial_variance))
    band = {
        "low_ms": max(0.0, speed - speed_radius),
        "high_ms": speed + speed_radius,
        "confidence_level": 0.90,
    }
    if speed < PUBLIC_DIRECTION_MIN_SPEED_MS:
        return band, None
    direction_radius = math.degrees(
        math.atan2(
            UNCERTAINTY_INTERVAL_Z * math.sqrt(max(0.0, tangential_variance)),
            speed,
        )
    )
    return band, min(180.0, direction_radius)


def build_live_wind_baseline(
    spot,
    raw_consensus,
    *,
    model_ids: list[str] | tuple[str, ...],
    valid_at: datetime | None,
    captured_at: datetime,
) -> dict:
    """Create an honest model-only LiveWind product when station evidence is absent."""
    if raw_consensus is None or valid_at is None:
        from app.live.weather_contract import unavailable_live_wind

        return unavailable_live_wind("model_baseline_unavailable")
    if raw_consensus.direction_deg is None:
        if not math.isclose(raw_consensus.speed_ms, 0.0, abs_tol=1e-12):
            from app.live.weather_contract import unavailable_live_wind

            return unavailable_live_wind("model_baseline_vector_invalid")
        u_ms = v_ms = 0.0
    else:
        u_ms, v_ms = wind_to_uv(raw_consensus.speed_ms, raw_consensus.direction_deg)
    model_version = "open-meteo-current:" + ",".join(sorted(model_ids))
    raw_profile = getattr(spot, "weather_profile", None)
    resolved_profile = resolve_weather_profile(raw_profile)
    target = TargetModelState(
        u_ms=u_ms,
        v_ms=v_ms,
        valid_at=valid_at,
        model_version=model_version,
        model_ids=tuple(model_ids),
        model_spread_ms=max(0.0, raw_consensus.high_ms - raw_consensus.low_ms),
        terrain_complexity=float(getattr(resolved_profile, "terrain_complexity", 0.0)),
        profile_available=resolved_profile is not None,
    )
    regional = analyze_regional_live_wind(target, (), analyzed_at=captured_at)
    return compose_live_wind(
        target,
        regional,
        profile=resolved_profile,
        physics_version=getattr(raw_profile, "physics_version", None),
        captured_at=captured_at,
    )


def analyze_live_wind_for_spot(
    db,
    spot,
    baseline: dict | None,
    *,
    model_ids: list[str] | tuple[str, ...] = (),
    analyzed_at: datetime | None = None,
    diagnostics_out: dict | None = None,
    cache=None,
    residual_context_id: str | None = None,
    input_generation: str | None = None,
) -> dict:
    """Re-run a cached model baseline with current, quality-checked residuals."""
    if not isinstance(baseline, dict) or baseline.get("status") != "baseline":
        from app.live.weather_contract import unavailable_live_wind

        return unavailable_live_wind("model_baseline_unavailable")
    if baseline.get("_exact_bundle_hash") and (
        not baseline.get("_exact_dataset_bundle_hash")
        or not isinstance(baseline.get("_exact_dataset_manifest"), dict)
    ):
        if diagnostics_out is not None:
            diagnostics_out["residual_rejection_reasons"] = {
                "exact_dataset_identity_unavailable": 1,
            }
        return {**baseline, "fallback_reason": "exact_dataset_identity_unavailable"}
    if not hasattr(db, "scalar") or not hasattr(db, "scalars"):
        return baseline
    private_model_ids = tuple(model_ids or baseline.get("_model_ids") or ())
    valid_at = _utc(baseline.get("valid_at"))
    model_u = _finite(baseline.get("model_baseline_u_ms"))
    model_v = _finite(baseline.get("model_baseline_v_ms"))
    spread = _finite(baseline.get("model_spread_ms"))
    model_version = baseline.get("model_version")
    if any(value is None for value in (valid_at, model_u, model_v, spread)) or not model_version:
        from app.live.weather_contract import unavailable_live_wind

        return unavailable_live_wind("model_baseline_unavailable")

    analysis_time = (analyzed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    residuals = None
    target_air_mass_id = None
    if cache is not None and residual_context_id:
        from app.live.public_cache import get_public_live_wind_residuals

        cached_residuals = get_public_live_wind_residuals(
            cache,
            spot.id,
            residual_context_id,
            input_generation=input_generation,
        )
        if cached_residuals is not None:
            restored = tuple(
                item
                for item in (
                    _deserialize_residual_input(payload)
                    for payload in cached_residuals.get("residuals", ())
                    if isinstance(payload, dict)
                )
                if item is not None
            )
            residuals = restored
            target_air_mass_id = cached_residuals.get("target_air_mass_id")
            if diagnostics_out is not None:
                diagnostics_out["station_residual_cache_hit"] = True

    if residuals is None:
        _, direction = uv_to_wind(model_u, model_v)
        selection = select_stations_for_spot(
            db,
            spot.id,
            now=analysis_time,
            wind_direction_deg=direction,
        )
        target_air_mass_id = selection.target_context.get("air_mass_id")
        if diagnostics_out is not None:
            diagnostics_out["station_residual_cache_hit"] = False
            diagnostics_out["station_selection"] = selection.payload()
        residuals = load_station_residual_inputs(
            db,
            selection,
            target_model_ids=private_model_ids,
            target_dataset_bundle_hash=baseline.get("_exact_dataset_bundle_hash"),
            target_dataset_manifest=baseline.get("_exact_dataset_manifest"),
            diagnostics_out=diagnostics_out,
        )
        if cache is not None and residual_context_id:
            from app.live.public_cache import set_public_live_wind_residuals

            set_public_live_wind_residuals(
                cache,
                spot.id,
                residual_context_id,
                {
                    "target_air_mass_id": target_air_mass_id,
                    "residuals": [
                        _serialize_residual_input(item) for item in residuals
                    ],
                },
                input_generation=input_generation,
            )
    raw_profile = getattr(spot, "weather_profile", None)
    resolved_profile = resolve_weather_profile(raw_profile)
    target = TargetModelState(
        u_ms=model_u,
        v_ms=model_v,
        valid_at=valid_at,
        model_version=str(model_version),
        model_ids=private_model_ids,
        model_spread_ms=spread,
        air_mass_id=target_air_mass_id,
        terrain_complexity=float(getattr(resolved_profile, "terrain_complexity", 0.0)),
        profile_available=resolved_profile is not None,
    )
    regional = analyze_regional_live_wind(
        target,
        residuals,
        analyzed_at=analysis_time,
    )
    captured_at = analysis_time
    for source in baseline.get("sources", []):
        if isinstance(source, dict) and source.get("source_type") == "model_nowcast":
            captured_at = _utc(source.get("captured_at")) or captured_at
            break
    return compose_live_wind(
        target,
        regional,
        profile=resolved_profile,
        physics_version=getattr(raw_profile, "physics_version", None),
        captured_at=captured_at,
        model_source=baseline.get("_exact_model_source"),
    )
