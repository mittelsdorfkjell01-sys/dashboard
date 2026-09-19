"""Audited, epoch- and dossier-bound manual station-scope decisions.

The importer never calls this module. Unconfigured policy is fail-closed.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import AdminUser, WeatherStationApprovalAudit, WeatherStationDossier, WeatherStationEpoch
from app.weather.station_qualification import QualificationPolicy, current_group_decisions, group_version

SCOPES = {
    "monitoring": "monitoring_approved",
    "residual_source": "residual_approved",
    "holdout_target": "holdout_target_approved",
    "holdout_input": "holdout_input_approved",
}


def _scope(scope: str) -> str:
    return "residual_source" if scope == "residual" else scope


def latest_dossier(db, epoch_id):
    return db.scalar(select(WeatherStationDossier).where(
        WeatherStationDossier.epoch_id == epoch_id
    ).order_by(WeatherStationDossier.generated_at.desc(), WeatherStationDossier.id.desc()))


def _latest_decision(db, epoch_id, scope):
    return db.scalar(select(WeatherStationApprovalAudit).where(
        WeatherStationApprovalAudit.epoch_id == epoch_id,
        WeatherStationApprovalAudit.scope == scope,
    ).order_by(WeatherStationApprovalAudit.decided_at.desc(), WeatherStationApprovalAudit.id.desc()))


def approval_reasons(db, station, *, scope: str,
                     policy: QualificationPolicy | None = None) -> list[str]:
    scope = _scope(scope)
    if scope not in SCOPES:
        return ["scope_invalid"]
    policy = policy or QualificationPolicy()
    reasons = []
    epoch = db.get(WeatherStationEpoch, station.current_epoch_id) if station.current_epoch_id else None
    if epoch is None or epoch.station_id != station.id or epoch.status != "reviewed":
        reasons.append("epoch_unreviewed")
    if not station.active or station.blocked or station.representativeness_status != "passed":
        reasons.append("station_not_representative")
    if station.license != "CC BY 4.0" or station.elevation_m is None:
        reasons.append("station_metadata_incomplete")
    if not policy.configured:
        reasons.append("qualification_policy_unconfigured")
    if epoch is None:
        return reasons
    if epoch.configuration.get("measurement_height_m") is None and (
        scope != "monitoring" or policy.allow_unknown_measurement_height is not True
    ):
        reasons.append("measurement_height_unknown")
    if group_version(current_group_decisions(db, epoch.id)) is None:
        reasons.append("dependency_group_unreviewed")
    dossier = latest_dossier(db, epoch.id)
    if dossier is None or not dossier.ready_for_review:
        reasons.append("review_dossier_missing")
        return reasons
    operational = dossier.payload["statistics"]["operational"]
    if policy.configured:
        first = operational["first_observed_at"]
        last = operational["last_observed_at"]
        if not first or not last or (datetime.fromisoformat(last) - datetime.fromisoformat(first)).days < policy.min_operational_days:
            reasons.append("operational_duration_insufficient")
        if operational["completeness"] is None or operational["completeness"] < policy.min_completeness:
            reasons.append("completeness_insufficient")
        p95 = operational["latency_minutes"]["p95"]
        if p95 is None or p95 > policy.max_latency_p95_minutes:
            reasons.append("latency_excessive")
        expected = operational["expected"]
        interval = dossier.payload["statistics"]["interval_minutes"]
        if expected is None or interval is None or operational["outage_duration_minutes"] is None or (
            operational["outage_duration_minutes"] / (expected * interval) > policy.max_outage_share
        ):
            reasons.append("outage_share_excessive")
        if operational["qc_acceptance_share"] is None or (
            1 - operational["qc_acceptance_share"] > policy.max_qc_exclusion_share
        ):
            reasons.append("qc_exclusion_share_excessive")
    if scope != "monitoring" and not station.monitoring_approved:
        reasons.append("monitoring_approval_required")
    return reasons


def decide_station_scope(db, station, *, scope: str, approved: bool,
                         actor: str, reason: str, reviewer: AdminUser | None = None,
                         policy: QualificationPolicy | None = None,
                         expires_at: datetime | None = None,
                         expected_dossier_hash: str | None = None) -> None:
    scope = _scope(scope)
    if scope not in SCOPES or not actor.strip() or not reason.strip():
        raise ValueError("scope_actor_reason_required")
    if reviewer is None or not reviewer.is_active or reviewer.role != "admin" or reviewer.email != actor:
        raise ValueError("authenticated_admin_reviewer_required")
    if expires_at is not None and (expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc)):
        raise ValueError("valid_future_expiry_required")
    epoch = db.get(WeatherStationEpoch, station.current_epoch_id) if station.current_epoch_id else None
    if epoch is None:
        raise ValueError("station_epoch_unavailable")
    dossier = latest_dossier(db, epoch.id)
    if approved:
        if dossier is None or expected_dossier_hash != dossier.dossier_hash:
            raise ValueError("reviewed_dossier_hash_mismatch")
        reasons = approval_reasons(db, station, scope=scope, policy=policy)
        if reasons:
            raise ValueError(";".join(reasons))
    latest = _latest_decision(db, epoch.id, scope)
    if not approved and latest is None:
        raise ValueError("approval_to_revoke_missing")
    db.add(WeatherStationApprovalAudit(
        station_id=station.id, epoch_id=epoch.id, scope=scope, approved=approved,
        actor=actor, reason=reason, dossier_hash=dossier.dossier_hash if dossier else None,
        policy_version=policy.version if policy else None,
        group_version=group_version(current_group_decisions(db, epoch.id)),
        expires_at=expires_at,
    ))
    setattr(station, SCOPES[scope], approved)
    if scope == "monitoring":
        station.approved = approved
        if not approved:
            for dependent in ("residual_source", "holdout_input", "holdout_target"):
                if getattr(station, SCOPES[dependent], False):
                    setattr(station, SCOPES[dependent], False)
                    db.add(WeatherStationApprovalAudit(
                        station_id=station.id, epoch_id=epoch.id, scope=dependent,
                        approved=False, actor=actor, reason=f"monitoring revoked: {reason}",
                        dossier_hash=dossier.dossier_hash if dossier else None,
                        policy_version=policy.version if policy else None,
                        group_version=group_version(current_group_decisions(db, epoch.id)),
                    ))
    db.flush()


def scope_valid(db, station, observation, *, scope: str,
                analyzed_at: datetime) -> bool:
    """Legacy booleans alone are insufficient evidence for model use."""
    scope = _scope(scope)
    if scope not in SCOPES or station.current_epoch_id is None:
        return False
    if not getattr(station, SCOPES[scope], False) or station.blocked or not station.active:
        return False
    if observation.epoch_id != station.current_epoch_id:
        return False
    if observation.availability_class != "captured_operationally":
        return False
    epoch = db.get(WeatherStationEpoch, station.current_epoch_id)
    if epoch is None or epoch.status != "reviewed":
        return False
    decision = _latest_decision(db, epoch.id, scope)
    if decision is None or not decision.approved or decision.decided_at > analyzed_at:
        return False
    if decision.expires_at is not None and decision.expires_at <= analyzed_at:
        return False
    if observation.observed_at < decision.decided_at:
        return False
    if scope != "monitoring" and not scope_valid(
        db, station, observation, scope="monitoring", analyzed_at=analyzed_at
    ):
        return False
    if decision.group_version != group_version(current_group_decisions(db, epoch.id)):
        return False
    dossier = db.scalar(select(WeatherStationDossier).where(
        WeatherStationDossier.epoch_id == epoch.id,
        WeatherStationDossier.dossier_hash == decision.dossier_hash,
    ))
    return dossier is not None
