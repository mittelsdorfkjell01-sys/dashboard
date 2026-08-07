"""Postgres-backed search cache and per-provider hourly request budget.

Both live in Postgres rather than Redis. ``app.live.cache`` is deliberately
fail-open (a dead cache reports a miss), which is right for forecast data and
wrong for a request budget: a counter that fails open cannot hold Unsplash's
50/hour line, and one that fails closed would take the picker down whenever
Redis hiccups. Postgres is the store every deployment mode already requires.

The cache stores the **raw provider payload**, not normalised results, so a
change to the normaliser or the size gates takes effect immediately instead of
waiting out a 24-hour TTL.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import MediaProviderBudget, MediaSearchCache


def normalize_query(query: str) -> str:
    """Fold a search query so trivially different spellings share a cache entry.

    ``"Tarifa  Kitesurf"`` and ``"tarifa kitesurf"`` must not cost two Unsplash
    requests. Accents are folded too, so ``"Peníscola"`` and ``"Peniscola"``
    hit the same entry.
    """
    folded = unicodedata.normalize("NFKD", query or "")
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", folded).strip().lower()


def cache_key(provider: str, query: str, page: int, **extra) -> str:
    """Key for one upstream call.

    Deliberately **without** ``role``: the normalised payload carries both
    ``hero_eligible`` and ``gallery_eligible``, and no adapter varies its
    upstream query by role. Keying on it would double every provider request the
    moment an operator toggles Hero/Galerie — the exact waste this cache exists
    to prevent.
    """
    parts = {"q": normalize_query(query), "page": page, **extra}
    blob = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]
    return f"{provider}:{digest}"


def cache_get(db: Session, key: str) -> list[dict] | None:
    row = db.scalar(
        select(MediaSearchCache).where(
            MediaSearchCache.cache_key == key,
            MediaSearchCache.expires_at > datetime.now(timezone.utc),
        )
    )
    if row is None:
        return None
    payload = row.payload
    return payload.get("raw") if isinstance(payload, dict) else None


def cache_put(db: Session, key: str, raw: list[dict], *, ttl: int | None = None) -> None:
    ttl = ttl if ttl is not None else get_settings().media_search_cache_ttl
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    statement = insert(MediaSearchCache).values(
        cache_key=key, payload={"raw": raw}, expires_at=expires
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[MediaSearchCache.cache_key],
            set_={"payload": statement.excluded.payload, "expires_at": statement.excluded.expires_at},
        )
    )
    db.commit()


def _hour_bucket() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(minute=0, second=0, microsecond=0)


def budget_limit(provider: str) -> int:
    """Requests per hour for ``provider``. 0 means "not budgeted"."""
    return int(get_settings().media_budget_per_hour.get(provider, 0))


def budget_used(db: Session, provider: str) -> int:
    return int(
        db.scalar(
            select(MediaProviderBudget.request_count).where(
                MediaProviderBudget.provider == provider,
                MediaProviderBudget.window_start == _hour_bucket(),
            )
        )
        or 0
    )


def budget_consume(db: Session, provider: str) -> int:
    """Record one upstream request and return the new count.

    ``INSERT … ON CONFLICT DO UPDATE`` so two concurrent serverless invocations
    cannot lose a count between a read and a write.
    """
    statement = insert(MediaProviderBudget).values(
        provider=provider, window_start=_hour_bucket(), request_count=1
    )
    row = db.execute(
        statement.on_conflict_do_update(
            index_elements=[
                MediaProviderBudget.provider,
                MediaProviderBudget.window_start,
            ],
            set_={"request_count": MediaProviderBudget.request_count + 1},
        ).returning(MediaProviderBudget.request_count)
    ).scalar_one()
    db.commit()
    return int(row)


def budget_state(db: Session, provider: str) -> dict:
    """``{used, limit, exhausted, warning}`` for the response meta."""
    limit = budget_limit(provider)
    used = budget_used(db, provider)
    ratio = get_settings().media_budget_warn_ratio
    return {
        "used": used,
        "limit": limit,
        "exhausted": bool(limit) and used >= limit,
        "warning": bool(limit) and used >= limit * ratio,
    }


def sweep_expired(db: Session, *, keep_budget_hours: int = 48) -> dict[str, int]:
    """Drop stale cache entries and old budget buckets.

    Called from the existing daily maintenance cron — this feature adds no cron
    of its own.
    """
    now = datetime.now(timezone.utc)
    cache_removed = db.execute(
        delete(MediaSearchCache).where(MediaSearchCache.expires_at <= now)
    ).rowcount
    budget_removed = db.execute(
        delete(MediaProviderBudget).where(
            MediaProviderBudget.window_start < now - timedelta(hours=keep_budget_hours)
        )
    ).rowcount
    db.commit()
    return {
        "cache_entries_removed": int(cache_removed or 0),
        "budget_rows_removed": int(budget_removed or 0),
    }


__all__ = [
    "budget_consume",
    "budget_limit",
    "budget_state",
    "budget_used",
    "cache_get",
    "cache_key",
    "cache_put",
    "normalize_query",
    "sweep_expired",
]
