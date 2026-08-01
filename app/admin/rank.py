"""The "Fertigstellen" traffic-light rank.

A spot's rank summarises how far along its rework is, from its readiness gaps:

* **green**  — nothing open (no required gaps left).
* **yellow** — one or two points open, and the hero image is present.
* **red**    — an *important* input is missing (hero image) OR more than two
               points are open.

Climatology is a *soft* gap: it runs as a background job (auto-started on
go-live), not a manual omission, so a pending climatology only ever keeps a spot
yellow — it never forces red and never counts toward the "more than two" red
threshold.

Operators may override the automatic value per spot (``spots.finish_rank``);
the override wins until cleared. Keep this rule in sync with the frontend copy
in ``frontend/src/lib/rank.ts``.
"""

from __future__ import annotations

# Gaps that count as "important" — their absence forces red on their own.
IMPORTANT_GAPS = {"image"}
# Gaps that must never push a spot to red (kept yellow at worst).
SOFT_GAPS = {"climatology"}
RANKS = ("red", "yellow", "green")


def auto_rank(gaps: list[str]) -> str:
    """Traffic-light rank derived purely from the readiness ``gaps`` list."""
    if not gaps:
        return "green"
    hard = [g for g in gaps if g not in SOFT_GAPS]
    if any(g in IMPORTANT_GAPS for g in gaps) or len(hard) > 2:
        return "red"
    return "yellow"


def effective_rank(gaps: list[str], override: str | None) -> str:
    """The rank actually shown: a valid manual override, else the auto value."""
    if override in RANKS:
        return override
    return auto_rank(gaps)
