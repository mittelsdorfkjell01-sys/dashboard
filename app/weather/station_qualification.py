"""Reproducible epoch-scoped station statistics and review dossiers.

Statistics describe evidence. They never grant monitoring or model-use scopes.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.models import (
    AdminUser, WeatherObservation, WeatherObservationRevision, WeatherStationApprovalAudit,
    WeatherStationDossier, WeatherStationEpoch, WeatherStationGroupDecision,
    WeatherStationMetadataRevision,
)
from app.weather.observation_quality import QC_VERSION, GOVERNANCE_REASONS
from app.weather.station_identity import possible_duplicate_candidates
from app.weather.providers.common import haversine_km

STATISTICS_VERSION = "station-temporal-qc-v1"
DOSSIER_VERSION = "station-dossier-v1"


@dataclass(frozen=True)
class QualificationPolicy:
    """Unset scientific thresholds are intentionally incapable of approval."""

    version: str = "station-qualification-unconfigured-v1"
    min_operational_days: int | None = None
    min_completeness: float | None = None
    max_latency_p95_minutes: float | None = None
    max_outage_share: float | None = None
    max_qc_exclusion_share: float | None = None
    allow_unknown_measurement_height: bool | None = None

    @property
    def configured(self) -> bool:
        return all(value is not None for value in (
            self.min_operational_days, self.min_completeness,
            self.max_latency_p95_minutes, self.max_outage_share,
            self.max_qc_exclusion_share, self.allow_unknown_measurement_height,
        ))


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 3)


def _window_statistics(rows, start: datetime, end: datetime, interval_minutes: int | None) -> dict:
    rows = sorted(rows, key=lambda item: (item.observed_at, str(item.id)))
    interval = timedelta(minutes=interval_minutes) if interval_minutes and interval_minutes > 0 else None
    expected = (math.floor((end - start) / interval) + 1) if interval else None
    timestamps = sorted({row.observed_at for row in rows})
    interior_gaps = [b - a for a, b in zip(timestamps, timestamps[1:])]
    gaps = ([timestamps[0] - start, *interior_gaps, end - timestamps[-1]]
            if timestamps else [end - start])
    outages = [gap for gap in gaps if interval and gap > interval * 1.5]
    latencies = [(row.received_at - row.observed_at).total_seconds() / 60 for row in rows
                 if row.received_at is not None]
    speeds = [float(row.wind_speed_ms) for row in rows if row.wind_speed_ms is not None]
    qc_counts = Counter(str(reason) for row in rows for reason in (row.qc_flags or []))
    accepted = sum(row.import_status == "accepted" and not
                   set(row.qc_flags or []).difference(GOVERNANCE_REASONS) for row in rows)
    return {
        "expected": expected,
        "received": len(rows),
        "first_observed_at": timestamps[0] if timestamps else None,
        "last_observed_at": timestamps[-1] if timestamps else None,
        "completeness": round(len(timestamps) / expected, 4) if expected else None,
        "longest_gap_minutes": round(max(gaps).total_seconds() / 60, 2) if gaps else None,
        "longest_interior_gap_minutes": round(max(interior_gaps).total_seconds() / 60, 2) if interior_gaps else None,
        "outage_count": len(outages),
        "outage_duration_minutes": round(sum((gap - interval for gap in outages), timedelta()).total_seconds() / 60, 2) if interval else None,
        "latency_minutes": {f"p{int(q * 100)}": _quantile(latencies, q) for q in (0.5, 0.9, 0.95, 0.99)},
        "on_time_30m_share": round(sum(0 <= delay <= 30 for delay in latencies) / len(latencies), 4) if latencies else None,
        "qc_acceptance_share": round(accepted / len(rows), 4) if rows else None,
        "qc_reasons": dict(sorted(qc_counts.items())),
        "intrinsic_qc_reasons": dict(sorted((key, value) for key, value in qc_counts.items()
                                            if key not in GOVERNANCE_REASONS)),
        "governance_reasons": dict(sorted((key, value) for key, value in qc_counts.items()
                                           if key in GOVERNANCE_REASONS)),
        "missing_direction": sum(row.wind_direction_deg is None for row in rows),
        "calm": sum(row.wind_speed_ms is not None and row.wind_speed_ms < 0.5 for row in rows),
        "speed_ms": {"min": min(speeds) if speeds else None,
                     "p50": _quantile(speeds, 0.5), "p90": _quantile(speeds, 0.9),
                     "max": max(speeds) if speeds else None},
        "gust_available": sum(row.wind_gust_ms is not None for row in rows),
        "sensor_stuck": qc_counts.get("sensor_stuck", 0),
        "wind_jump": qc_counts.get("wind_jump", 0),
        "last_valid_observed_at": max((row.observed_at for row in rows
                                       if row.import_status == "accepted" and not
                                       set(row.qc_flags or []).difference(GOVERNANCE_REASONS)), default=None),
    }


def temporal_quality(db, epoch: WeatherStationEpoch, *, end: datetime,
                     window_days: int = 14) -> dict:
    if end.tzinfo is None or end.utcoffset() is None or window_days < 1:
        raise ValueError("valid_utc_window_required")
    end = end.astimezone(timezone.utc)
    start = end - timedelta(days=window_days)
    rows = db.scalars(select(WeatherObservation).where(
        WeatherObservation.epoch_id == epoch.id,
        WeatherObservation.observed_at >= start,
        WeatherObservation.observed_at <= end,
    ).order_by(WeatherObservation.observed_at, WeatherObservation.id)).all()
    interval = (epoch.configuration.get("sensor_metadata") or {}).get("typical_interval_minutes")
    if interval is None:
        interval = epoch.configuration.get("typical_interval_minutes")
    operational = [row for row in rows if row.availability_class == "captured_operationally"]
    historical = [row for row in rows if row.availability_class == "historical_backfill"]
    unproven = [row for row in rows if row.availability_class == "availability_unproven"]
    revisions = db.scalars(select(WeatherObservationRevision).where(
        WeatherObservationRevision.epoch_id == epoch.id,
        WeatherObservationRevision.observed_at >= start,
        WeatherObservationRevision.observed_at <= end,
    )).all()
    metadata = db.scalars(select(WeatherStationMetadataRevision).where(
        WeatherStationMetadataRevision.station_id == epoch.station_id,
        WeatherStationMetadataRevision.received_at >= start,
        WeatherStationMetadataRevision.received_at <= end,
    )).all()
    return {
        "version": STATISTICS_VERSION, "qc_version": QC_VERSION,
        "window_start": start, "window_end": end,
        "interval_minutes": interval,
        "operational": _window_statistics(operational, start, end, interval),
        "historical": _window_statistics(historical, start, end, interval),
        "availability_unproven_count": len(unproven),
        "provider_revision_count": sum(row.revision_status == "pending_review" for row in revisions),
        "metadata_revision_count": len(metadata),
    }


def current_group_decisions(db, epoch_id) -> dict:
    rows = db.scalars(select(WeatherStationGroupDecision).where(
        WeatherStationGroupDecision.epoch_id == epoch_id
    ).order_by(WeatherStationGroupDecision.decided_at, WeatherStationGroupDecision.id)).all()
    latest = {}
    for row in rows:
        latest[row.group_type] = row
    return latest


def propose_group_candidates(db, stations: list, *, dry_run: bool = True,
                             evidence_end: datetime | None = None) -> dict:
    """Persist identity hints only; no candidate confirms sensor identity."""
    evidence_end = evidence_end or datetime.now(timezone.utc)
    hints = possible_duplicate_candidates(stations)
    proposed = 0
    for left_index, right_index, reasons in hints:
        left, right = stations[left_index], stations[right_index]
        key = "candidate:" + ":".join(sorted((str(left.id), str(right.id))))
        evidence = {"station_ids": sorted((str(left.id), str(right.id))),
                    "distance_km": round(haversine_km(left.latitude, left.longitude,
                                                       right.latitude, right.longitude), 4),
                    "evidence_end": evidence_end.isoformat(), "confidence": None,
                    "reasons": list(reasons)}
        if dry_run:
            proposed += 1
            continue
        for station in (left, right):
            if station.current_epoch_id is None:
                continue
            inserted = db.execute(insert(WeatherStationGroupDecision).values(
                epoch_id=station.current_epoch_id, group_type="physical",
                group_key=key, status="proposed", rule_version="identity-candidate-v1",
                evidence=evidence, actor=None, reason="possible shared station; manual sensor review required",
            ).on_conflict_do_nothing(index_elements=["epoch_id", "group_type", "group_key"],
                                      index_where=text("status = 'proposed'")).returning(
                                          WeatherStationGroupDecision.id)).scalars().all()
            proposed += len(inserted)
            if inserted:
                station.blocked = True
                station.identity_review_status = "unreviewed"
        db.flush()
    if not dry_run:
        db.commit()
    return {"candidate_pairs": len(hints), "proposal_rows": proposed, "dry_run": dry_run}


def group_version(decisions: dict) -> str | None:
    if not all(decisions.get(kind) and decisions[kind].status == "confirmed"
               for kind in ("physical", "correlation")):
        return None
    material = [(kind, decisions[kind].group_key, str(decisions[kind].id))
                for kind in ("physical", "correlation")]
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def build_dossier(db, station, *, end: datetime, window_days: int = 14) -> tuple[dict, str]:
    epoch = db.get(WeatherStationEpoch, station.current_epoch_id) if station.current_epoch_id else None
    if epoch is None or epoch.station_id != station.id:
        raise ValueError("station_epoch_unavailable")
    statistics = temporal_quality(db, epoch, end=end, window_days=window_days)
    groups = current_group_decisions(db, epoch.id)
    group_history = db.scalars(select(WeatherStationGroupDecision).where(
        WeatherStationGroupDecision.epoch_id == epoch.id
    ).order_by(WeatherStationGroupDecision.decided_at, WeatherStationGroupDecision.id)).all()
    revisions = db.scalars(select(WeatherObservationRevision.payload_hash).where(
        WeatherObservationRevision.epoch_id == epoch.id
    ).order_by(WeatherObservationRevision.payload_hash)).all()
    blockers = []
    if not station.license or station.license != "CC BY 4.0":
        blockers.append("license_unverified")
    if epoch.configuration.get("measurement_height_m") is None:
        blockers.append("measurement_height_unknown")
    if epoch.configuration.get("elevation_m") is None:
        blockers.append("station_elevation_unknown")
    if epoch.status != "reviewed":
        blockers.append("epoch_unreviewed")
    if group_version(groups) is None:
        blockers.append("dependency_groups_unreviewed")
    if statistics["operational"]["received"] == 0:
        blockers.append("operational_evidence_missing")
    approvals = db.scalars(select(WeatherStationApprovalAudit).where(
        WeatherStationApprovalAudit.epoch_id == epoch.id
    ).order_by(WeatherStationApprovalAudit.decided_at, WeatherStationApprovalAudit.id)).all()
    payload = {
        "version": DOSSIER_VERSION, "epoch_id": str(epoch.id),
        "epoch_number": epoch.epoch_number, "configuration_hash": epoch.configuration_hash,
        "configuration": epoch.configuration,
        "station": {"provider": station.provider, "provider_station_id": station.provider_station_id,
                    "physical_station_group": station.physical_station_group,
                    "wigos_id": station.wigos_id, "icao_id": station.icao_id,
                    "operator": station.operator, "station_type": station.station_type},
        "statistics": statistics,
        "independence": {key: {"group_key": row.group_key, "status": row.status,
                               "rule_version": row.rule_version, "evidence": row.evidence,
                               "reason": row.reason}
                         for key, row in sorted(groups.items())},
        "group_review_history": [{"type": row.group_type, "key": row.group_key,
                                  "status": row.status, "rule_version": row.rule_version,
                                  "evidence": row.evidence, "reviewer": row.actor,
                                  "reviewed_at": row.decided_at, "reason": row.reason}
                                 for row in group_history],
        "group_version": group_version(groups),
        "provenance": {"source_url": station.source_url, "license": station.license,
                       "license_reviewed_at": epoch.reviewed_at,
                       "attribution_required": (station.provenance or {}).get("attribution_required"),
                       "metadata_payload_hash": station.metadata_payload_hash,
                       "metadata_received_at": db.scalar(select(WeatherStationMetadataRevision.received_at).where(
                           WeatherStationMetadataRevision.station_id == station.id
                       ).order_by(WeatherStationMetadataRevision.received_at.desc())),
                       "observation_payload_hashes_digest": hashlib.sha256("".join(revisions).encode()).hexdigest(),
                       "parser_version": sorted({row.parser_version for row in db.scalars(select(WeatherObservationRevision).where(
                           WeatherObservationRevision.epoch_id == epoch.id)).all()}),
                       "qc_version": QC_VERSION},
        "decision": {"blockers": sorted(blockers),
                     "ready_for_review": statistics["operational"]["received"] > 0 or statistics["historical"]["received"] > 0,
                     "existing_approvals": [{"scope": row.scope, "approved": row.approved,
                                             "decided_at": row.decided_at} for row in approvals],
                     "next_review": "configure_policy_and_review_epoch_groups"},
    }
    serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return payload, hashlib.sha256(serialized.encode()).hexdigest()


def persist_dossier(db, station, *, end: datetime, window_days: int = 14,
                    dry_run: bool = True) -> tuple[dict, str]:
    payload, dossier_hash = build_dossier(db, station, end=end, window_days=window_days)
    if not dry_run:
        db.execute(insert(WeatherStationDossier).values(
            epoch_id=station.current_epoch_id, dossier_hash=dossier_hash,
            payload=json.loads(json.dumps(payload, default=str)),
            ready_for_review=payload["decision"]["ready_for_review"],
        ).on_conflict_do_nothing(index_elements=["dossier_hash"]))
        db.commit()
    return payload, dossier_hash


def _require_reviewer(reviewer: AdminUser | None) -> str:
    if reviewer is None or not reviewer.is_active or reviewer.role != "admin":
        raise ValueError("authenticated_admin_reviewer_required")
    return reviewer.email


def decide_group(db, station, *, group_type: str, group_key: str,
                 status: str, reviewer: AdminUser | None, reason: str,
                 evidence: dict, rule_version: str = "manual-group-review-v1") -> None:
    actor = _require_reviewer(reviewer)
    if group_type not in {"physical", "sensor", "correlation"} or status not in {"confirmed", "rejected"}:
        raise ValueError("group_decision_invalid")
    if not group_key.strip() or not reason.strip() or not evidence:
        raise ValueError("group_evidence_required")
    epoch = db.get(WeatherStationEpoch, station.current_epoch_id) if station.current_epoch_id else None
    if epoch is None:
        raise ValueError("station_epoch_unavailable")
    db.add(WeatherStationGroupDecision(
        epoch_id=epoch.id, group_type=group_type, group_key=group_key.strip(),
        status=status, rule_version=rule_version, evidence=evidence,
        actor=actor, reason=reason.strip(),
    ))
    if group_type == "physical":
        station.physical_station_group = group_key.strip() if status == "confirmed" else None
    if group_type == "correlation":
        station.correlation_group = group_key.strip() if status == "confirmed" else None
    station.identity_review_status = "unreviewed"
    station.blocked = True
    db.flush()


def review_epoch(db, station, *, reviewer: AdminUser | None, reason: str) -> None:
    actor = _require_reviewer(reviewer)
    if not reason.strip():
        raise ValueError("review_reason_required")
    epoch = db.get(WeatherStationEpoch, station.current_epoch_id) if station.current_epoch_id else None
    if epoch is None or group_version(current_group_decisions(db, epoch.id)) is None:
        raise ValueError("dependency_groups_unreviewed")
    config = epoch.configuration
    if any(config.get(key) is None for key in ("latitude", "longitude", "elevation_m")):
        raise ValueError("station_location_or_height_unknown")
    for key in ("latitude", "longitude", "elevation_m", "measurement_height_m",
                "sensor_metadata", "wigos_id", "icao_id", "station_type"):
        setattr(station, key, config.get(key))
    epoch.status = "reviewed"
    epoch.reviewer = actor
    epoch.review_reason = reason.strip()
    epoch.reviewed_at = datetime.now(timezone.utc)
    station.representativeness_status = "passed"
    station.identity_review_status = "passed"
    station.blocked = False
    station.decision_reason = "station_epoch_reviewed"
    db.flush()
