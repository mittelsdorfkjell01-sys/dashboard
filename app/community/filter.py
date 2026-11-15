"""Content term filter for UGC (tips/ratings), in two tiers.

**Flag** is the old behaviour and still the default: a match publishes the item
and raises ``flagged``, so it sorts to the top of the admin review queue. It is
for signals that are *suspicious*, not certainly wrong — a link, a crypto
mention, an operator's domain term. Publishing them keeps the site honest: most
are fine, and quietly swallowing a comment because it contains a URL would lose
real local knowledge.

**Hold** is new and stronger: a match never publishes. The comment is written
with ``status="pending"``, nobody but the operator sees it, and the author is
told that it is being checked rather than left to wonder. It is for abuse —
slurs and sexual insults — where the cost of showing it for even an hour is
higher than the cost of making a false positive wait for review.

Both lists are substring, case-insensitive, and deliberately small. A big list
of "bad words" catches Scunthorpe, not abuse: it would hold "Wasserstand" for
containing "ass" and still miss anything spelled with a 0. Substring matching
is a floor, not a wall — the operator queue is the real moderation, and this
only decides what is visible while it waits. Operators extend either tier via
``BANNED_WORDS`` (flag) and ``BLOCKED_WORDS`` (hold).
"""

from __future__ import annotations

import re

from app.config import get_settings

# Built-in spam/link indicators (uncontroversial). Substring, case-insensitive.
_BUILTIN_FLAG = (
    "http://", "https://", "www.", ".com", ".net", ".ru",
    "casino", "viagra", "bitcoin", "crypto", "telegram", "whatsapp +",
)

# Terms that hold a comment back for review. German and English slurs and
# sexual insults only — not mild profanity. "Scheiße" in "der Einstieg ist
# scheiße steinig" is someone describing a spot, and holding that back would
# teach people that this site does not want plain speech.
#
# Matched on word boundaries, not bare substrings, so "Wasserstand" survives a
# list that contains "ass" and "Fickmühle" does not take "Fick" down with it in
# the rare case it is meant as the board-game term.
_BUILTIN_HOLD = (
    "fotze", "wichser", "hurensohn", "missgeburt", "untermensch",
    "nigger", "neger", "schwuchtel", "kanake", "judensau",
    "faggot", "retard", "cunt", "whore",
)


def _extra(raw: str | None) -> list[str]:
    return [w.strip().lower() for w in (raw or "").split(",") if w.strip()]


def _flag_terms() -> list[str]:
    return list(_BUILTIN_FLAG) + _extra(get_settings().banned_words)


def _hold_terms() -> list[str]:
    return list(_BUILTIN_HOLD) + _extra(getattr(get_settings(), "blocked_words", ""))


def _blob(texts: tuple[str | None, ...]) -> str:
    return " ".join(t for t in texts if t).lower()


def is_flagged(*texts: str | None) -> bool:
    """True if any text contains a built-in or configured flag term.

    Substring matching is right here: the flag tier is about links and spam
    fragments, which are substrings by nature (".com" inside a domain).
    """
    blob = _blob(texts)
    if not blob:
        return False
    return any(term in blob for term in _flag_terms())


def is_held(*texts: str | None) -> bool:
    """True if any text contains a term that must not publish before review.

    Word boundaries, unlike :func:`is_flagged`: a hold costs the author their
    comment until a human looks, so a false positive is expensive and "ass"
    inside "Wasserstand" must not trigger one.
    """
    blob = _blob(texts)
    if not blob:
        return False
    return any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", blob) for term in _hold_terms())
