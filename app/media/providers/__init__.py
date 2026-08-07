"""Provider adapters for the admin media picker.

Each adapter owns two things and nothing else: how to ask its API, and how to
turn that answer into :class:`app.media.normalize.MediaResult`. The parsing half
is a pure function over a decoded JSON body, so the test-suite exercises it
against frozen real responses without touching the network.

Pixabay is deliberately absent: its API serves ~1280px to non-approved accounts,
which fails the hero gate for practically every photo, and its terms forbid
permanent hotlinking.
"""

from __future__ import annotations

from typing import Protocol

from app.media.providers import openverse, pexels, unsplash, wikimedia
from app.media.providers.base import ProviderError, ProviderRequest, ProviderUnavailable


class MediaProvider(Protocol):
    name: str

    def available(self) -> bool:
        """False when a required credential is missing — the tab then reports
        ``disabled`` instead of failing."""

    def search(self, request: ProviderRequest) -> list[dict]:
        """Raw upstream payload(s), already decoded. Cached verbatim."""

    def parse(self, raw: list[dict]) -> list:
        """Raw payload → list[MediaResult]. Pure; no network."""


# Tab order is a UI concern (it differs for spots and regions), so this registry
# is deliberately unordered — it maps a provider key to its adapter.
PROVIDERS: dict[str, MediaProvider] = {
    unsplash.ADAPTER.name: unsplash.ADAPTER,
    pexels.ADAPTER.name: pexels.ADAPTER,
    wikimedia.ADAPTER.name: wikimedia.ADAPTER,
    openverse.ADAPTER.name: openverse.ADAPTER,
}

# "nearby" is a cross-provider search rather than a source of its own, so it is
# handled by the search service and not registered here.
NEARBY = "nearby"

PROVIDER_KEYS = tuple(PROVIDERS) + (NEARBY,)


def get_provider(key: str) -> MediaProvider:
    try:
        return PROVIDERS[key]
    except KeyError:
        raise ProviderError(f"unknown provider: {key!r}")


__all__ = [
    "MediaProvider",
    "PROVIDERS",
    "PROVIDER_KEYS",
    "NEARBY",
    "ProviderError",
    "ProviderRequest",
    "ProviderUnavailable",
    "get_provider",
]
