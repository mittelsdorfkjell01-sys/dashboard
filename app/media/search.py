"""Search orchestration for the media picker.

One provider per call, one failure domain per call: a provider that is down, out
of budget or unconfigured returns a status for its own tab and nothing else. The
overlay keeps working with the tabs that answered.

Order of operations, and why:

1. **Cache first** — a hit costs no upstream request and no budget.
2. **Budget check** — before the call, so an exhausted provider never fires one.
3. **Call, then count** — the counter tracks requests actually made.
4. **Normalise, gate, annotate** — licenses that forbid commercial use or
   modification are dropped here rather than greyed out: unlike a too-small
   photo, an operator can never make them usable.
5. **Duplicate lookup** — one query against ``media_usage`` for the whole page.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.media import budget as budget_store
from app.media.normalize import MediaResult, adoptable
from app.media.providers import NEARBY, PROVIDERS, get_provider
from app.media.providers.base import ProviderError, ProviderRequest, ProviderUnavailable
from app.media.providers import openverse as openverse_module
from app.media.providers import wikimedia as wikimedia_module
from app.models import MediaUsage, Region, Spot

# Response statuses the picker understands.
STATUS_OK = "ok"
STATUS_DISABLED = "disabled"
STATUS_EXHAUSTED = "budget_exhausted"
STATUS_ERROR = "error"

_DISABLED_HINT = {
    "unsplash": "UNSPLASH_ACCESS_KEY ist nicht konfiguriert.",
    "pexels": "PEXELS_API_KEY ist nicht konfiguriert.",
}


@dataclass
class SearchOutcome:
    provider: str
    status: str
    items: list[dict]
    total: int
    page: int
    cached: bool = False
    budget: dict | None = None
    message: str | None = None

    def as_payload(self) -> dict:
        return {
            "provider": self.provider,
            "status": self.status,
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "meta": {
                "cached": self.cached,
                "budget": self.budget,
                "message": self.message,
            },
        }


def _fetch_raw(
    db: Session, provider_key: str, adapter, request: ProviderRequest, *, nearby: bool
) -> tuple[list[dict], bool]:
    """Cached upstream payload for one adapter. Returns ``(raw, cached)``."""
    key = budget_store.cache_key(
        provider_key,
        request.query,
        request.page,
        nearby=nearby,
        lat=round(request.lat, 3) if nearby and request.lat is not None else None,
        lon=round(request.lon, 3) if nearby and request.lon is not None else None,
        radius=request.radius_km if nearby else None,
        per_page=request.per_page,
    )
    cached = budget_store.cache_get(db, key)
    if cached is not None:
        return cached, True

    state = budget_store.budget_state(db, provider_key)
    if state["exhausted"]:
        raise BudgetExhausted(provider_key, state)

    if nearby and hasattr(adapter, "search_nearby"):
        raw = adapter.search_nearby(request)
    else:
        raw = adapter.search(request)
    budget_store.budget_consume(db, provider_key)
    budget_store.cache_put(db, key, raw)
    return raw, False


class BudgetExhausted(RuntimeError):
    def __init__(self, provider: str, state: dict) -> None:
        super().__init__(f"{provider} budget exhausted")
        self.provider = provider
        self.state = state


def _usage_index(db: Session, results: list[MediaResult]) -> dict[tuple[str, str], list[dict]]:
    """Where each of these photos is already used, in one query.

    An operator seeing the same Unsplash photo on twelve spots is what destroys
    a catalogue's credibility, so this is surfaced during the search rather than
    only refused at adopt time.
    """
    keys = {(r.provider, r.external_id) for r in results if r.external_id}
    if not keys:
        return {}
    rows = db.scalars(
        select(MediaUsage).where(
            MediaUsage.provider.in_({p for p, _ in keys}),
            MediaUsage.external_id.in_({e for _, e in keys}),
        )
    ).all()
    if not rows:
        return {}

    spot_names = dict(
        db.execute(
            select(Spot.id, Spot.name).where(
                Spot.id.in_([r.entity_id for r in rows if r.entity_type == "spot"])
            )
        ).all()
    )
    region_names = dict(
        db.execute(
            select(Region.id, Region.name).where(
                Region.id.in_([r.entity_id for r in rows if r.entity_type == "region"])
            )
        ).all()
    )

    index: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        pair = (row.provider, row.external_id)
        if pair not in keys:
            continue
        names = spot_names if row.entity_type == "spot" else region_names
        index.setdefault(pair, []).append(
            {
                "entity_type": row.entity_type,
                "entity_id": str(row.entity_id),
                "name": names.get(row.entity_id) or "—",
                "role": row.role,
            }
        )
    return index


def search(
    db: Session,
    *,
    provider: str,
    query: str,
    page: int = 1,
    per_page: int = 24,
    role: str = "hero",
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 5.0,
) -> SearchOutcome:
    """Run one tab's search. Never raises for provider-side problems."""
    request = ProviderRequest(
        query=query,
        page=page,
        per_page=per_page,
        role=role,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
    )
    if provider == NEARBY:
        return _search_nearby(db, request)

    try:
        adapter = get_provider(provider)
    except ProviderError as exc:
        return SearchOutcome(provider, STATUS_ERROR, [], 0, page, message=str(exc))

    if not adapter.available():
        return SearchOutcome(
            provider,
            STATUS_DISABLED,
            [],
            0,
            page,
            message=_DISABLED_HINT.get(provider, "Zugang ist nicht konfiguriert."),
        )

    try:
        raw, cached = _fetch_raw(db, provider, adapter, request, nearby=False)
        results = adapter.parse(raw)
    except BudgetExhausted as exc:
        return SearchOutcome(
            provider,
            STATUS_EXHAUSTED,
            [],
            0,
            page,
            budget=exc.state,
            message="Stundenkontingent aufgebraucht — andere Quellen funktionieren weiter.",
        )
    except ProviderUnavailable as exc:
        return SearchOutcome(provider, STATUS_DISABLED, [], 0, page, message=str(exc))
    except ProviderError as exc:
        return SearchOutcome(
            provider,
            STATUS_ERROR,
            [],
            0,
            page,
            message=f"Quelle nicht erreichbar: {exc}",
        )

    items = _finalise(db, results)
    return SearchOutcome(
        provider,
        STATUS_OK,
        items,
        len(items),
        page,
        cached=cached,
        budget=budget_store.budget_state(db, provider),
    )


def _search_nearby(db: Session, request: ProviderRequest) -> SearchOutcome:
    """Cross-provider coordinate search.

    Commons geosearch gives genuinely coordinate-verified hits; Openverse has no
    radius search, so its contribution is a place-name query and stays
    ``geo_verified: false``. Marking those as verified would be a lie the admin
    UI then repeats.

    Each source degrades on its own — losing Openverse still leaves the Commons
    hits, which are the ones that actually prove proximity.
    """
    if request.lat is None or request.lon is None:
        return SearchOutcome(
            NEARBY, STATUS_ERROR, [], 0, request.page,
            message="Für die Umkreissuche fehlen Koordinaten.",
        )

    results: list[MediaResult] = []
    cached_all = True
    messages: list[str] = []

    try:
        raw, cached = _fetch_raw(
            db, wikimedia_module.ADAPTER.name, wikimedia_module.ADAPTER, request, nearby=True
        )
        results.extend(wikimedia_module.ADAPTER.parse(raw, geo_verified=True))
        cached_all = cached_all and cached
    except (BudgetExhausted, ProviderError) as exc:
        messages.append(f"Wikimedia: {exc}")

    if request.query:
        try:
            raw, cached = _fetch_raw(
                db, openverse_module.ADAPTER.name, openverse_module.ADAPTER, request, nearby=True
            )
            results.extend(openverse_module.ADAPTER.parse(raw))
            cached_all = cached_all and cached
        except (BudgetExhausted, ProviderError) as exc:
            messages.append(f"Openverse: {exc}")

    if not results and messages:
        return SearchOutcome(
            NEARBY, STATUS_ERROR, [], 0, request.page, message="; ".join(messages)
        )

    items = _finalise(db, results)
    return SearchOutcome(
        NEARBY,
        STATUS_OK,
        items,
        len(items),
        request.page,
        cached=cached_all,
        message="; ".join(messages) or None,
    )


def _finalise(db: Session, results: list[MediaResult]) -> list[dict]:
    """Drop unusable licenses, de-duplicate, annotate prior usage."""
    usable: list[MediaResult] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        if not adoptable(result):
            continue
        pair = (result.provider, result.external_id)
        if pair in seen:
            continue
        seen.add(pair)
        usable.append(result)

    index = _usage_index(db, usable)
    payload = []
    for result in usable:
        result.used_by = index.get((result.provider, result.external_id), [])
        payload.append(result.as_payload())
    return payload


def provider_status(db: Session) -> list[dict]:
    """Configured/enabled state and budget of every provider — powers the budget
    display in the admin header."""
    rows = []
    for key, adapter in PROVIDERS.items():
        rows.append(
            {
                "provider": key,
                "available": adapter.available(),
                "budget": budget_store.budget_state(db, key),
            }
        )
    return rows
