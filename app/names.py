"""Canonical display-name and slug handling shared by catalogue entities."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select

_SPACE = re.compile(r"\s+")
_SLUG_SEP = re.compile(r"[^a-z0-9]+")


def clean_display_name(value: str) -> str:
    cleaned = _SPACE.sub(" ", unicodedata.normalize("NFKC", value or "").strip())
    if not cleaned:
        raise ValueError("Name darf nicht leer sein.")
    return cleaned


def normalize_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", clean_display_name(value).casefold())
    return "".join(c for c in folded if not unicodedata.combining(c))


def slugify(value: str) -> str:
    folded = unicodedata.normalize("NFKD", clean_display_name(value))
    ascii_value = folded.encode("ascii", "ignore").decode("ascii").lower()
    return _SLUG_SEP.sub("-", ascii_value).strip("-") or "eintrag"


def available_slug(db, model, value: str, *, exclude_id=None, max_length: int = 120) -> str:
    base = slugify(value)[:max_length].rstrip("-")
    candidate = base
    suffix = 2
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if db.scalar(stmt) is None:
            return candidate
        tail = f"-{suffix}"
        candidate = f"{base[: max_length - len(tail)].rstrip('-')}{tail}"
        suffix += 1
