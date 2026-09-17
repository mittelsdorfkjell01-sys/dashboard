"""Deterministic station selection for a spot; never computes a wind correction."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math

from sqlalchemy import select

from app.models import (
    Spot,
    SpotGeoProfileVersion,
    WeatherObservation,
    WeatherObservationImportState,
    WeatherStation,
)
from app.weather.providers.common import haversine_km
from app.weather.station_identity import (
    duplicate_station_groups,
    station_display_identity,
)
from app.weather.vectors import uv_to_wind


@dataclass(frozen=True)
class StationSelectionPolicy:
    version: str = "station-selection-v1"
    max_age_minutes: int = 30
    max_future_minutes: int = 2
    max_distance_km: float = 100.0
    max_elevation_difference_m: float = 600.0
    duplicate_radius_km: float = 0.5
    duplicate_elevation_difference_m: float = 50.0
    correlation_radius_km: float = 15.0
    correlated_group_weight_cap: float = 0.90
    desired_measurement_height_m: float = 10.0
    vector_speed_tolerance_ms: float = 0.20
    vector_direction_tolerance_deg: float = 2.0
    component_weights: tuple[tuple[str, float], ...] = (
        ("measurement_age", 0.12),
        ("distance", 0.13),
        ("elevation_difference", 0.10),
        ("measurement_height", 0.07),
        ("terrain_similarity", 0.10),
        ("roughness_similarity", 0.09),
        ("surface_context", 0.10),
        ("mountain_side", 0.10),
        ("wind_sector", 0.06),
        ("exposure", 0.06),
        ("provider_station_history", 0.07),
    )

    def __post_init__(self) -> None:
        total = sum(weight for _, weight in self.component_weights)
        if not math.isclose(total, 1.0, abs_tol=1e-9):
            raise ValueError("station-selection component weights must sum to 1")
        if dict(self.component_weights)["measurement_age"] > 0.20:
            raise ValueError("freshness must not dominate station selection")

    def snapshot(self) -> dict:
        payload = asdict(self)
        payload["component_weights"] = dict(self.component_weights)
        return payload

    @property
    def configuration_hash(self) -> str:
        encoded = json.dumps(
            self.snapshot(), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


DEFAULT_STATION_SELECTION_POLICY = StationSelectionPolicy()


@dataclass(frozen=True)
class SpotSelectionContext:
    latitude: float
    longitude: float
    elevation_m: float | None = None
    measurement_height_m: float = 10.0
    terrain_class: str | None = None
    roughness_length_m: float | None = None
    surface_context: str | None = None
    mountain_side: str | None = None
    air_mass_id: str | None = None
    wind_direction_deg: float | None = None
    geo_profile_version: str | None = None


@dataclass(frozen=True)
class StationCandidate:
    station: object
    observation: object | None
    provider_history_score: float | None = None
    station_history_score: float | None = None


@dataclass
class CandidateEvaluation:
    station_identity: str
    station_id: str | None
    observation_id: str | None
    provider: str
    provider_station_id: str
    eligible: bool
    exclusion_reasons: list[str]
    component_weights: dict[str, dict[str, float]] = field(default_factory=dict)
    base_score: float = 0.0
    correlation_group: str | None = None
    correlation_factor: float = 0.0
    total_weight: float = 0.0
    normalized_weight: float = 0.0
    distance_km: float | None = None
    elevation_difference_m: float | None = None
    observed_at: str | None = None
    air_mass_id: str | None = None

    def payload(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StationSelectionResult:
    policy_version: str
    configuration_hash: str
    configuration: dict
    target_context: dict
    evaluated_at: datetime
    candidates: tuple[CandidateEvaluation, ...]

    @property
    def selected(self) -> CandidateEvaluation | None:
        return next((candidate for candidate in self.candidates if candidate.eligible), None)

    def payload(self) -> dict:
        selected = self.selected
        return {
            "policy_version": self.policy_version,
            "configuration_hash": self.configuration_hash,
            "configuration": self.configuration,
            "target_context": self.target_context,
            "evaluated_at": self.evaluated_at.isoformat(),
            "selected_station_identity": (
                selected.station_identity if selected is not None else None
            ),
            "candidates": [candidate.payload() for candidate in self.candidates],
        }


def _finite(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _aware_utc(value) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _provenance(station) -> dict:
    value = getattr(station, "provenance", None)
    return value if isinstance(value, dict) else {}


def _meta(station, name: str, default=None):
    direct = getattr(station, name, None)
    if direct is not None:
        return direct
    return _provenance(station).get(name, default)


def _circular_difference(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def provider_quality_acceptable(observation) -> bool:
    """Shared conservative provider-quality gate for accepted observations."""
    quality = str(getattr(observation, "provider_quality", "") or "").strip().lower()
    if any(token in quality for token in ("bad", "suspect", "reject", "invalid", "failed")):
        return False
    # AWC exposes qcField as an opaque bit field, not an ordinal grade.  Its
    # presence is retained for audit but must not be guessed into a quality rank.
    if quality.startswith("awc_qc:"):
        return True
    return quality in {"", "0", "1", "2", "3", "accepted", "good"}


def _vector_reasons(observation, policy: StationSelectionPolicy) -> list[str]:
    if observation is None:
        return ["observation_missing"]
    speed = _finite(getattr(observation, "wind_speed_ms", None))
    direction = _finite(getattr(observation, "wind_direction_deg", None))
    u_ms = _finite(getattr(observation, "wind_u_ms", None))
    v_ms = _finite(getattr(observation, "wind_v_ms", None))
    if speed is None or not 0 <= speed <= 75 or u_ms is None or v_ms is None:
        return ["wind_vector_invalid"]
    if speed > 0 and (direction is None or not 0 <= direction < 360):
        return ["wind_vector_invalid"]
    vector_speed, vector_direction = uv_to_wind(u_ms, v_ms)
    reasons = []
    if abs(vector_speed - speed) > policy.vector_speed_tolerance_ms:
        reasons.append("wind_vector_inconsistent")
    if speed > policy.vector_speed_tolerance_ms and direction is not None and (
        _circular_difference(vector_direction, direction)
        > policy.vector_direction_tolerance_deg
    ):
        reasons.append("wind_vector_inconsistent")
    return list(dict.fromkeys(reasons))


def _hard_reasons(
    candidate: StationCandidate,
    target: SpotSelectionContext,
    *,
    now: datetime,
    policy: StationSelectionPolicy,
) -> tuple[list[str], float | None, float | None]:
    station, observation = candidate.station, candidate.observation
    reasons = []
    if not getattr(station, "active", False):
        reasons.append("station_inactive")
    if not getattr(station, "approved", False):
        reasons.append("station_unapproved")
    if getattr(station, "blocked", False):
        reasons.append("station_blocked")
    if getattr(station, "representativeness_status", "unreviewed") != "passed":
        reasons.append("representativeness_unpassed")

    observed_at = _aware_utc(getattr(observation, "observed_at", None))
    if observed_at is None:
        reasons.append("observation_time_invalid")
    else:
        age = now - observed_at
        if age > timedelta(minutes=policy.max_age_minutes):
            reasons.append("observation_stale")
        if age < -timedelta(minutes=policy.max_future_minutes):
            reasons.append("observation_future")
    reasons.extend(_vector_reasons(observation, policy))
    if observation is not None and not provider_quality_acceptable(observation):
        reasons.append("provider_quality_rejected")
    if observation is not None and getattr(observation, "import_status", None) != "accepted":
        reasons.append("import_rejected")

    latitude = _finite(getattr(station, "latitude", None))
    longitude = _finite(getattr(station, "longitude", None))
    distance = None
    if latitude is None or longitude is None:
        reasons.append("station_coordinates_invalid")
    else:
        distance = haversine_km(target.latitude, target.longitude, latitude, longitude)
        if distance > policy.max_distance_km:
            reasons.append("distance_exceeded")

    station_elevation = _finite(getattr(station, "elevation_m", None))
    difference = None
    if station_elevation is not None and target.elevation_m is not None:
        difference = abs(station_elevation - target.elevation_m)
        if difference > policy.max_elevation_difference_m:
            reasons.append("elevation_difference_exceeded")
    return list(dict.fromkeys(reasons)), distance, difference


def _similarity(left, right, *, missing=0.5) -> float:
    if left is None or right is None:
        return missing
    return 1.0 if str(left).lower() == str(right).lower() else 0.1


def _reliability(value, *, default=0.5) -> float:
    number = _finite(value)
    return default if number is None else max(0.0, min(1.0, number))


def _sector_score(station, direction: float | None) -> float:
    if direction is None:
        return 0.5
    scores = _meta(station, "wind_sector_scores")
    if not isinstance(scores, dict):
        return _reliability(_meta(station, "wind_sector_score"), default=0.5)
    sector = int(direction // 30) % 12
    return _reliability(scores.get(str(sector), scores.get(sector)), default=0.5)


def _component_scores(
    candidate: StationCandidate,
    target: SpotSelectionContext,
    *,
    now: datetime,
    policy: StationSelectionPolicy,
    distance: float,
    elevation_difference: float | None,
) -> dict[str, float]:
    station, observation = candidate.station, candidate.observation
    observed_at = _aware_utc(getattr(observation, "observed_at", None))
    age_minutes = max(0.0, (now - observed_at).total_seconds() / 60.0)
    station_height = _finite(getattr(station, "measurement_height_m", None))
    height_score = (
        0.4
        if station_height is None
        else math.exp(-abs(station_height - target.measurement_height_m) / 10.0)
    )
    station_roughness = _finite(_meta(station, "roughness_length_m"))
    if station_roughness is None or target.roughness_length_m is None:
        roughness_score = 0.5
    elif station_roughness <= 0 or target.roughness_length_m <= 0:
        roughness_score = 0.0
    else:
        roughness_score = math.exp(
            -abs(math.log(station_roughness / target.roughness_length_m)) / 2.0
        )
    provider_history = _reliability(_meta(station, "provider_reliability"))
    station_history = _reliability(_meta(station, "station_reliability"))
    if candidate.provider_history_score is not None:
        provider_history = (
            provider_history + _reliability(candidate.provider_history_score)
        ) / 2.0
    if candidate.station_history_score is not None:
        station_history = (
            station_history + _reliability(candidate.station_history_score)
        ) / 2.0
    exposure = {
        "passed": 1.0,
        "limited": 0.55,
        "unknown": 0.4,
        "failed": 0.0,
    }.get(str(getattr(station, "exposure_status", "unknown")).lower(), 0.4)
    station_surface_context = getattr(station, "setting_class", None)
    if station_surface_context in {None, "unknown"}:
        station_surface_context = _meta(station, "surface_context")
    current_sector_direction = (
        target.wind_direction_deg
        if target.wind_direction_deg is not None
        else _finite(getattr(observation, "wind_direction_deg", None))
    )
    return {
        "measurement_age": max(0.0, 1.0 - age_minutes / policy.max_age_minutes),
        "distance": max(0.0, 1.0 - distance / policy.max_distance_km),
        "elevation_difference": (
            0.5
            if elevation_difference is None
            else max(0.0, 1.0 - elevation_difference / policy.max_elevation_difference_m)
        ),
        "measurement_height": height_score,
        "terrain_similarity": _similarity(
            _meta(station, "terrain_class"), target.terrain_class
        ),
        "roughness_similarity": roughness_score,
        "surface_context": _similarity(
            station_surface_context, target.surface_context
        ),
        "mountain_side": _similarity(
            _meta(station, "mountain_side"), target.mountain_side
        ),
        "wind_sector": _sector_score(station, current_sector_direction),
        "exposure": exposure,
        "provider_station_history": (provider_history + station_history) / 2.0,
    }


def _canonical_duplicate(
    group: tuple[int, ...],
    candidates: list[StationCandidate],
    reasons: list[list[str]],
) -> int:
    def rank(index: int):
        station, observation = candidates[index].station, candidates[index].observation
        observed_at = _aware_utc(getattr(observation, "observed_at", None))
        reliability = _reliability(_meta(station, "station_reliability"))
        identity_count = sum(
            bool(getattr(station, attribute, None)) for attribute in ("wigos_id", "icao_id")
        )
        return (
            not bool(reasons[index]),
            bool(getattr(station, "approved", False)),
            reliability,
            identity_count,
            observed_at or datetime.min.replace(tzinfo=timezone.utc),
            station_display_identity(station),
        )

    return max(group, key=rank)


def _correlation_groups(
    eligible_indices: list[int], candidates: list[StationCandidate], radius_km: float
) -> list[list[int]]:
    adjacency = {index: set() for index in eligible_indices}
    for position, left in enumerate(eligible_indices):
        left_station = candidates[left].station
        left_coordinate = (
            float(getattr(left_station, "latitude")),
            float(getattr(left_station, "longitude")),
        )
        for right in eligible_indices[position + 1:]:
            right_station = candidates[right].station
            if haversine_km(
                *left_coordinate,
                float(getattr(right_station, "latitude")),
                float(getattr(right_station, "longitude")),
            ) <= radius_km:
                adjacency[left].add(right)
                adjacency[right].add(left)
    groups = []
    unseen = set(eligible_indices)
    while unseen:
        seed = min(unseen)
        stack, group = [seed], []
        unseen.remove(seed)
        while stack:
            current = stack.pop()
            group.append(current)
            for neighbor in adjacency[current] & unseen:
                unseen.remove(neighbor)
                stack.append(neighbor)
        groups.append(sorted(group))
    return groups


def evaluate_station_candidates(
    candidates: list[StationCandidate],
    target: SpotSelectionContext,
    *,
    now: datetime | None = None,
    policy: StationSelectionPolicy = DEFAULT_STATION_SELECTION_POLICY,
) -> StationSelectionResult:
    """Gathered candidates -> hard gates -> scoring -> correlation limiting."""
    evaluated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    hard = []
    distances = []
    elevation_differences = []
    for candidate in candidates:
        reasons, distance, difference = _hard_reasons(
            candidate, target, now=evaluated_at, policy=policy
        )
        hard.append(reasons)
        distances.append(distance)
        elevation_differences.append(difference)

    # Duplicate detection intentionally happens across the complete gathered
    # set.  The best valid representative survives; every alias remains visible.
    for group in duplicate_station_groups(
        [candidate.station for candidate in candidates],
        spatial_threshold_km=policy.duplicate_radius_km,
        elevation_threshold_m=policy.duplicate_elevation_difference_m,
    ):
        canonical = _canonical_duplicate(group, candidates, hard)
        canonical_identity = station_display_identity(candidates[canonical].station)
        for index in group:
            if index != canonical:
                hard[index].append(f"duplicate_of:{canonical_identity}")

    weights = dict(policy.component_weights)
    evaluations = []
    for index, candidate in enumerate(candidates):
        station, observation = candidate.station, candidate.observation
        eligible = not hard[index]
        components = {}
        base_score = 0.0
        if eligible:
            scores = _component_scores(
                candidate,
                target,
                now=evaluated_at,
                policy=policy,
                distance=distances[index],
                elevation_difference=elevation_differences[index],
            )
            for name, score in scores.items():
                weighted = score * weights[name]
                components[name] = {
                    "score": round(score, 6),
                    "policy_weight": weights[name],
                    "weighted_value": round(weighted, 6),
                }
                base_score += weighted
        observed = _aware_utc(getattr(observation, "observed_at", None))
        evaluations.append(CandidateEvaluation(
            station_identity=station_display_identity(station),
            station_id=(str(getattr(station, "id")) if getattr(station, "id", None) else None),
            observation_id=(
                str(getattr(observation, "id"))
                if getattr(observation, "id", None)
                else None
            ),
            provider=str(getattr(station, "provider", "")),
            provider_station_id=str(
                getattr(station, "provider_station_id", None)
                or getattr(station, "station_id", "")
            ),
            eligible=eligible,
            exclusion_reasons=list(dict.fromkeys(hard[index])),
            component_weights=components,
            base_score=round(base_score, 6),
            distance_km=(round(distances[index], 6) if distances[index] is not None else None),
            elevation_difference_m=(
                round(elevation_differences[index], 3)
                if elevation_differences[index] is not None else None
            ),
            observed_at=observed.isoformat() if observed else None,
            air_mass_id=(
                str(_meta(station, "air_mass_id"))
                if _meta(station, "air_mass_id")
                else None
            ),
        ))

    eligible_indices = [index for index, item in enumerate(evaluations) if item.eligible]
    correlation_groups = _correlation_groups(
        eligible_indices, candidates, policy.correlation_radius_km
    )
    for group_number, group in enumerate(correlation_groups, start=1):
        group_id = f"cluster-{group_number}"
        ordered = sorted(group, key=lambda index: evaluations[index].base_score, reverse=True)
        raw = [evaluations[index].base_score / math.sqrt(rank + 1) for rank, index in enumerate(ordered)]
        scale = (
            1.0
            if len(group) == 1
            else min(
                1.0,
                policy.correlated_group_weight_cap / sum(raw) if sum(raw) else 0.0,
            )
        )
        for rank, (index, value) in enumerate(zip(ordered, raw), start=1):
            evaluations[index].correlation_group = group_id
            evaluations[index].correlation_factor = round(scale / math.sqrt(rank), 6)
            evaluations[index].total_weight = round(value * scale, 6)

    total = sum(item.total_weight for item in evaluations)
    if total:
        for item in evaluations:
            item.normalized_weight = round(item.total_weight / total, 6)
    evaluations.sort(
        key=lambda item: (
            not item.eligible,
            -item.total_weight,
            item.station_identity,
        )
    )
    return StationSelectionResult(
        policy_version=policy.version,
        configuration_hash=policy.configuration_hash,
        configuration=policy.snapshot(),
        target_context=asdict(target),
        evaluated_at=evaluated_at,
        candidates=tuple(evaluations),
    )


def _surface_context(spot, profile) -> str | None:
    kinds = set(getattr(spot, "water_type", None) or [])
    if kinds & {"ocean", "sea", "lagoon"} or getattr(profile, "coastal_normal_deg", None) is not None:
        return "coastal"
    if kinds & {"lake", "river", "reservoir"}:
        return "inland"
    return None


def select_stations_for_spot(
    db,
    spot_id,
    *,
    now: datetime | None = None,
    wind_direction_deg: float | None = None,
    policy: StationSelectionPolicy = DEFAULT_STATION_SELECTION_POLICY,
) -> StationSelectionResult:
    """Load every configured candidate and only then run the common selector."""
    from geoalchemy2.shape import to_shape

    spot = db.get(Spot, spot_id)
    if spot is None:
        raise LookupError("spot_not_found")
    stations = list(db.scalars(
        select(WeatherStation).where(WeatherStation.spot_id == spot_id)
    ).all())
    latest_by_station = {}
    import_state_by_station = {}
    if stations:
        observations = db.scalars(
            select(WeatherObservation)
            .where(WeatherObservation.station_id.in_([station.id for station in stations]))
            .distinct(WeatherObservation.station_id)
            .order_by(
                WeatherObservation.station_id,
                WeatherObservation.observed_at.desc(),
            )
        ).all()
        for observation in observations:
            latest_by_station.setdefault(observation.station_id, observation)
        import_states = db.scalars(
            select(WeatherObservationImportState).where(
                WeatherObservationImportState.station_id.in_(
                    [station.id for station in stations]
                )
            )
        ).all()
        import_state_by_station = {state.station_id: state for state in import_states}

    provider_operational_scores: dict[str, float] = {}
    for provider in {station.provider for station in stations}:
        provider_states = [
            import_state_by_station.get(station.id)
            for station in stations
            if station.provider == provider and import_state_by_station.get(station.id)
        ]
        if provider_states:
            provider_operational_scores[provider] = sum(
                1.0
                if state.status == "success"
                else max(0.1, 1.0 / (1.0 + state.consecutive_failures))
                for state in provider_states
            ) / len(provider_states)

    profile = getattr(spot, "weather_profile", None)
    geo_profile = db.scalar(
        select(SpotGeoProfileVersion).where(
            SpotGeoProfileVersion.spot_id == spot_id,
            SpotGeoProfileVersion.active.is_(True),
        ).order_by(SpotGeoProfileVersion.version.desc()).limit(1)
    )
    geo_payload = geo_profile.profile if geo_profile and isinstance(geo_profile.profile, dict) else {}
    point = to_shape(spot.location)
    target = SpotSelectionContext(
        latitude=float(point.y),
        longitude=float(point.x),
        elevation_m=(
            _finite(getattr(profile, "elevation_m", None))
            if _finite(getattr(profile, "elevation_m", None)) is not None
            else _finite(geo_payload.get("elevation_m"))
        ),
        measurement_height_m=policy.desired_measurement_height_m,
        terrain_class=geo_payload.get("terrain_class"),
        roughness_length_m=_finite(getattr(profile, "roughness_length_m", None)),
        surface_context=_surface_context(spot, profile),
        mountain_side=geo_payload.get("mountain_side"),
        air_mass_id=geo_payload.get("air_mass_id"),
        wind_direction_deg=wind_direction_deg,
        geo_profile_version=(
            f"{geo_profile.algorithm_version}:{geo_profile.version}" if geo_profile else None
        ),
    )
    return evaluate_station_candidates(
        [
            StationCandidate(
                station,
                latest_by_station.get(station.id),
                provider_history_score=provider_operational_scores.get(station.provider),
                station_history_score=(
                    None
                    if (state := import_state_by_station.get(station.id)) is None
                    else 1.0
                    if state.status == "success"
                    else max(0.1, 1.0 / (1.0 + state.consecutive_failures))
                ),
            )
            for station in stations
        ],
        target,
        now=now,
        policy=policy,
    )
