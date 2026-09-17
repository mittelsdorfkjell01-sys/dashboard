"""Insert-only, as-of reconstructed LiveWind shadow holdouts.

The target observation vector is fetched only after a prediction has been
computed from a separately queried model state and foreign residuals. Nothing
in this module writes a public weather product or activates a candidate.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert

from app.live.live_wind import load_station_residual_inputs
from app.models import (
    Region, Spot, WeatherLiveWindHoldoutCase, WeatherLiveWindJob,
    WeatherObservation, WeatherStation, WeatherStationModelResidual,
)
from app.weather.catalog import family_for
from app.weather.exact_run import (
    EXACT_BUNDLE_VERSION, EXPECTED_MODELS, ExactRunLoader,
    compatible_dataset_manifests,
)
from app.weather.live_wind_analysis import (
    REGIONAL_LIVE_WIND_VERSION, StationResidualInput, TargetModelState,
    analyze_regional_live_wind,
)
from app.weather.live_wind_verification import (
    HoldoutPrediction, LiveWindHoldoutCase, LiveWindVerificationPolicy,
    evaluate_live_wind_holdouts, persist_live_wind_verification_evidence,
)
from app.weather.model_error import (
    DEFAULT_MODEL_ERROR_POLICY, _interpolate_member, load_reviewed_station_physics,
)
from app.weather.physics.engine import apply_local_physics
from app.weather.providers.common import haversine_km
from app.weather.station_identity import duplicate_station_groups
from app.weather.station_selection import (
    DEFAULT_STATION_SELECTION_POLICY, SpotSelectionContext, StationCandidate,
    evaluate_station_candidates,
)
from app.weather.vectors import uv_to_wind, wind_to_uv
from app.weather.weights import normalized_model_weights

HOLDOUT_BUILDER_VERSION = "live-wind-holdout-builder-v1"
MAX_CASE_AGE_DAYS = 180


def _utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _engine_hash() -> str:
    return hashlib.sha256(Path(__file__).with_name("live_wind_analysis.py").read_bytes()).hexdigest()


def _season(at: datetime) -> str:
    return ("winter", "spring", "summer", "autumn")[(at.month % 12) // 3]


def _sector(u_ms: float, v_ms: float) -> str:
    _, direction = uv_to_wind(u_ms, v_ms)
    if direction is None:
        return "variable"
    return ("N", "NE", "E", "SE", "S", "SW", "W", "NW")[int((direction + 22.5) // 45) % 8]


def _training_reasons(proof: dict | None, candidate_version: str, at: datetime) -> list[str]:
    """A reviewed, complete training inventory is required; a date alone is not proof."""
    if not isinstance(proof, dict) or proof.get("candidate_version") != candidate_version:
        return ["training_boundary_unproven"]
    end = _utc(_parse_time(proof.get("training_window_end")))
    frozen = _utc(_parse_time(proof.get("frozen_at")))
    blocks = proof.get("training_weather_blocks")
    sources = proof.get("training_sources")
    if (end is None or frozen is None or frozen < end or frozen > at
            or proof.get("lineage_complete") is not True
            or proof.get("reviewed") is not True
            or not isinstance(blocks, list)
            or not isinstance(sources, list) or not sources
            or _hash(sources) != proof.get("training_source_hash")):
        return ["training_boundary_unproven"]
    declared_blocks = set()
    for source in sources:
        if (not isinstance(source, dict) or not source.get("source_id")
                or not isinstance(source.get("content_hash"), str)
                or len(source["content_hash"]) != 64
                or any(c not in "0123456789abcdef" for c in source["content_hash"].lower())
                or _utc(_parse_time(source.get("last_observed_at"))) is None
                or _utc(_parse_time(source["last_observed_at"])) > end
                or not isinstance(source.get("weather_blocks"), list)):
            return ["training_boundary_unproven"]
        declared_blocks.update(str(item) for item in source["weather_blocks"])
    if declared_blocks != {str(item) for item in blocks}:
        return ["training_boundary_unproven"]
    # This work package can independently verify only the untrained regional
    # engine source. Trained profiles need their own immutable lineage inventory.
    if (len(sources) != 1 or sources[0]["source_id"] != "regional-live-wind-engine"
            or sources[0]["content_hash"] != _engine_hash() or blocks):
        return ["training_boundary_unproven"]
    if at <= end + timedelta(hours=24):
        return ["training_embargo"]
    block = int(at.timestamp()) // 86400
    if str(block) in {str(item) for item in blocks}:
        return ["training_weather_block_overlap"]
    try:
        if any(int(item) * 86400 > end.timestamp() for item in blocks):
            return ["training_boundary_unproven"]
    except (TypeError, ValueError):
        return ["training_boundary_unproven"]
    return []


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return None


def _station_metadata_reasons(station: WeatherStation, cutoff: datetime) -> tuple[str, ...]:
    """Current mutable station metadata is unsafe for a historical replay."""
    created = _utc(getattr(station, "created_at", None))
    updated = _utc(getattr(station, "updated_at", None))
    if created is None or updated is None:
        return ("station_metadata_time_unproven",)
    if created > cutoff or updated > cutoff:
        return ("station_metadata_after_cutoff",)
    return ()


def audit_holdout_inputs(
    *, target_station: WeatherStation, residual_rows: list[tuple[WeatherStation, WeatherObservation, WeatherStationModelResidual]],
    cutoff: datetime, target_dataset_hash: str, target_manifest: dict,
    quality_reasons_by_observation: dict[str, tuple[str, ...]] | None = None,
) -> tuple[tuple[tuple[WeatherStation, WeatherObservation, WeatherStationModelResidual], ...], tuple[dict, ...]]:
    """Filter temporal and physical dependence before exposing inputs to engine."""
    stations = [target_station, *(row[0] for row in residual_rows)]
    duplicates = {str(target_station.id)}
    for group in duplicate_station_groups(stations):
        if 0 in group:
            duplicates.update(str(stations[index].id) for index in group)
    explicit = {str(value) for value in (target_station.provenance or {}).get("dependent_station_ids", [])}
    target_group = (target_station.provenance or {}).get("correlation_group")
    accepted, excluded = [], []
    for station, observation, residual in sorted(
        residual_rows, key=lambda row: (str(row[0].id), str(row[1].id), str(row[2].id))
    ):
        reasons = []
        reasons.extend((quality_reasons_by_observation or {}).get(str(observation.id), ()))
        reasons.extend(_station_metadata_reasons(station, cutoff))
        station_id = str(station.id)
        if station_id == str(target_station.id):
            reasons.append("target_station")
        if station_id in duplicates and station_id != str(target_station.id):
            reasons.append("target_api_duplicate")
        if (station_id in explicit or str(target_station.id) in {
            str(value) for value in (station.provenance or {}).get("dependent_station_ids", [])
        }):
            reasons.append("dependent_station")
        if target_group and target_group == (station.provenance or {}).get("correlation_group"):
            reasons.append("target_correlation_group")
        try:
            if haversine_km(
                target_station.latitude, target_station.longitude,
                station.latitude, station.longitude,
            ) <= DEFAULT_STATION_SELECTION_POLICY.correlation_radius_km:
                reasons.append("target_correlation_group")
        except (TypeError, ValueError):
            reasons.append("station_coordinates_invalid")
        observed = _utc(observation.observed_at)
        received = _utc(observation.received_at)
        imported = _utc(observation.imported_at)
        if received is None:
            reasons.append("station_received_at_unproven")
        if imported is None:
            reasons.append("station_imported_at_unproven")
        if any(value is not None and value > cutoff for value in (observed, received, imported)):
            reasons.append("station_available_after_cutoff")
        if _utc(residual.analyzed_at) is None or residual.analyzed_at > cutoff or residual.created_at > cutoff:
            reasons.append("residual_available_after_cutoff")
        if residual.qc_status not in {"accepted", "degraded"} or not residual.activation_eligible:
            reasons.append("residual_not_activation_eligible")
        if getattr(residual, "station_profile_id", None) is not None:
            reasons.append("station_profile_training_unproven")
        if residual.baseline_version != EXACT_BUNDLE_VERSION:
            reasons.append("legacy_capture_time_baseline")
        if residual.dataset_bundle_hash != target_dataset_hash:
            reasons.append("dataset_bundle_hash_mismatch")
        if not compatible_dataset_manifests(residual.dataset_manifest, target_manifest):
            reasons.append("dataset_manifest_incompatible")
        if _hash(residual.dataset_manifest) != residual.dataset_bundle_hash:
            reasons.append("dataset_manifest_hash_mismatch")
        if (not isinstance(residual.sample_manifest, dict) or
                _hash(residual.sample_manifest) != residual.sample_hash):
            reasons.append("sample_hash_mismatch")
        source_ids = {
            str(value)
            for member in (residual.model_members or []) if isinstance(member, dict)
            for value in member.get("source_observation_ids", [])
        }
        if source_ids:
            reasons.append("observation_derived_model_input")
        # Persisted member summaries do not carry source_product; the sealed
        # exact bundle/sample provenance above is their raw-model proof.
        if (not isinstance(residual.model_members, list) or not residual.model_members
                or any(not isinstance(member, dict)
                       or member.get("source_product") not in (None, "raw_model")
                       for member in residual.model_members)):
            reasons.append("adjusted_model_input_forbidden")
        if reasons:
            excluded.append({"station_id": station_id, "observation_id": str(observation.id),
                             "residual_id": str(residual.id), "reasons": sorted(set(reasons))})
        else:
            accepted.append((station, observation, residual))
    return tuple(accepted), tuple(excluded)


def _station_history_reasons(db, station: WeatherStation, observation: WeatherObservation,
                             cutoff: datetime) -> tuple[str, ...]:
    reasons = []
    if (station.elevation_m is None or station.measurement_height_m is None
            or not 0 < station.measurement_height_m <= 300):
        reasons.append("station_metadata_incomplete")
    provenance = station.provenance or {}
    if not provenance.get("measurement_standard") and provenance.get("wind_uncertainty_ms") is None:
        reasons.append("measurement_standard_unproven")
    rows = db.scalars(
        select(WeatherObservation)
        .where(WeatherObservation.station_id == station.id,
               WeatherObservation.observed_at <= observation.observed_at,
               WeatherObservation.observed_at >= observation.observed_at - timedelta(hours=3),
               WeatherObservation.received_at <= cutoff,
               WeatherObservation.imported_at <= cutoff,
               WeatherObservation.import_status == "accepted")
        .order_by(WeatherObservation.observed_at.desc(), WeatherObservation.id)
        .limit(8)
    ).all()
    if len(rows) < 3 or (rows[0].observed_at - rows[-1].observed_at) < timedelta(minutes=20):
        reasons.append("station_history_unproven")
    else:
        valid = all(row.wind_u_ms is not None and row.wind_v_ms is not None for row in rows)
        if not valid:
            reasons.append("station_history_vector_missing")
        elif (rows[0].observed_at - rows[-1].observed_at >= timedelta(minutes=30)
              and all(math.hypot(row.wind_u_ms - rows[0].wind_u_ms,
                                 row.wind_v_ms - rows[0].wind_v_ms) < 0.05 for row in rows)):
            reasons.append("station_wind_stuck")
        if (len(rows) >= 2 and rows[0].observed_at - rows[1].observed_at <= timedelta(minutes=10)
                and valid and math.hypot(rows[0].wind_u_ms - rows[1].wind_u_ms,
                                         rows[0].wind_v_ms - rows[1].wind_v_ms) > 30):
            reasons.append("station_wind_jump")
    return tuple(reasons)


def exclude_target_dependence(stations: list[WeatherStation], target: WeatherStation) -> tuple[list, list[dict]]:
    """Remove hidden station and aliases before selection can affect weights."""
    candidates = [target, *(item for item in stations if str(item.id) != str(target.id))]
    duplicates = {str(target.id)}
    for group in duplicate_station_groups(candidates):
        if 0 in group:
            duplicates.update(str(candidates[index].id) for index in group)
    dependencies = {str(value) for value in (target.provenance or {}).get("dependent_station_ids", [])}
    target_group = (target.provenance or {}).get("correlation_group")
    accepted, excluded = [], []
    for item in stations:
        reasons = []
        identity = str(item.id)
        if identity == str(target.id):
            reasons.append("target_station")
        if identity in duplicates and identity != str(target.id):
            reasons.append("target_api_duplicate")
        if (identity in dependencies or str(target.id) in {
            str(value) for value in (item.provenance or {}).get("dependent_station_ids", [])
        }):
            reasons.append("dependent_station")
        if target_group and target_group == (item.provenance or {}).get("correlation_group"):
            reasons.append("target_correlation_group")
        try:
            if haversine_km(target.latitude, target.longitude,
                            item.latitude, item.longitude) <= DEFAULT_STATION_SELECTION_POLICY.correlation_radius_km:
                reasons.append("target_correlation_group")
        except (TypeError, ValueError):
            reasons.append("station_coordinates_invalid")
        if reasons:
            excluded.append({"station_id": identity, "reasons": sorted(set(reasons))})
        else:
            accepted.append(item)
    return accepted, excluded


def _physical_station_group(stations: list[WeatherStation], target: WeatherStation) -> str:
    indexed = [target, *(item for item in stations if str(item.id) != str(target.id))]
    for group in duplicate_station_groups(indexed):
        if 0 in group:
            return "physical:" + _hash(sorted(str(indexed[item].id) for item in group))[:20]
    return f"station:{target.id}"


def _target_model(loader: ExactRunLoader, station: WeatherStation, at: datetime, cutoff: datetime):
    # The model state must have existed before the measurement, not merely
    # before the later reconstruction cutoff.
    bundle = loader.bundle(valid_at=at, latitude=station.latitude, longitude=station.longitude, as_of=at)
    sampled = loader.sample(bundle, latitude=station.latitude, longitude=station.longitude)
    if not sampled.activation_eligible or not compatible_dataset_manifests(bundle.dataset_manifest, bundle.dataset_manifest):
        return None, bundle, "model_availability_unproven", {}, {}
    members = {}
    for model in EXPECTED_MODELS:
        member, reason = _interpolate_member(
            [point for point in sampled.points if point.model_id == model],
            at, policy=DEFAULT_MODEL_ERROR_POLICY,
        )
        if member is None:
            return None, bundle, reason or "model_member_missing", {}, {}
        members[model] = member
    lead = max((at - member.model_run_at).total_seconds() / 3600 for member in members.values())
    weights = normalized_model_weights(((model, family_for(model)) for model in members), lead)
    u_ms = sum(member.u_ms * weights[model] for model, member in members.items())
    v_ms = sum(member.v_ms * weights[model] for model, member in members.items())
    spread = math.sqrt(sum(weights[model] * ((member.u_ms-u_ms)**2 + (member.v_ms-v_ms)**2)
                           for model, member in members.items()))
    return TargetModelState(
        u_ms=u_ms, v_ms=v_ms, valid_at=at,
        model_version=f"exact-run:{bundle.dataset_bundle_hash[:16]}",
        model_ids=tuple(members), model_spread_ms=spread,
        profile_available=False,
    ), bundle, None, members, weights


def _physics_prediction(members: dict, weights: dict, profile, *, correction_u=0.0,
                        correction_v=0.0) -> HoldoutPrediction:
    u_total = v_total = 0.0
    for model, member in members.items():
        u_ms, v_ms = member.u_ms + correction_u, member.v_ms + correction_v
        speed, direction = uv_to_wind(u_ms, v_ms)
        if direction is not None:
            applied = apply_local_physics(speed, direction, profile.profile)
            u_ms, v_ms = wind_to_uv(applied.speed_ms, applied.direction_deg)
        u_total += weights[model] * u_ms
        v_total += weights[model] * v_ms
    return HoldoutPrediction(u_total, v_total)


def _case_for_observation(db, loader, station, observation_meta, job, *, candidate_version, training_proof):
    observation_id, observed_at, received_at, imported_at = observation_meta
    observed_at = _utc(observed_at)
    cutoff = _utc(job.analyzed_at)
    if cutoff is None or observed_at is None or observed_at > cutoff:
        return None, "analysis_cutoff_invalid"
    reasons = _training_reasons(training_proof, candidate_version, observed_at)
    if received_at is None:
        reasons.append("target_received_at_unproven")
    if imported_at is None:
        reasons.append("target_imported_at_unproven")
    if (not station.approved or station.blocked or not station.active
            or station.representativeness_status != "passed"):
        reasons.append("target_station_unapproved")
    reasons.extend(_station_metadata_reasons(station, cutoff))
    if _utc(job.created_at) is None or job.created_at > cutoff:
        reasons.append("shadow_job_available_after_cutoff")
    if station.elevation_m is None or station.measurement_height_m is None:
        reasons.append("target_station_metadata_incomplete")
    target, bundle, model_error, members, weights = _target_model(loader, station, observed_at, cutoff)
    if model_error:
        reasons.append(model_error)
    shadow_manifest = (job.diagnostics or {}).get("exact_run_bundle", {}).get("dataset_manifest")
    if (job.diagnostics or {}).get("activation_eligible") is not True:
        reasons.append("shadow_not_activation_eligible")
    if not compatible_dataset_manifests(bundle.dataset_manifest, shadow_manifest):
        reasons.append("shadow_dataset_mismatch")
    if (job.diagnostics or {}).get("dataset_bundle_hash") != bundle.dataset_bundle_hash:
        reasons.append("shadow_dataset_hash_mismatch")
    if target is None:
        return None, ",".join(sorted(set(reasons)))

    # Query only metadata and as-of accepted inputs. The hidden truth vector is
    # deliberately not selected until after regional prediction is complete.
    all_stations = list(db.scalars(select(WeatherStation).where(WeatherStation.active.is_(True))).all())
    target_station_group = _physical_station_group(all_stations, station)
    stations, preexcluded = exclude_target_dependence(all_stations, station)
    as_of_stations = []
    for peer in stations:
        metadata_reasons = _station_metadata_reasons(peer, cutoff)
        if metadata_reasons:
            preexcluded.append({"station_id": str(peer.id), "reasons": list(metadata_reasons)})
        else:
            as_of_stations.append(peer)
    stations = as_of_stations
    ids = [item.id for item in stations]
    observations = db.scalars(
        select(WeatherObservation)
        .where(
            WeatherObservation.station_id.in_(ids),
            WeatherObservation.observed_at <= cutoff,
            WeatherObservation.received_at <= cutoff,
            WeatherObservation.imported_at <= cutoff,
        )
        .distinct(WeatherObservation.station_id)
        .order_by(WeatherObservation.station_id, WeatherObservation.observed_at.desc(), WeatherObservation.id)
    ).all() if ids else []
    latest = {item.station_id: item for item in observations}
    _, direction = uv_to_wind(target.u_ms, target.v_ms)
    selection = evaluate_station_candidates(
        [StationCandidate(item, latest.get(item.id)) for item in stations],
        SpotSelectionContext(
            latitude=station.latitude, longitude=station.longitude,
            elevation_m=float(station.elevation_m) if station.elevation_m is not None else None,
            measurement_height_m=float(station.measurement_height_m or 10.0),
            wind_direction_deg=direction,
        ), now=cutoff,
    )
    eligible_observations = {candidate.observation_id for candidate in selection.candidates if candidate.eligible}
    raw_rows = db.execute(
        select(WeatherStation, WeatherObservation, WeatherStationModelResidual)
        .join(WeatherObservation, WeatherObservation.station_id == WeatherStation.id)
        .join(WeatherStationModelResidual, WeatherStationModelResidual.observation_id == WeatherObservation.id)
        .where(WeatherObservation.id.in_([uuid.UUID(value) for value in eligible_observations]))
    ).all() if eligible_observations else []
    quality_reasons = {
        str(observation.id): _station_history_reasons(db, peer, observation, cutoff)
        for peer, observation, _ in raw_rows
    }
    accepted, excluded = audit_holdout_inputs(
        target_station=station, residual_rows=list(raw_rows), cutoff=cutoff,
        target_dataset_hash=bundle.dataset_bundle_hash,
        target_manifest=bundle.dataset_manifest,
        quality_reasons_by_observation=quality_reasons,
    )
    accepted_ids = {str(item[2].id) for item in accepted}
    diagnostics = {}
    residuals = tuple(item for item in load_station_residual_inputs(
        db, selection, target_model_ids=target.model_ids,
        target_dataset_bundle_hash=bundle.dataset_bundle_hash,
        target_dataset_manifest=bundle.dataset_manifest,
        as_of=cutoff, diagnostics_out=diagnostics,
    ) if item.residual_id in accepted_ids and item.model_compatible)
    regional = analyze_regional_live_wind(target, residuals, analyzed_at=cutoff)
    # No unreviewed target-station physics is invented. The regional engine is
    # the only available candidate variant in that situation.
    regional_prediction = HoldoutPrediction(
        regional.regional_u_ms, regional.regional_v_ms,
        regional.covariance_uu_ms2, regional.covariance_uv_ms2,
        regional.covariance_vv_ms2,
    ) if regional.regional_u_ms is not None and regional.regional_v_ms is not None else None
    if regional_prediction is None:
        reasons.append("candidate_unavailable")
    profile = load_reviewed_station_physics(db, station.id)
    physics_prediction = None
    prediction = regional_prediction
    if profile is not None:
        reasons.append("target_profile_training_unproven")
        if profile.reviewed_at > cutoff or (
            isinstance(training_proof, dict)
            and _utc(_parse_time(training_proof.get("training_window_end"))) is not None
            and profile.reviewed_at > _utc(_parse_time(training_proof["training_window_end"]))
        ):
            reasons.append("target_profile_after_training_boundary")
        else:
            physics_prediction = _physics_prediction(members, weights, profile)
            prediction = _physics_prediction(
                members, weights, profile,
                correction_u=regional.correction_u_ms,
                correction_v=regional.correction_v_ms,
            )

    # Open target truth only after all model and foreign-station predictions.
    truth = db.execute(select(WeatherObservation.wind_u_ms, WeatherObservation.wind_v_ms,
                              WeatherObservation.wind_speed_ms, WeatherObservation.import_status)
                       .where(WeatherObservation.id == observation_id)).one()
    if truth.import_status != "accepted" or any(value is None or not math.isfinite(value)
                                                     for value in (truth.wind_u_ms, truth.wind_v_ms)):
        reasons.append("target_truth_invalid")
    target_observation = db.get(WeatherObservation, observation_id)
    reasons.extend(_station_history_reasons(db, station, target_observation, cutoff))
    if not residuals:
        reasons.append("independent_station_evidence_missing")
    if any(item.observation_id == str(observation_id) or item.station_id == str(station.id)
           for item in residuals):
        reasons.append("leakage_audit_failed")
    country = db.scalar(select(Region.country).join(Spot, Spot.region_id == Region.id)
                        .where(Spot.id == station.spot_id)) or "unknown"
    observed_speed = math.hypot(truth.wind_u_ms or 0.0, truth.wind_v_ms or 0.0)
    previous = db.execute(
        select(WeatherObservation.wind_u_ms, WeatherObservation.wind_v_ms,
               WeatherObservation.observed_at)
        .where(WeatherObservation.station_id == station.id,
               WeatherObservation.observed_at < observed_at,
               WeatherObservation.observed_at >= observed_at - timedelta(hours=1),
               WeatherObservation.received_at <= cutoff,
               WeatherObservation.imported_at <= cutoff,
               WeatherObservation.import_status == "accepted")
        .order_by(WeatherObservation.observed_at.desc()).limit(1)
    ).first()
    weather_regime = "unknown"
    if previous and None not in (previous.wind_u_ms, previous.wind_v_ms,
                                  truth.wind_u_ms, truth.wind_v_ms):
        change = math.hypot(truth.wind_u_ms - previous.wind_u_ms,
                            truth.wind_v_ms - previous.wind_v_ms)
        weather_regime = "rapid_change" if change >= 5.0 else "steady"
    station_meta = station.provenance or {}
    payload = {
        "builder_version": HOLDOUT_BUILDER_VERSION,
        "candidate_version": candidate_version,
        "engine_version": REGIONAL_LIVE_WIND_VERSION,
        "target_station_id": str(station.id), "target_observation_id": str(observation_id),
        "target_station_group": target_station_group,
        "target_correlation_group": station_meta.get("correlation_group"),
        "target_station_metadata_updated_at": station.updated_at.isoformat() if station.updated_at else None,
        "shadow_job_id": str(job.id), "analysis_cutoff_at": cutoff.isoformat(),
        "model_valid_at": observed_at.isoformat(),
        "station_observed_at": observed_at.isoformat(),
        "station_received_at": received_at.isoformat() if received_at else None,
        "station_imported_at": imported_at.isoformat() if imported_at else None,
        "dataset_bundle_hash": bundle.dataset_bundle_hash,
        "dataset_manifest": bundle.dataset_manifest,
        "exact_bundle_manifest": bundle.manifest(),
        "target_model": asdict(target),
        "target_model_members": {
            model: {**asdict(member),
                    "lower": member.lower.model_dump(mode="json"),
                    "upper": member.upper.model_dump(mode="json")}
            for model, member in members.items()
        },
        "target_truth": {"u_ms": truth.wind_u_ms, "v_ms": truth.wind_v_ms},
        "residuals": [asdict(item) for item in residuals],
        "residual_availability": [
            {"residual_id": str(residual.id), "station_id": str(peer.id),
             "observation_id": str(observation.id),
             "observed_at": observation.observed_at.isoformat(),
             "received_at": observation.received_at.isoformat(),
             "imported_at": observation.imported_at.isoformat(),
             "residual_created_at": residual.created_at.isoformat(),
             "station_metadata_updated_at": peer.updated_at.isoformat() if peer.updated_at else None,
             "station_age_seconds": (cutoff - observation.observed_at).total_seconds(),
             "receipt_delay_seconds": (observation.received_at - observation.observed_at).total_seconds(),
             "wigos_id": peer.wigos_id, "icao_id": peer.icao_id,
             "correlation_group": (peer.provenance or {}).get("correlation_group")}
            for peer, observation, residual in accepted
            if str(residual.id) in {item.residual_id for item in residuals}
        ],
        "excluded": [*preexcluded, *excluded],
        "station_selection": selection.payload(),
        "regional": asdict(regional),
        "predictions": {
            "raw_consensus": {"u_ms": target.u_ms, "v_ms": target.v_ms},
            "model_local_physics": asdict(physics_prediction) if physics_prediction else None,
            "multi_station_live_wind": asdict(prediction) if prediction else None,
            "ablation:without_station_residual": (
                asdict(physics_prediction) if physics_prediction else
                {"u_ms": target.u_ms, "v_ms": target.v_ms}
            ),
            "ablation:without_local_physics": asdict(regional_prediction) if regional_prediction else None,
        },
        "target_profile_version": profile.version if profile else None,
        "target_physics_version": profile.physics_version if profile else None,
        "country": country,
        "terrain_class": station_meta.get("terrain_class") or "unknown",
        "coastal_class": station.setting_class or "unknown",
        "season": _season(observed_at), "wind_sector": _sector(target.u_ms, target.v_ms),
        "wind_strength": "strong" if observed_speed >= 10 else "calm" if observed_speed < 2 else "moderate",
        "fallback_reason": regional.fallback_reason,
        "weather_regime": weather_regime,
        "conflict_case": regional.conflict_index >= 0.5,
        "conflict_index": regional.conflict_index,
        "effective_independent_stations": regional.effective_station_count,
        "independent_group_count": len({item.correlation_group or item.station_id for item in residuals}),
        "correction_magnitude_ms": math.hypot(regional.correction_u_ms, regional.correction_v_ms),
        "uncertainty_ms": regional.uncertainty_ms,
        "training_proof_hash": _hash(training_proof) if training_proof else None,
        "leakage_audit": "passed" if "leakage_audit_failed" not in reasons else "failed",
        "residual_rejection_reasons": diagnostics.get("residual_rejection_reasons", {}),
    }
    audit_reasons = audit_persisted_case(payload)
    if audit_reasons:
        reasons.extend(audit_reasons)
        payload["leakage_audit"] = "failed"
        payload["leakage_audit_reasons"] = list(audit_reasons)
    input_hash = _hash(payload)
    context_hash = _hash({"candidate_version": candidate_version, "builder_version": HOLDOUT_BUILDER_VERSION,
                          "training_proof_hash": payload["training_proof_hash"],
                          "dataset_bundle_hash": bundle.dataset_bundle_hash})
    return {
        "candidate_version": candidate_version, "target_station_id": station.id,
        "target_observation_id": observation_id, "shadow_job_id": job.id,
        "analysis_cutoff_at": cutoff, "model_valid_at": observed_at,
        "dataset_bundle_hash": bundle.dataset_bundle_hash,
        "input_hash": input_hash, "context_hash": context_hash,
        "eligibility_status": "eligible" if not reasons else "not_activation_eligible",
        "exclusion_reasons": sorted(set(reasons)),
        "payload": json.loads(json.dumps(payload, sort_keys=True, default=str)),
    }, None


def build_live_wind_holdout_cases(db, loader: ExactRunLoader, *, candidate_version: str,
                                  training_proof: dict | None = None, limit: int = 25,
                                  since: datetime | None = None, until: datetime | None = None,
                                  dry_run: bool = False, recompute: bool = False) -> dict:
    """Bounded replay; one complete insert transaction per case, no updates."""
    if not candidate_version.strip():
        raise ValueError("candidate_version_required")
    started = time.monotonic()
    window_end = _utc(until) or datetime.now(timezone.utc)
    window_start = _utc(since) or window_end - timedelta(days=MAX_CASE_AGE_DAYS)
    if window_start >= window_end or (window_end - window_start).days > MAX_CASE_AGE_DAYS:
        raise ValueError("holdout_window_invalid")
    base = (
        select(WeatherStation, WeatherObservation.id, WeatherObservation.observed_at,
               WeatherObservation.received_at, WeatherObservation.imported_at)
        .join(WeatherObservation, WeatherObservation.station_id == WeatherStation.id)
        .where(WeatherObservation.observed_at >= window_start,
               WeatherObservation.observed_at <= window_end,
               exists(select(WeatherStationModelResidual.id).where(
                   WeatherStationModelResidual.observation_id == WeatherObservation.id,
                   WeatherStationModelResidual.baseline_version == EXACT_BUNDLE_VERSION,
                   WeatherStationModelResidual.activation_eligible.is_(True),
                   WeatherStationModelResidual.qc_status.in_(("accepted", "degraded")),
               )),
               exists(select(WeatherLiveWindJob.id).where(
                   WeatherLiveWindJob.spot_id == WeatherStation.spot_id,
                   WeatherLiveWindJob.status == "succeeded",
                   WeatherLiveWindJob.analyzed_at >= WeatherObservation.observed_at,
                   WeatherLiveWindJob.analyzed_at <= WeatherObservation.observed_at + timedelta(minutes=30),
               )),
               *([] if recompute else [~exists(select(WeatherLiveWindHoldoutCase.id).where(
                   WeatherLiveWindHoldoutCase.target_observation_id == WeatherObservation.id,
                   WeatherLiveWindHoldoutCase.candidate_version == candidate_version,
               ))]))
    )
    batch_size = max(1, min(limit, 500))
    total_pending = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    offset = ((int(datetime.now(timezone.utc).timestamp()) // 600) * batch_size) % total_pending if total_pending else 0
    ordered = base.order_by(WeatherObservation.observed_at, WeatherObservation.id)
    rows = db.execute(ordered.offset(offset).limit(batch_size)).all()
    if offset and len(rows) < batch_size:
        rows.extend(db.execute(ordered.limit(batch_size - len(rows))).all())
    counts = {"selected": len(rows), "inserted": 0, "existing": 0, "eligible": 0,
              "not_activation_eligible": 0, "unbuildable": 0, "errors": 0,
              "dry_run": dry_run, "reasons": {}, "total_pending": total_pending,
              "rotation_offset": offset}
    for station, observation_id, observed_at, received_at, imported_at in rows:
        try:
            job = db.scalar(
                select(WeatherLiveWindJob)
                .where(WeatherLiveWindJob.status == "succeeded",
                       WeatherLiveWindJob.analyzed_at >= observed_at,
                       WeatherLiveWindJob.analyzed_at <= observed_at + timedelta(minutes=30),
                       WeatherLiveWindJob.spot_id == station.spot_id)
                .order_by(WeatherLiveWindJob.analyzed_at, WeatherLiveWindJob.id).limit(1)
            )
            if job is None:
                counts["unbuildable"] += 1
                counts["reasons"]["shadow_job_missing"] = counts["reasons"].get("shadow_job_missing", 0) + 1
                continue
            values, error = _case_for_observation(
                db, loader, station,
                (observation_id, observed_at, received_at, imported_at), job,
                candidate_version=candidate_version, training_proof=training_proof,
            )
            if values is None:
                counts["unbuildable"] += 1
                counts["reasons"][error] = counts["reasons"].get(error, 0) + 1
                continue
            counts[values["eligibility_status"]] += 1
            for reason in values["exclusion_reasons"]:
                counts["reasons"][reason] = counts["reasons"].get(reason, 0) + 1
            for item in values["payload"].get("excluded", []):
                for reason in item.get("reasons", []):
                    counts["reasons"][reason] = counts["reasons"].get(reason, 0) + 1
            if dry_run:
                db.rollback()
                continue
            inserted = db.scalar(
                insert(WeatherLiveWindHoldoutCase).values(values)
                .on_conflict_do_nothing(constraint="uq_live_wind_holdout_case_version")
                .returning(WeatherLiveWindHoldoutCase.id)
            )
            db.commit()
            counts["inserted" if inserted else "existing"] += 1
        except Exception as exc:
            db.rollback()
            counts["errors"] += 1
            key = f"worker_error:{type(exc).__name__}"
            counts["reasons"][key] = counts["reasons"].get(key, 0) + 1
    counts["duration_ms"] = round((time.monotonic() - started) * 1000)
    return counts


def holdout_status(db, *, candidate_version: str) -> dict:
    rows = db.execute(
        select(WeatherLiveWindHoldoutCase.eligibility_status, func.count())
        .where(WeatherLiveWindHoldoutCase.candidate_version == candidate_version)
        .group_by(WeatherLiveWindHoldoutCase.eligibility_status)
    ).all()
    return {"candidate_version": candidate_version, "cases": dict(rows),
            "public_effect": "none", "activation": "manual_only"}


def audit_persisted_case(value: dict) -> tuple[str, ...]:
    """Recheck the sealed as-of and LOSO contract before aggregate scoring."""
    reasons = []
    cutoff = _utc(_parse_time(value.get("analysis_cutoff_at")))
    observed = _utc(_parse_time(value.get("station_observed_at")))
    if cutoff is None or observed is None or observed > cutoff:
        return ("analysis_cutoff_invalid",)
    dataset = value.get("dataset_manifest")
    if (not compatible_dataset_manifests(dataset, dataset)
            or _hash(dataset) != value.get("dataset_bundle_hash")):
        reasons.append("dataset_identity_invalid")
    target_station = value.get("target_station_id")
    target_observation = value.get("target_observation_id")
    target_group = value.get("target_correlation_group")
    excluded = {item.get("station_id") for item in value.get("excluded", [])}
    preselection_reasons = {"target_station", "target_api_duplicate", "dependent_station",
                            "target_correlation_group", "station_metadata_after_cutoff",
                            "station_metadata_time_unproven"}
    preexcluded = {
        item.get("station_id") for item in value.get("excluded", [])
        if preselection_reasons.intersection(item.get("reasons") or [])
    }
    target_updated = _utc(_parse_time(value.get("target_station_metadata_updated_at")))
    if target_updated is None or target_updated > cutoff:
        reasons.append("target_station_metadata_after_or_unknown_cutoff")
    for candidate in (value.get("station_selection") or {}).get("candidates", []):
        if candidate.get("station_id") == target_station or candidate.get("station_id") in preexcluded:
            reasons.append("target_in_station_selection")
    availability = {item.get("residual_id"): item for item in value.get("residual_availability", [])}
    for residual in value.get("residuals", []):
        if residual.get("station_id") == target_station or residual.get("observation_id") == target_observation:
            reasons.append("target_leakage")
        if residual.get("station_id") in excluded:
            reasons.append("excluded_station_reused")
        row = availability.get(residual.get("residual_id"))
        if not row or row.get("station_id") != residual.get("station_id"):
            reasons.append("residual_availability_unproven")
            continue
        if target_group and row.get("correlation_group") == target_group:
            reasons.append("target_correlation_group_leakage")
        for field in ("observed_at", "received_at", "imported_at", "residual_created_at",
                      "station_metadata_updated_at"):
            instant = _utc(_parse_time(row.get(field)))
            if instant is None or instant > cutoff:
                reasons.append(f"{field}_after_or_unknown_cutoff")
        residual_observed = _utc(_parse_time(residual.get("observed_at")))
        if residual_observed is None or residual_observed > cutoff:
            reasons.append("residual_observed_after_cutoff")
    for member in (value.get("exact_bundle_manifest") or {}).get("members", {}).values():
        for asset in member.get("assets", []):
            first = _utc(_parse_time(asset.get("first_seen_at")))
            completed = _utc(_parse_time(asset.get("retrieval_completed_at")))
            if (first is None or completed is None or completed > first or first > observed
                    or asset.get("availability_basis") != "first_seen_capture"):
                reasons.append("target_model_available_after_observation")
    if not (value.get("exact_bundle_manifest") or {}).get("members"):
        reasons.append("target_model_manifest_missing")
    for member in (value.get("target_model_members") or {}).values():
        for endpoint in (member.get("lower"), member.get("upper")):
            if not isinstance(endpoint, dict):
                reasons.append("target_model_endpoint_missing")
            elif endpoint.get("source_product") != "raw_model" or endpoint.get("source_observation_ids"):
                reasons.append("target_derived_model_input")
    return tuple(sorted(set(reasons)))


def verify_persisted_holdouts(db, *, candidate_version: str, training_proof: dict | None,
                              policy: LiveWindVerificationPolicy,
                              dry_run: bool = False) -> dict:
    """Evaluate only latest, immutable, audited cases; insert one aggregate snapshot."""
    end = _utc(_parse_time((training_proof or {}).get("training_window_end")))
    if end is None or not isinstance(training_proof, dict) or training_proof.get("candidate_version") != candidate_version:
        return {"status": "gate_blocked", "reason": "training_boundary_unproven", "cases": 0}
    rows = db.scalars(
        select(WeatherLiveWindHoldoutCase)
        .where(WeatherLiveWindHoldoutCase.candidate_version == candidate_version)
        .order_by(WeatherLiveWindHoldoutCase.created_at.desc(), WeatherLiveWindHoldoutCase.id.desc())
    ).all()
    latest = {}
    for row in rows:
        latest.setdefault(str(row.target_observation_id), row)
    unique_physical_time = {}
    for row in sorted(latest.values(), key=lambda item: (str(item.id), str(item.target_observation_id))):
        group = (row.payload or {}).get("target_station_group") or str(row.target_station_id)
        unique_physical_time.setdefault((group, row.model_valid_at), row)
    eligible = [row for row in unique_physical_time.values() if row.eligibility_status == "eligible"]
    cases = []
    for row in sorted(eligible, key=lambda value: (value.model_valid_at, str(value.id))):
        value = row.payload or {}
        if (_hash(value) != row.input_hash or value.get("leakage_audit") != "passed"
                or value.get("training_proof_hash") != _hash(training_proof)
                or value.get("dataset_bundle_hash") != row.dataset_bundle_hash
                or value.get("candidate_version") != candidate_version):
            return {"status": "gate_blocked", "reason": "leakage_audit_failed", "cases": len(cases)}
        audit_reasons = audit_persisted_case(value)
        if audit_reasons:
            return {"status": "gate_blocked", "reason": "leakage_audit_failed", "cases": len(cases),
                    "audit_reasons": audit_reasons}
        if _training_reasons(training_proof, candidate_version, row.model_valid_at):
            return {"status": "gate_blocked", "reason": "training_boundary_unproven", "cases": len(cases)}
        model = dict(value["target_model"])
        model["valid_at"] = _parse_time(model["valid_at"])
        residuals = []
        for item in value.get("residuals", []):
            item = dict(item)
            item["observed_at"] = _parse_time(item["observed_at"])
            residuals.append(StationResidualInput(**item))
        predictions = value.get("predictions") or {}
        if not isinstance(predictions.get("multi_station_live_wind"), dict):
            return {"status": "gate_blocked", "reason": "candidate_prediction_missing", "cases": len(cases)}
        def prediction(name):
            item = predictions.get(name)
            return HoldoutPrediction(**item) if isinstance(item, dict) else None
        truth = value.get("target_truth") or {}
        cases.append(LiveWindHoldoutCase(
            case_id=str(row.id), target_station_id=str(row.target_station_id),
            target_observation_id=str(row.target_observation_id),
            observed_at=row.model_valid_at,
            observed_u_ms=truth["u_ms"], observed_v_ms=truth["v_ms"],
            target_model=TargetModelState(**model), residuals=tuple(residuals),
            country=value.get("country") or "unknown",
            terrain_class=value.get("terrain_class") or "unknown",
            coastal_class=value.get("coastal_class") or "unknown",
            season=value.get("season") or "unknown",
            wind_sector=value.get("wind_sector") or "unknown",
            wind_strength=value.get("wind_strength") or "unknown",
            station_density=("sparse" if len(residuals) < 3 else "dense"),
            station_group=value.get("target_station_group") or str(row.target_station_id),
            fallback=bool(value.get("fallback_reason")),
            weather_regime=value.get("weather_regime") or "unknown",
            conflict_case=bool(value.get("conflict_case")),
            input_hash=row.input_hash,
            local_physics_prediction=prediction("model_local_physics"),
            candidate_prediction=prediction("multi_station_live_wind"),
            ablation_predictions={
                key.removeprefix("ablation:"): HoldoutPrediction(**item)
                for key, item in predictions.items()
                if key.startswith("ablation:") and isinstance(item, dict)
            },
        ))
    result = evaluate_live_wind_holdouts(
        cases, candidate_version=candidate_version, training_window_end=end,
        policy=policy, evidence_metadata={
            "baseline_source": EXACT_BUNDLE_VERSION,
            "builder_version": HOLDOUT_BUILDER_VERSION,
            "training_proof_hash": _hash(training_proof),
            "leakage_audit": "passed",
            "persisted_case_count": len(cases),
            "case_context_hashes": sorted({row.context_hash for row in eligible}),
        },
    )
    inserted = False
    if not dry_run:
        inserted = persist_live_wind_verification_evidence(db, result)
        db.commit()
    return {
        "status": result.status, "reason": result.reason, "cases": len(cases),
        "input_hash": result.input_hash, "context_hash": result.context_hash,
        "inserted": inserted, "dry_run": dry_run,
        "metrics": result.metrics.get("activation", {}),
        "public_effect": "none", "activation": "manual_only",
    }
