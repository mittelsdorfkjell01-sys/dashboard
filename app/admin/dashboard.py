"""Read-side aggregation for the admin dashboard (Sprint B).

Pure query helpers over existing tables — no new state. The endpoints in
``app.api.admin`` expose these; the numbers here also feed ``/admin/overview``.
Kept deliberately additive so Sprint C/D can fold in review-queue counts.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, defer

from app.admin.readiness import build_checklist
from app.models import Era5Job, Region, RequiredField, Spot, SpotAudit
from app.names import normalize_name

logger = logging.getLogger(__name__)

_SORTS = {
    "name": Spot.name.asc(),
    "-name": Spot.name.desc(),
    "updated": Spot.updated_at.asc(),
    "-updated": Spot.updated_at.desc(),
    "confidence": Spot.confidence.asc().nullslast(),
    "-confidence": Spot.confidence.desc().nullslast(),
    "status": Spot.status.asc(),
}


def _spot_filters(stmt, *, status, region_id, sport, q, exclude_status=None):
    if status:
        stmt = stmt.where(Spot.status == status)
    if exclude_status:
        stmt = stmt.where(Spot.status != exclude_status)
    if region_id is not None:
        stmt = stmt.where(Spot.region_id == region_id)
    if sport:
        stmt = stmt.where(Spot.sports.any(sport))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Spot.name.ilike(like), Spot.slug.ilike(like)))
    return stmt


def list_spots(
    db: Session,
    *,
    status: str | None = None,
    region_id: uuid.UUID | None = None,
    sport: str | None = None,
    q: str | None = None,
    sort: str = "name",
    limit: int = 50,
    offset: int = 0,
    exclude_status: str | None = None,
    completeness: str | None = None,
) -> tuple[list[Spot], int, dict[uuid.UUID, dict]]:
    """Filtered, sorted spot page plus readiness from the canonical rules."""
    base = _spot_filters(
        select(Spot), status=status, region_id=region_id, sport=sport, q=q,
        exclude_status=exclude_status,
    )
    ordered = base.order_by(_SORTS.get(sort, Spot.name.asc()))

    if completeness:
        candidates = list(db.scalars(ordered).all())
        readiness = readiness_for_spots(db, candidates)
        expected = completeness == "complete"
        candidates = [s for s in candidates if readiness[s.id]["ready"] is expected]
        total = len(candidates)
        rows = candidates[offset:offset + limit]
        return rows, total, {s.id: readiness[s.id] for s in rows}

    total = db.scalar(
        _spot_filters(
            select(func.count()).select_from(Spot), status=status,
            region_id=region_id, sport=sport, q=q, exclude_status=exclude_status,
        )
    )
    rows = list(db.scalars(ordered.limit(limit).offset(offset)).all())
    return rows, int(total or 0), readiness_for_spots(db, rows)


def _status_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Spot.status, func.count()).group_by(Spot.status)
    ).all()
    counts = {s: int(n) for s, n in rows}
    for key in ("draft", "published", "archived"):
        counts.setdefault(key, 0)
    counts["total"] = sum(int(n) for _, n in rows)
    return counts


def list_regions_with_counts(db: Session, *, q: str | None = None) -> list[dict[str, Any]]:
    """Regions ordered by name, each with per-status spot counts."""
    count_rows = db.execute(
        select(Spot.region_id, Spot.status, func.count())
        .group_by(Spot.region_id, Spot.status)
    ).all()
    by_region: dict[uuid.UUID, dict[str, int]] = {}
    for region_id, status, n in count_rows:
        bucket = by_region.setdefault(
            region_id, {"draft": 0, "published": 0, "archived": 0, "total": 0}
        )
        bucket[status] = bucket.get(status, 0) + int(n)
        bucket["total"] += int(n)

    region_stmt = select(Region)
    if q and q.strip():
        normalized = normalize_name(q)
        like = f"%{q.strip()}%"
        region_stmt = region_stmt.where(
            or_(Region.normalized_name.contains(normalized), Region.country.ilike(like))
        )
    regions = db.scalars(region_stmt.order_by(Region.name)).all()
    out: list[dict[str, Any]] = []
    for r in regions:
        out.append(
            {
                "region": r,
                "spot_counts": by_region.get(
                    r.id, {"draft": 0, "published": 0, "archived": 0, "total": 0}
                ),
            }
        )
    return out


def _latest_job_status_map(
    db: Session, spot_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, str]:
    """spot_id → status of its most recent ERA5 job (Postgres DISTINCT ON)."""
    stmt = (
        select(Era5Job.spot_id, Era5Job.status)
        .order_by(Era5Job.spot_id, Era5Job.created_at.desc())
        .distinct(Era5Job.spot_id)
    )
    if spot_ids is not None:
        if not spot_ids:
            return {}
        stmt = stmt.where(Era5Job.spot_id.in_(spot_ids))
    return {sid: status for sid, status in db.execute(stmt).all()}


def _required_rules(db: Session) -> list[dict]:
    return [
        {"entity": r.entity, "field": r.field, "applies_when": r.applies_when,
         "severity": r.severity}
        for r in db.scalars(
            select(RequiredField).where(RequiredField.entity == "spot")
        ).all()
    ]


def not_live_gaps(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    """Non-published spots that are not yet ready, with their missing fields."""
    rules = _required_rules(db)
    jobs = _latest_job_status_map(db)
    spots = db.scalars(
        select(Spot).where(Spot.status != "published").order_by(Spot.updated_at.desc())
    ).all()
    out: list[dict[str, Any]] = []
    for s in spots:
        try:
            result = build_checklist(s, rules, job_status=jobs.get(s.id))
        except Exception:
            logger.exception("not_live_gaps: skipping spot %s", getattr(s, "id", None))
            continue
        if not result["ready"]:
            out.append(
                {
                    "id": str(s.id),
                    "name": s.name,
                    "slug": s.slug,
                    "status": s.status,
                    "region_id": str(s.region_id),
                    "gaps": result["gaps"],
                }
            )
        if len(out) >= limit:
            break
    return out


def draft_spots(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    """Draft spots (the 'Entwürfe' column), each with its readiness gaps.

    Incomplete uploads are saved as drafts (create_spot never blocks on missing
    parts), so this is the draft pipeline — every entry carries its open points
    (``gaps``) so the dashboard can show 'x offene Punkte' per draft and link
    straight into the editor to complete it later."""
    rules = _required_rules(db)
    jobs = _latest_job_status_map(db)
    spots = db.scalars(
        select(Spot)
        .where(Spot.status == "draft")
        .order_by(Spot.updated_at.desc())
        .limit(limit)
    ).all()
    out: list[dict[str, Any]] = []
    for s in spots:
        try:
            result = build_checklist(s, rules, job_status=jobs.get(s.id))
        except Exception:
            logger.exception("draft_spots: skipping spot %s", getattr(s, "id", None))
            continue
        out.append(
            {
                "id": str(s.id),
                "name": s.name,
                "slug": s.slug,
                "status": s.status,
                "region_id": str(s.region_id),
                "gaps": result["gaps"],
                "ready": result["ready"],
                "updated_at": s.updated_at.isoformat(),
            }
        )
    return out


_AUDIT_NOISE = {"auto", "from", "to"}


def _latest_audit_map(db: Session, spot_ids: list) -> dict:
    """spot_id → its most recent audit entry (Postgres DISTINCT ON)."""
    if not spot_ids:
        return {}
    stmt = (
        select(SpotAudit.spot_id, SpotAudit.action, SpotAudit.changes, SpotAudit.created_at)
        .where(SpotAudit.spot_id.in_(spot_ids))
        .order_by(SpotAudit.spot_id, SpotAudit.created_at.desc())
        .distinct(SpotAudit.spot_id)
    )
    out: dict = {}
    for spot_id, action, changes, created_at in db.execute(stmt).all():
        fields: list[str] = []
        if isinstance(changes, dict):
            if "field" in changes and isinstance(changes["field"], str):
                fields = [changes["field"]]
            else:
                fields = [k for k in changes.keys() if k not in _AUDIT_NOISE]
        out[spot_id] = {
            "action": action,
            "fields": fields,
            "at": created_at.isoformat() if created_at else None,
        }
    return out


def recent_spots(db: Session, *, limit: int = 8) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Spot)
        .options(
            defer(Spot.climatology), defer(Spot.editorial),
            defer(Spot.overrides), defer(Spot.era5_cell),
        )
        .order_by(Spot.updated_at.desc())
        .limit(limit)
    ).all()
    audits = _latest_audit_map(db, [s.id for s in rows])
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "slug": s.slug,
            "status": s.status,
            "region_id": str(s.region_id),
            "confidence": s.confidence,
            "updated_at": s.updated_at.isoformat(),
            "last_change": audits.get(s.id),
        }
        for s in rows
    ]


def ranked_spots(db: Session, *, limit: int | None = 500) -> list[dict[str, Any]]:
    """Every spot with its "Fertigstellen" traffic-light rank.

    The whole catalogue is being reworked, so this lists ALL spots (not just the
    unfinished ones) with their readiness gaps and rank — a manual override
    (``finish_rank``) wins over the automatic value. Ordered worst-first
    (red → yellow → green) so the spots needing attention surface at the top."""
    from app.admin.rank import auto_rank, effective_rank

    rules = _required_rules(db)
    jobs = _latest_job_status_map(db)
    spots = db.scalars(select(Spot).order_by(Spot.name)).all()
    out: list[dict[str, Any]] = []
    for s in spots:
        # One spot with malformed data (bad facilities/image shape) must never
        # 500 the whole Übersicht — skip and log it so the rest still loads.
        try:
            result = build_checklist(s, rules, job_status=jobs.get(s.id))
            gaps = result["gaps"]
            out.append(
                {
                    "id": str(s.id),
                    "name": s.name,
                    "slug": s.slug,
                    "status": s.status,
                    "region_id": str(s.region_id) if s.region_id else None,
                    "gaps": gaps,
                    "ready": result["ready"],
                    "rank": effective_rank(gaps, s.finish_rank),
                    "rank_auto": auto_rank(gaps),
                    "finish_rank": s.finish_rank,
                    "updated_at": s.updated_at.isoformat(),
                }
            )
        except Exception:
            logger.exception(
                "ranked_spots: skipping spot %s (%s)",
                getattr(s, "id", None),
                getattr(s, "slug", None),
            )
    order = {"red": 0, "yellow": 1, "green": 2}
    out.sort(key=lambda r: (order.get(r["rank"], 3), r["name"].lower()))
    return out[:limit] if limit is not None else out


def map_spots(
    db: Session,
    *,
    bounds: tuple[float, float, float, float] | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Return lightweight map records, optionally limited to a viewport.

    Heavy JSONB columns are never loaded; spots without coordinates are skipped.
    """
    from geoalchemy2 import Geometry

    point = Spot.location.cast(Geometry(geometry_type="POINT", srid=4326))
    stmt = select(
        Spot.id, Spot.name, Spot.status, func.ST_Y(point), func.ST_X(point)
    ).where(Spot.location.is_not(None))
    if bounds is not None:
        west, south, east, north = bounds
        envelope = func.ST_MakeEnvelope(west, south, east, north, 4326)
        stmt = stmt.where(func.ST_Intersects(point, envelope))
    rows = db.execute(stmt.order_by(Spot.id).limit(limit)).all()
    return [
        {"id": str(spot_id), "name": name, "status": status, "lat": lat, "lon": lon}
        for spot_id, name, status, lat, lon in rows
    ]


def readiness_for_spots(db: Session, spots: list[Spot]) -> dict[uuid.UUID, dict]:
    """Batch readiness without per-spot queries; always delegates to build_checklist."""
    rules = _required_rules(db)
    jobs = _latest_job_status_map(db, [spot.id for spot in spots])
    return {
        spot.id: build_checklist(spot, rules, job_status=jobs.get(spot.id))
        for spot in spots
    }


def no_region_spots(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    """Region-less spots (dragged out of every region). Surfaced at the top of
    the Übersicht (red) until a region is assigned."""
    rows = db.scalars(
        select(Spot)
        .where(Spot.region_id.is_(None))
        .order_by(Spot.updated_at.desc())
        .limit(limit)
    ).all()
    return [{"id": str(s.id), "name": s.name, "slug": s.slug, "status": s.status} for s in rows]


def overview(db: Session) -> dict[str, Any]:
    """Dashboard KPIs, including the moderation review-queue counts + team notes."""
    from app.admin.era5_worker import count_missing, count_queued
    from app.admin.moderation import review_counts
    from app.admin.team import list_notes

    spots = _status_counts(db)
    regions_count = int(db.scalar(select(func.count()).select_from(Region)) or 0)
    ranked = ranked_spots(db, limit=None)
    not_live = [r for r in ranked if r["status"] != "published" and not r["ready"]]
    drafts = sorted(
        (r for r in ranked if r["status"] == "draft"),
        key=lambda row: row["updated_at"],
        reverse=True,
    )[:100]
    return {
        "spots": spots,
        "regions": regions_count,
        "readiness_open": len(not_live),
        "not_live": not_live[:20],
        # Fertigstellen: every spot, ranked; the count is how many aren't green.
        "finish": ranked,
        "finish_open": sum(1 for r in ranked if r["rank"] != "green"),
        "no_region": no_region_spots(db),
        "drafts": drafts,
        "recent": recent_spots(db),
        "review": review_counts(db),
        "team_notes": list_notes(db, limit=12),
        "era5_queued": count_queued(db),
        "climatology_missing": count_missing(db),
    }
