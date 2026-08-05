"""Indexed text search over the published spot and region catalogue."""

from __future__ import annotations

import unicodedata
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

# Match quality scores (higher = better).
_EXACT = 4.0
_ALIAS_EXACT = 3.0
_PREFIX = 2.0
_SUBSTRING = 1.0


def normalize(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def _aliases(entity: Any) -> list[str]:
    for attr in ("editorial", "defaults"):
        blob = getattr(entity, attr, None)
        if isinstance(blob, dict):
            vals = blob.get("aliases")
            if isinstance(vals, list):
                return [str(v) for v in vals]
    return []


def _fields(entity: Any) -> dict[str, list[str]]:
    names = [getattr(entity, "name", "") or ""]
    aliases = _aliases(entity)
    extra = [
        getattr(entity, "slug", "") or "",
        getattr(entity, "country", "") or "",
    ]
    return {
        "name": [normalize(n) for n in names if n],
        "alias": [normalize(a) for a in aliases if a],
        "extra": [normalize(e) for e in extra if e],
    }


def _match_score(query_n: str, fields: dict[str, list[str]]) -> float | None:
    best = 0.0
    for name in fields["name"]:
        if name == query_n:
            best = max(best, _EXACT)
        elif name.startswith(query_n):
            best = max(best, _PREFIX)
        elif query_n in name:
            best = max(best, _SUBSTRING)
    for alias in fields["alias"]:
        if alias == query_n:
            best = max(best, _ALIAS_EXACT)
        elif query_n in alias:
            best = max(best, _SUBSTRING)
    for extra in fields["extra"]:
        if extra == query_n or query_n in extra:
            best = max(best, _SUBSTRING)
    return best or None


def match_entities(
    query: str, spots: list[Any], regions: list[Any]
) -> dict[str, list[Any]]:
    """Pure matcher: return ``{"regionen": [...], "spots": [...]}`` ranked."""
    query_n = normalize(query)
    if not query_n:
        return {"regionen": [], "spots": []}

    def _ranked(entities: list[Any]) -> list[Any]:
        scored = []
        for e in entities:
            s = _match_score(query_n, _fields(e))
            if s is not None:
                scored.append((s, getattr(e, "name", ""), e))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [e for _, _, e in scored]

    return {"regionen": _ranked(regions), "spots": _ranked(spots)}


def search_entities(query: str, *, db: Session) -> dict[str, list[Any]]:
    """Trigram-ranked search with hard limits and a mandatory published scope."""
    from app.models import Region, Spot
    from app.public_catalog import PUBLISHED

    query_n = normalize(query)
    if not query_n:
        return {"regionen": [], "spots": []}

    def _query(model, extra_columns):
        similarity = func.similarity(model.normalized_name, query_n)
        exact_rank = case(
            (model.normalized_name == query_n, 4.0),
            (model.normalized_name.startswith(query_n), 2.0),
            else_=similarity,
        )
        filters = [
            model.normalized_name.op("%") (query_n),
            model.normalized_name.startswith(query_n),
            model.slug.ilike(f"%{query_n}%"),
        ]
        filters.extend(column.ilike(f"%{query_n}%") for column in extra_columns)
        stmt = (
            select(model)
            .where(model.status == PUBLISHED, or_(*filters))
            .order_by(exact_rank.desc(), model.name.asc())
            .limit(20)
        )
        return list(db.scalars(stmt).all())

    spots = _query(Spot, [])
    regions = _query(Region, [Region.country])
    return {"regionen": regions, "spots": spots}
