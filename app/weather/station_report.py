"""Low-cardinality local station coverage and readiness report."""

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import (
    WeatherObservation, WeatherObservationImportState, WeatherStation,
    WeatherStationApprovalAudit, WeatherStationDossier, WeatherStationEpoch,
    WeatherProviderHttpResource, WeatherStationCaptureCycle,
    WeatherStationCatalogState, WeatherStationGroupDecision,
    WeatherStationMetadataRevision,
    WeatherStationProviderCursor,
)
from app.weather.station_identity import (
    duplicate_station_groups, possible_duplicate_candidates, spatial_duplicate_candidates,
)


def station_report(db, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    stations = db.scalars(select(WeatherStation).order_by(WeatherStation.provider, WeatherStation.provider_station_id)).all()
    by_id = {item.id: item for item in stations}
    observations = db.scalars(select(WeatherObservation).where(
        WeatherObservation.observed_at >= now - timedelta(days=1))).all()
    states = db.scalars(select(WeatherObservationImportState)).all()
    epochs = db.scalars(select(WeatherStationEpoch)).all()
    metadata_revisions = db.scalars(select(WeatherStationMetadataRevision)).all()
    dossiers = db.scalars(select(WeatherStationDossier)).all()
    group_decisions = db.scalars(select(WeatherStationGroupDecision)).all()
    approvals = db.scalars(select(WeatherStationApprovalAudit)).all()
    cursors = db.scalars(select(WeatherStationProviderCursor)).all()
    catalog_states = db.scalars(select(WeatherStationCatalogState)).all()
    resources = db.scalars(select(WeatherProviderHttpResource)).all()
    cycles = db.scalars(select(WeatherStationCaptureCycle).where(
        WeatherStationCaptureCycle.started_at >= now - timedelta(days=1)
    )).all()
    groups = duplicate_station_groups(stations)
    candidates = spatial_duplicate_candidates(stations)
    current_epoch_ids = {item.current_epoch_id for item in stations if item.current_epoch_id}
    current_dossiers = [item for item in dossiers if item.epoch_id in current_epoch_ids]
    countries = Counter((item.country_code or "unknown", item.provider) for item in stations)
    active_countries = Counter((item.country_code or "unknown", item.provider)
                               for item in stations if item.active)
    qc = Counter(str(reason) for item in observations for reason in (item.qc_flags or []))
    first_capture, last_capture, operational_total = db.execute(select(
        func.min(WeatherObservation.first_seen_at),
        func.max(WeatherObservation.first_seen_at),
        func.count(WeatherObservation.id),
    ).where(
        WeatherObservation.availability_class == "captured_operationally",
        WeatherObservation.first_seen_at.is_not(None),
    )).one()
    current_dossier_by_epoch = {
        item.epoch_id: item for item in sorted(dossiers, key=lambda row: row.generated_at)
        if item.epoch_id in current_epoch_ids
    }
    epochs_by_id = {item.id: item for item in epochs}
    metadata_revisions_by_id = {item.id: item for item in metadata_revisions}
    epoch_count_by_station = Counter(item.station_id for item in epochs)
    group_history_by_epoch: dict = {}
    for decision in group_decisions:
        group_history_by_epoch.setdefault(decision.epoch_id, []).append(decision)
    candidate_pairs = possible_duplicate_candidates(stations)
    identity_hints = Counter()
    identity_evidence: dict[int, list[dict]] = {index: [] for index in range(len(stations))}
    for left, right, _reasons in candidate_pairs:
        identity_hints[left] += 1
        identity_hints[right] += 1
        for index, counterpart in ((left, right), (right, left)):
            other = stations[counterpart]
            identity_evidence[index].append({
                "station_id": str(other.id),
                "identity": f"{other.provider}:{other.provider_station_id}",
                "cross_provider": stations[index].provider != other.provider,
                "reasons": list(_reasons),
            })
    review_queue = []
    for index, station in enumerate(stations):
        dossier = current_dossier_by_epoch.get(station.current_epoch_id)
        epoch = epochs_by_id.get(station.current_epoch_id)
        metadata_revision = (
            metadata_revisions_by_id.get(epoch.metadata_revision_id) if epoch else None
        )
        epoch_measurement_height = (
            epoch.configuration.get("measurement_height_m") if epoch else None
        )
        blockers = ((dossier.payload.get("decision") or {}).get("blockers", [])
                    if dossier else ["current_dossier_missing"])
        statistics = (dossier.payload.get("statistics") or {}) if dossier else {}
        operational = statistics.get("operational") or {}
        first_observed = operational.get("first_observed_at")
        last_observed = operational.get("last_observed_at")
        try:
            first_value = datetime.fromisoformat(str(first_observed))
            last_value = datetime.fromisoformat(str(last_observed))
            elapsed_days = max(
                0.0, round((last_value - first_value).total_seconds() / 86400, 2)
            )
        except (TypeError, ValueError):
            elapsed_days = 0.0
        current_group_history = sorted(
            group_history_by_epoch.get(station.current_epoch_id, []),
            key=lambda row: (row.decided_at, str(row.id)),
        )
        latest_groups = {}
        for decision in current_group_history:
            latest_groups[decision.group_type] = decision
        open_questions = []
        if identity_evidence[index]:
            open_questions.append("confirm_or_reject_possible_duplicate_relationships")
        if not station.physical_station_group:
            open_questions.append("confirm_physical_station_identity")
        if not station.correlation_group:
            open_questions.append("confirm_correlation_group_independence")
        if station.measurement_height_m is None:
            open_questions.append("obtain_official_individual_wind_measurement_height")
        if epoch is None or epoch.status != "reviewed":
            open_questions.append("review_current_station_epoch_and_metadata_changes")
        if dossier is None:
            open_questions.append("generate_current_epoch_dossier")
        proposed_roles = []
        if station.active and dossier and dossier.ready_for_review:
            proposed_roles.append("monitoring")
        strict_role_candidate = bool(
            epoch_measurement_height is not None
            and epoch is not None
            and epoch.status == "reviewed"
            and station.identity_review_status == "passed"
            and station.physical_station_group
            and station.correlation_group
            and not identity_evidence[index]
            and dossier
            and dossier.ready_for_review
        )
        if strict_role_candidate:
            proposed_roles.extend(("residual_source", "holdout_input", "holdout_target"))
        review_queue.append({
            "priority": (
                1 if station.active and dossier else
                2 if station.active else 3
            ),
            "station_id": str(station.id),
            "identity": f"{station.provider}:{station.provider_station_id}",
            "provider": station.provider,
            "current_epoch_id": (
                str(station.current_epoch_id) if station.current_epoch_id else None
            ),
            "dossier_hash": dossier.dossier_hash if dossier else None,
            "ready_for_review": bool(dossier and dossier.ready_for_review),
            "measurement_height_known": epoch_measurement_height is not None,
            "measurement_height_m": epoch_measurement_height,
            "measurement_height_evidence": {
                "source_url": (
                    metadata_revision.source_url if metadata_revision else None
                ),
                "metadata_payload_hash": (
                    metadata_revision.payload_hash if metadata_revision else None
                ),
                "metadata_revision_id": (
                    str(epoch.metadata_revision_id)
                    if epoch and epoch.metadata_revision_id else None
                ),
                "status": (
                    "official_source_linked"
                    if epoch_measurement_height is not None
                    and metadata_revision is not None
                    and metadata_revision.source_url
                    else "unproven_or_unknown"
                ),
            },
            "identity_candidate_links": identity_hints[index],
            "identity_evidence": identity_evidence[index],
            "physical_group": station.physical_station_group,
            "correlation_group": station.correlation_group,
            "group_evidence": [
                {
                    "type": kind,
                    "key": decision.group_key,
                    "status": decision.status,
                    "rule_version": decision.rule_version,
                    "evidence": decision.evidence,
                    "reviewer": decision.actor,
                    "reason": decision.reason,
                    "decided_at": decision.decided_at.isoformat(),
                }
                for kind, decision in sorted(latest_groups.items())
            ],
            "epoch": {
                "number": epoch.epoch_number if epoch else None,
                "status": epoch.status if epoch else "missing",
                "configuration_hash": epoch.configuration_hash if epoch else None,
                "first_seen_at": epoch.first_seen_at.isoformat() if epoch else None,
                "metadata_revision_id": (
                    str(epoch.metadata_revision_id)
                    if epoch and epoch.metadata_revision_id else None
                ),
                "known_epochs_for_station": epoch_count_by_station[station.id],
            },
            "source_url": station.source_url,
            "license": station.license,
            "blockers": blockers,
            "open_questions": open_questions,
            "proposed_roles_for_human_review": proposed_roles,
            "role_proposal_is_approval": False,
            "operational_quality": operational if dossier else None,
            "operational_elapsed_days": elapsed_days,
            "remaining_days_to_unapproved_28_day_proposal": max(
                0.0, round(28 - elapsed_days, 2)
            ),
        })
    return {
        "generated_at": now.isoformat(),
        "continuous_capture": {
            "first_operational_capture_at": (
                first_capture.isoformat() if first_capture else None
            ),
            "last_operational_capture_at": (
                last_capture.isoformat() if last_capture else None
            ),
            "operational_observations_total": operational_total,
            "cycles_24h": {
                f"{job_type}:{provider}:{status}": count
                for (job_type, provider, status), count in sorted(Counter(
                    (item.job_type, item.provider, item.status) for item in cycles
                ).items())
            },
        },
        "station_records_by_country_provider": [
            {"country": country, "provider": provider, "count": count}
            for (country, provider), count in sorted(countries.items())
        ],
        "active_by_country_provider": [
            {"country": country, "provider": provider, "count": count}
            for (country, provider), count in sorted(active_countries.items())
        ],
        "station_records": len(stations),
        "station_epochs": len(epochs),
        "current_epochs": sum(item.current_epoch_id is not None for item in stations),
        "pending_epoch_review": sum(item.status == "pending_review" for item in epochs),
        "dossiers": len(dossiers),
        "current_epoch_dossiers": len(current_dossiers),
        "dossiers_ready_for_review": sum(item.ready_for_review for item in current_dossiers),
        "dossiers_with_blockers": sum(bool((item.payload.get("decision") or {}).get("blockers")) for item in current_dossiers),
        "group_proposals_unreviewed": sum(item.status == "proposed" for item in group_decisions),
        "group_decisions_confirmed": sum(item.status == "confirmed" for item in group_decisions),
        "approval_decisions_by_scope": dict(sorted(Counter(item.scope for item in approvals if item.approved).items())),
        "approval_revocations": sum(not item.approved for item in approvals),
        "operational_observations_24h": sum(item.availability_class == "captured_operationally" for item in observations),
        "historical_backfill_observations_24h": sum(item.availability_class == "historical_backfill" for item in observations),
        "availability_unproven_observations_24h": sum(item.availability_class == "availability_unproven" for item in observations),
        "potential_holdout_target_gap_to_10": max(0, 10 - len({item.correlation_group for item in stations
            if item.holdout_target_approved and item.identity_review_status == "passed"
            and item.correlation_group})),
        "provider_cursors": {item.provider: {"paused": item.paused,
                                             "watermark_at": item.watermark_at.isoformat() if item.watermark_at else None,
                                             "last_cycle_at": item.last_cycle_at.isoformat() if item.last_cycle_at else None,
                                             "last_success_at": item.last_success_at.isoformat() if item.last_success_at else None,
                                             "last_error_class": item.last_error_class}
                             for item in cursors},
        "catalogs": {
            item.provider: {
                "last_attempt_at": item.last_attempt_at.isoformat()
                if item.last_attempt_at else None,
                "last_success_at": item.last_success_at.isoformat()
                if item.last_success_at else None,
                "age_hours": round((now - item.last_success_at).total_seconds() / 3600, 2)
                if item.last_success_at else None,
                "next_attempt_at": item.next_attempt_at.isoformat()
                if item.next_attempt_at else None,
                "last_error_class": item.last_error_class,
                "consecutive_failures": item.consecutive_failures,
                "last_counts": item.last_counts,
            }
            for item in catalog_states
        },
        "dwd_http_validators": {
            "resources": sum(item.provider == "dwd" for item in resources),
            "with_etag": sum(item.provider == "dwd" and bool(item.etag)
                             for item in resources),
            "with_last_modified": sum(
                item.provider == "dwd" and bool(item.last_modified)
                for item in resources
            ),
            "last_checked_at": max(
                (item.last_checked_at for item in resources if item.provider == "dwd"),
                default=None,
            ).isoformat() if any(item.provider == "dwd" for item in resources) else None,
            "not_modified_resources": sum(
                item.provider == "dwd" and item.last_status_code == 304
                for item in resources
            ),
        },
        "physical_station_upper_bound_after_confirmed_merge": len(stations) - sum(len(group) - 1 for group in groups),
        "physical_station_count_verified": (
            len(stations) - sum(len(group) - 1 for group in groups)
            if all(item.identity_review_status == "passed" for item in stations) else None
        ),
        "confirmed_duplicate_groups": len(groups),
        "spatial_duplicate_candidates": len(candidates),
        "identity_candidate_pairs": len(possible_duplicate_candidates(stations)),
        "station_review_queue": sorted(
            review_queue,
            key=lambda item: (
                item["priority"], not item["ready_for_review"],
                item["provider"], item["identity"],
            ),
        ),
        "independent_reviewed_groups": len({item.correlation_group for item in stations
                                             if item.identity_review_status == "passed" and item.correlation_group}),
        "independent_holdout_target_groups": len({
            item.correlation_group for item in stations
            if item.holdout_target_approved and item.identity_review_status == "passed"
            and item.correlation_group
        }),
        "independent_holdout_input_groups": len({
            item.correlation_group for item in stations
            if item.holdout_input_approved and item.identity_review_status == "passed"
            and item.correlation_group
        }),
        "active_station_records": sum(bool(item.active) for item in stations),
        "monitoring_approved": sum(bool(item.monitoring_approved) for item in stations),
        "residual_approved": sum(bool(item.residual_approved) for item in stations),
        "holdout_target_approved": sum(bool(item.holdout_target_approved) for item in stations),
        "holdout_input_approved": sum(bool(item.holdout_input_approved) for item in stations),
        "missing_station_elevation": sum(item.elevation_m is None for item in stations),
        "unknown_measurement_height": sum(item.measurement_height_m is None for item in stations),
        "known_measurement_height": sum(item.measurement_height_m is not None for item in stations),
        "unknown_license": sum(not item.license for item in stations),
        "licenses_by_provider": [
            {"provider": provider, "license": license_name, "stations": count}
            for (provider, license_name), count in sorted(Counter(
                (item.provider, item.license or "unknown") for item in stations
            ).items())
        ],
        "attribution_required_station_records": sum(
            bool((item.provenance or {}).get("attribution_required")) for item in stations
        ),
        "observations_24h": len(observations),
        "unknown_received_at_24h": sum(item.received_at is None for item in observations),
        "qc_reasons_24h": dict(sorted(qc.items())),
        "expected_residual_yield_24h": sum(
            item.import_status == "accepted" and item.qc_version == "station-observation-qc-v1"
            and item.qc_stage in {"eligible_for_residuals", "eligible_for_holdout"}
            and not item.qc_flags and item.wind_u_ms is not None and item.wind_v_ms is not None
            and bool(getattr(by_id.get(item.station_id), "residual_approved", False))
            for item in observations
        ),
        "providers": {
            provider: {
                "last_success_at": max((state.last_success_at for state in states
                                        if state.provider == provider and state.last_success_at), default=None).isoformat()
                if any(state.provider == provider and state.last_success_at for state in states) else None,
                "error_stations": sum(state.provider == provider and state.status == "error" for state in states),
                "latest_observation_age_minutes": (
                    lambda latest: round((now - latest).total_seconds() / 60, 1) if latest else None
                )(max((item.last_observation_at for item in stations
                       if item.provider == provider and item.last_observation_at), default=None)),
                "receipt_delay_minutes_p50_24h_window": (
                    lambda delays: sorted(delays)[len(delays) // 2] if delays else None
                )([round((item.received_at - item.observed_at).total_seconds() / 60, 1)
                   for item in observations if item.received_at and
                   getattr(by_id.get(item.station_id), "provider", None) == provider]),
            }
            for provider in sorted({item.provider for item in stations} | {item.provider for item in states})
        },
    }
