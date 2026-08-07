"""One result schema for every media provider, plus the size gates.

The picker UI must not know a single provider special case, so every adapter in
:mod:`app.media.providers` returns :class:`MediaResult` and nothing else. All
provider-specific knowledge — which URL field is the big one, where the license
name hides, whether the bytes may be hotlinked — is spent inside the adapter and
never leaves it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# --- size gates ------------------------------------------------------------
# A hero is cropped to 2:1 and carries typography, so the source must survive
# that crop without upscaling regardless of where the focal point sits:
# 3840×1920 is the smallest size that always can. Portrait photos fail this by
# construction, which is the intent — no separate orientation rule needed.
#
# Deliberately distinct from app.media.hero.HERO_MIN_* (3840×2000), which gates
# operator *uploads* and stays where it is: loosening that would change what
# admins may upload, which is not this feature's call.
HERO_MIN_WIDTH = 3840
HERO_MIN_HEIGHT = 1920

# Gallery images are shown in a justified grid, so only the long edge matters.
GALLERY_MIN_LONG_EDGE = 1600


def hero_eligible(width: int | None, height: int | None) -> bool:
    if not width or not height:
        return False
    return width >= HERO_MIN_WIDTH and height >= HERO_MIN_HEIGHT


def gallery_eligible(width: int | None, height: int | None) -> bool:
    if not width or not height:
        return False
    return max(width, height) >= GALLERY_MIN_LONG_EDGE


@dataclass(frozen=True)
class License:
    name: str
    url: str | None = None
    # Both must be true for a result to be adoptable at all — we run a
    # commercial site and crop/overlay every hero.
    commercial: bool = False
    modification: bool = False


@dataclass(frozen=True)
class Credit:
    name: str
    url: str | None = None


@dataclass
class MediaResult:
    provider: str
    external_id: str
    thumb_url: str
    preview_url: str          # ~1600px, feeds the live hero preview
    full_url: str             # highest resolution the provider offers
    license: License
    credit: Credit
    source_page: str | None = None
    width: int | None = None
    height: int | None = None
    delivery: str = "hosted"  # decided by the adapter, never by the UI
    geo_verified: bool = False
    # Filled in by the search service from media_usage, not by the adapter.
    used_by: list[dict] = field(default_factory=list)
    # Unsplash only: pinging this on adopt is an API condition. Never stored on
    # the image object — it is a one-shot callback, not provenance.
    unsplash_download_location: str | None = None

    def as_payload(self) -> dict:
        """JSON shape sent to the picker, with the gates resolved."""
        data = asdict(self)
        data["hero_eligible"] = hero_eligible(self.width, self.height)
        data["gallery_eligible"] = gallery_eligible(self.width, self.height)
        return data


def adoptable(result: MediaResult) -> bool:
    """Whether the license permits our use at all.

    Enforced when results leave the server, so a photo we may not crop or use
    commercially never reaches the grid — the operator cannot pick it by
    mistake and Sprint 3 re-checks it anyway before writing.
    """
    return result.license.commercial and result.license.modification
