"""Human-approved parameter proposal generation and activation."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable, Mapping

from sqlalchemy import select

KNOTS_PER_MS = 1.9438444924406


def _quantile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("quantile requires values")
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lo, hi = int(index), min(int(index) + 1, len(ordered) - 1)
    fraction = index - lo
    return ordered[lo] * (1 - fraction) + ordered[hi] * fraction


def default_rider_proposal(db, *, minimum_profiles: int) -> dict:
    from app.admin.constants import STYLES
    from app.models import GearItem, RiderProfile, RiderSportProfile

    rows = db.execute(
        select(RiderProfile, RiderSportProfile)
        .join(RiderSportProfile, RiderSportProfile.rider_profile_id == RiderProfile.id)
        .where(
            RiderProfile.weight_kg.is_not(None),
            RiderSportProfile.sport == "kitesurf",
        )
    ).all()
    profile_ids = [base.id for base, _sport in rows]
    gear = list(db.scalars(
        select(GearItem).where(
            GearItem.rider_profile_id.in_(profile_ids),
            GearItem.sport == "kitesurf",
            GearItem.active.is_(True),
        )
    )) if profile_ids else []
    by_profile: dict[object, list] = {}
    for item in gear:
        by_profile.setdefault(item.rider_profile_id, []).append(item)
    complete = [
        (base, sport, by_profile.get(base.id, []))
        for base, sport in rows
        if any(item.kind == "kite" and item.size is not None for item in by_profile.get(base.id, []))
        and any(item.kind in {"board", "foil"} for item in by_profile.get(base.id, []))
    ]
    if len(complete) < minimum_profiles:
        return {
            "eligible": False,
            "sample_count": len(complete),
            "minimum_profiles": minimum_profiles,
            "proposal": None,
        }
    kite_slots: list[list[float]] = []
    for _base, _sport, items in complete:
        sizes = sorted(float(item.size) for item in items if item.kind == "kite" and item.size)
        for index, size in enumerate(sizes):
            while len(kite_slots) <= index:
                kite_slots.append([])
            kite_slots[index].append(size)
    board_types = [
        item.board_type
        for _base, _sport, items in complete
        for item in items
        if item.kind in {"board", "foil"} and item.board_type
    ]
    levels = Counter(sport.level for _base, sport, _items in complete)
    modes = Counter(base.travel_mode for base, _sport, _items in complete)
    styles = {
        key: int(round(median([
            int((sport.style_weights or {}).get(key, 0))
            for _base, sport, _items in complete
        ])))
        for key in STYLES
    }
    quiver = [
        {"kind": "kite", "size": round(median(slot), 1)}
        for slot in kite_slots
        if len(slot) >= max(2, len(complete) // 4)
    ]
    quiver.append({
        "kind": "board",
        "board_type": Counter(board_types).most_common(1)[0][0] if board_types else "twintip",
    })
    return {
        "eligible": True,
        "sample_count": len(complete),
        "minimum_profiles": minimum_profiles,
        "proposal": {
            "weight_kg": round(median(float(base.weight_kg) for base, _sport, _items in complete), 1),
            "level": levels.most_common(1)[0][0],
            "quiver": quiver,
            "style_weights": styles,
            "travel_mode": modes.most_common(1)[0][0],
        },
    }


def band_factor_proposal(
    samples: Iterable[Mapping],
    current: Mapping,
    *,
    minimum_checkins: int,
) -> dict:
    rows = [row for row in samples if row.get("outcome") == "worthwhile"]
    grouped: dict[tuple[float, str], list[float]] = {}
    for row in rows:
        key = (float(row["kite_size"]), str(row.get("board_type") or "twintip"))
        grouped.setdefault(key, []).append(float(row["wind_kt"]))
    observations = [
        {
            "kite_size": kite_size,
            "board_type": board,
            "sample_count": len(winds),
            "median_wind_kt": round(median(winds), 1),
            "p10_wind_kt": round(_quantile(winds, 0.1), 1),
            "p90_wind_kt": round(_quantile(winds, 0.9), 1),
        }
        for (kite_size, board), winds in sorted(grouped.items())
    ]
    if len(rows) < minimum_checkins:
        return {
            "eligible": False, "sample_count": len(rows),
            "minimum_checkins": minimum_checkins, "proposal": None,
            "observations": observations,
        }
    k_values: dict[str, list[float]] = {}
    ratios: list[float] = []
    for row in rows:
        weight = float(row["weight_kg"])
        size = float(row["kite_size"])
        wind = float(row["wind_kt"])
        board = str(row.get("board_type") or "twintip")
        observed_k = wind * size / weight
        k_values.setdefault(board, []).append(observed_k)
        current_k = float(current["k_board"].get(board, current["k_board"]["twintip"]))
        core = current_k * weight / size
        ratios.append(wind / core)
    proposed_k = dict(current["k_board"])
    for board, values in k_values.items():
        proposed_k[board] = round(median(values), 3)
    return {
        "eligible": True,
        "sample_count": len(rows),
        "minimum_checkins": minimum_checkins,
        "observations": observations,
        "proposal": {
            "k_board": proposed_k,
            "f_lo": round(max(0.4, min(1.2, _quantile(ratios, 0.1))), 3),
            "f_hi": round(max(1.0, min(2.0, _quantile(ratios, 0.9))), 3),
        },
    }


def checkin_band_samples(db, *, days: int = 180) -> list[dict]:
    from app.models import GearItem, RiderProfile, UserEvent, WeatherObservation, WeatherStation

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = list(db.scalars(
        select(UserEvent).where(
            UserEvent.type == "session_checkin",
            UserEvent.app_user_id.is_not(None),
            UserEvent.spot_id.is_not(None),
            UserEvent.created_at >= cutoff,
        ).order_by(UserEvent.created_at)
    ))
    latest: dict[tuple[object, object, object], object] = {}
    for event in events:
        latest[(event.app_user_id, event.spot_id, event.created_at.date())] = event
    result = []
    for event in latest.values():
        outcome = (event.context or {}).get("outcome")
        if outcome not in {"worthwhile", "not_worthwhile"}:
            continue
        profile = db.scalar(select(RiderProfile).where(RiderProfile.app_user_id == event.app_user_id))
        if profile is None or profile.weight_kg is None:
            continue
        gear = list(db.scalars(select(GearItem).where(
            GearItem.rider_profile_id == profile.id,
            GearItem.sport == "kitesurf",
            GearItem.active.is_(True),
        )))
        kites = [item for item in gear if item.kind == "kite" and item.size]
        if not kites:
            continue
        observed = db.execute(
            select(WeatherObservation.wind_speed_ms)
            .join(WeatherStation, WeatherStation.id == WeatherObservation.station_id)
            .where(
                WeatherStation.spot_id == event.spot_id,
                WeatherObservation.import_status == "accepted",
                WeatherObservation.observed_at >= event.created_at - timedelta(hours=2),
                WeatherObservation.observed_at <= event.created_at + timedelta(hours=2),
            )
            .order_by(WeatherObservation.observed_at)
        ).scalars().all()
        if not observed:
            continue
        wind = median(float(value) * KNOTS_PER_MS for value in observed)
        # The check-in intentionally asks no gear question. Infer the most
        # plausible active kite and expose that fact in the evidence.
        kite = min(kites, key=lambda item: abs(float(item.size) - (2.2 * float(profile.weight_kg) / max(wind, 1))))
        board = next((item.board_type for item in gear if item.board_type), "twintip")
        result.append({
            "outcome": outcome, "weight_kg": float(profile.weight_kg),
            "kite_size": float(kite.size), "board_type": board,
            "wind_kt": wind, "kite_inferred": True,
        })
    return result


def apply_proposal(db, proposal, *, actor: str, note: str | None = None) -> int:
    from app.models import ScoringParams

    rows = list(db.scalars(
        select(ScoringParams)
        .where(ScoringParams.sport == proposal.sport)
        .with_for_update()
    ))
    active = max((row for row in rows if row.active), key=lambda row: row.version, default=None)
    if active is None or active.version != proposal.base_params_version:
        raise ValueError("proposal base version is no longer active")
    params = deepcopy(active.params)
    if proposal.kind == "default_rider":
        params.setdefault("default_rider", {})[proposal.sport] = proposal.proposed_params
    elif proposal.kind == "personal_band":
        model = params.setdefault("rider_model", {}).setdefault(proposal.sport, {})
        model.update(proposal.proposed_params)
    elif proposal.kind == "social_weight":
        if not proposal.evidence.get("improved"):
            raise ValueError("social weight requires measured improvement")
        params.setdefault("social", {}).update(proposal.proposed_params)
        params["social"]["validated"] = True
    else:
        raise ValueError("unknown proposal kind")
    next_version = max(row.version for row in rows) + 1
    params.setdefault("parameter_log", []).append({
        "version": next_version,
        "kind": proposal.kind,
        "proposal_id": str(proposal.id),
        "approved_by": actor,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    })
    for row in rows:
        row.active = False
    db.add(ScoringParams(
        sport=proposal.sport, version=next_version, active=True, params=params
    ))
    proposal.status = "approved"
    proposal.reviewed_by = actor
    proposal.review_note = note
    proposal.reviewed_at = datetime.now(timezone.utc)
    proposal.activated_params_version = next_version
    db.commit()
    return next_version
