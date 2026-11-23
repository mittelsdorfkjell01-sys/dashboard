"""Bounded OpenStreetMap POI lookup for the spot locator map."""

from __future__ import annotations

import math
import re
from functools import lru_cache
from urllib.parse import urlparse
from typing import Any, Protocol

import httpx

from app.config import get_settings

POI_CATEGORIES = {"parking", "cafe", "bar", "surf_school", "campsite"}
CATEGORY_LIMITS = {
    "parking": 40,
    "cafe": 25,
    "bar": 20,
    "surf_school": 20,
    "campsite": 15,
}


class PoiProviderError(RuntimeError):
    """The configured POI provider could not return a usable response."""


class PoiClient(Protocol):
    def nearby(self, latitude: float, longitude: float, radius_m: int) -> list[dict[str, Any]]: ...


class OverpassPoiClient:
    def __init__(
        self,
        *,
        global_endpoints: tuple[str, ...],
        europe_endpoint: str,
        user_agent: str,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.global_endpoints = global_endpoints
        self.europe_endpoint = europe_endpoint
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client(
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def nearby(self, latitude: float, longitude: float, radius_m: int) -> list[dict[str, Any]]:
        query = _overpass_query(latitude, longitude, radius_m)
        endpoints = self.global_endpoints
        if _is_in_europe(latitude, longitude):
            endpoints = (self.europe_endpoint, *endpoints)
        last_error: Exception | None = None
        for endpoint in dict.fromkeys(endpoints):
            try:
                response = self.client.post(
                    endpoint,
                    data={"data": query},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
                    raise ValueError("invalid Overpass response")
                return parse_overpass_pois(
                    payload["elements"], latitude, longitude, radius_m=radius_m
                )
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        raise PoiProviderError("OpenStreetMap POIs are temporarily unavailable") from last_error


def _is_in_europe(latitude: float, longitude: float) -> bool:
    """Broad coverage bounds including the Canaries, Azores and Iceland."""
    return 27 <= latitude <= 72 and -32 <= longitude <= 45


def _overpass_query(latitude: float, longitude: float, radius_m: int) -> str:
    latitude_delta = radius_m / 111_320
    longitude_delta = radius_m / max(1, 111_320 * math.cos(math.radians(latitude)))
    bbox = (
        f"{latitude - latitude_delta:.6f},{longitude - longitude_delta:.6f},"
        f"{latitude + latitude_delta:.6f},{longitude + longitude_delta:.6f}"
    )
    selectors = (
        '["amenity"~"^(parking|cafe|bar|pub|surf_school)$"]',
        '["education"="surf_school"]',
        '["training"="surf"]',
        '["tourism"~"^(camp_site|caravan_site)$"]',
    )
    body = "\n".join(f"  nwr({bbox}){selector};" for selector in selectors)
    return f"[out:json][timeout:8][maxsize:8388608];\n(\n{body}\n);\nout center tags qt;"


def _category(tags: dict[str, Any]) -> str | None:
    amenity = tags.get("amenity")
    if (
        amenity == "surf_school"
        or tags.get("education") == "surf_school"
        or tags.get("training") == "surf"
    ):
        return "surf_school"
    if amenity == "parking":
        return "parking"
    if amenity == "cafe":
        return "cafe"
    if amenity in {"bar", "pub"}:
        return "bar"
    if tags.get("tourism") in {"camp_site", "caravan_site"}:
        return "campsite"
    return None


_PHONE_ALLOWED = re.compile(r"^[+0-9 ()/.\-]{4,40}$")


def _text(tags: dict[str, Any], *keys: str, limit: int = 160) -> str | None:
    for key in keys:
        value = tags.get(key)
        if isinstance(value, str) and (cleaned := " ".join(value.split())):
            return cleaned[:limit]
    return None


def _website(tags: dict[str, Any]) -> str | None:
    raw = _text(tags, "website", "contact:website", "url", limit=300)
    if not raw:
        return None
    candidate = raw if re.match(r"^https?://", raw, re.IGNORECASE) else f"https://{raw}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or " " in candidate:
        return None
    return candidate


def _phone(tags: dict[str, Any]) -> str | None:
    raw = _text(tags, "phone", "contact:phone", "contact:mobile", limit=200)
    if not raw:
        return None
    first = raw.split(";")[0].strip()
    return first if _PHONE_ALLOWED.match(first) else None


def _yes_no(value: Any) -> bool | None:
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    return None


def _address(tags: dict[str, Any]) -> str | None:
    street = " ".join(part for part in (_text(tags, "addr:street"), _text(tags, "addr:housenumber")) if part)
    town = " ".join(part for part in (_text(tags, "addr:postcode"), _text(tags, "addr:city", "addr:place")) if part)
    joined = ", ".join(part for part in (street, town) if part)
    return joined[:200] or None


def _details(tags: dict[str, Any]) -> dict[str, Any]:
    """The facts OpenStreetMap volunteers recorded — nothing inferred.

    Every field is optional: an empty one means "not mapped", never "no"."""
    cuisine = _text(tags, "cuisine", limit=200)
    capacity = tags.get("capacity")
    wheelchair = tags.get("wheelchair")
    return {
        "opening_hours": _text(tags, "opening_hours", limit=240),
        "website": _website(tags),
        "phone": _phone(tags),
        "address": _address(tags),
        "cuisine": [part.strip().replace("_", " ") for part in cuisine.split(";") if part.strip()][:4] if cuisine else [],
        "outdoor_seating": _yes_no(tags.get("outdoor_seating")),
        "wheelchair": wheelchair if wheelchair in {"yes", "limited", "no"} else None,
        "fee": _yes_no(tags.get("fee")),
        "capacity": int(capacity) if isinstance(capacity, str) and capacity.isdigit() and int(capacity) <= 100_000 else None,
        "takeaway": _choice(tags.get("takeaway"), {"yes", "no", "only"}),
        "wifi": _wifi(tags),
        "vegetarian": _choice(tags.get("diet:vegetarian"), {"yes", "no", "only", "limited"}),
        "vegan": _choice(tags.get("diet:vegan"), {"yes", "no", "only", "limited"}),
        "dogs": _choice(tags.get("dog"), {"yes", "no", "leashed"}),
        "card_payment": _card_payment(tags),
        "toilets": _yes_no(tags.get("toilets")),
        "reservation": _choice(tags.get("reservation"), {"yes", "no", "required", "recommended"}),
        "smoking": _choice(tags.get("smoking"), {"yes", "no", "outside", "separated", "isolated"}),
        "instagram": _instagram(tags),
        "check_date": _check_date(tags),
    }


def _choice(value: Any, allowed: set[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _wifi(tags: dict[str, Any]) -> bool | None:
    value = tags.get("internet_access")
    if value in {"wlan", "wifi", "yes"}:
        return True
    if value == "no":
        return False
    return None


def _card_payment(tags: dict[str, Any]) -> bool | None:
    keys = ("payment:cards", "payment:credit_cards", "payment:debit_cards", "payment:contactless", "payment:girocard")
    if any(tags.get(key) == "yes" for key in keys):
        return True
    if tags.get("payment:cash_only") == "yes" or tags.get("payment:cards") == "no":
        return False
    return None


_INSTAGRAM_HANDLE = re.compile(r"^[A-Za-z0-9_.]{1,30}$")


def _instagram(tags: dict[str, Any]) -> str | None:
    raw = _text(tags, "contact:instagram", "instagram", limit=200)
    if not raw:
        return None
    handle = re.sub(r"^(?:https?://)?(?:www\.)?instagram\.com/", "", raw, flags=re.IGNORECASE)
    handle = handle.strip("/@ ").split("/")[0].split("?")[0]
    return f"https://www.instagram.com/{handle}/" if _INSTAGRAM_HANDLE.match(handle) else None


def _check_date(tags: dict[str, Any]) -> str | None:
    """When a mapper last confirmed the entry on site (YYYY-MM[-DD])."""
    value = _text(tags, "check_date", "survey:date", limit=10)
    return value if value and re.match(r"^\d{4}-\d{2}(?:-\d{2})?$", value) else None


def _distance_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> int:
    earth_radius_m = 6_371_000
    phi_a, phi_b = math.radians(lat_a), math.radians(lat_b)
    delta_phi = math.radians(lat_b - lat_a)
    delta_lambda = math.radians(lon_b - lon_a)
    haversine = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
    )
    return round(earth_radius_m * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine)))


def parse_overpass_pois(
    elements: list[Any],
    latitude: float,
    longitude: float,
    *,
    radius_m: int | None = None,
    limit: int = 120,
) -> list[dict[str, Any]]:
    pois: list[dict[str, Any]] = []
    seen: set[str] = set()
    for element in elements:
        if not isinstance(element, dict):
            continue
        element_type = element.get("type")
        element_id = element.get("id")
        tags = element.get("tags")
        if element_type not in {"node", "way", "relation"} or not isinstance(element_id, int):
            continue
        if not isinstance(tags, dict) or (category := _category(tags)) is None:
            continue
        point = element if element_type == "node" else element.get("center")
        if not isinstance(point, dict):
            continue
        item_lat, item_lon = point.get("lat"), point.get("lon")
        if not isinstance(item_lat, (int, float)) or not isinstance(item_lon, (int, float)):
            continue
        poi_id = f"{element_type}/{element_id}"
        if poi_id in seen:
            continue
        seen.add(poi_id)
        name = tags.get("name") or tags.get("operator")
        distance_m = _distance_m(latitude, longitude, float(item_lat), float(item_lon))
        if radius_m is not None and distance_m > radius_m:
            continue
        pois.append(
            {
                "id": poi_id,
                "category": category,
                "name": str(name).strip()[:160] if name else None,
                "lat": float(item_lat),
                "lon": float(item_lon),
                "distance_m": distance_m,
                "osm_url": f"https://www.openstreetmap.org/{element_type}/{element_id}",
                **_details(tags),
            }
        )
    pois.sort(key=lambda poi: (poi["distance_m"], poi["id"]))
    category_counts = {category: 0 for category in POI_CATEGORIES}
    balanced: list[dict[str, Any]] = []
    for poi in pois:
        category = poi["category"]
        if category_counts[category] >= CATEGORY_LIMITS[category]:
            continue
        category_counts[category] += 1
        balanced.append(poi)
    balanced.sort(key=lambda poi: (poi["distance_m"], poi["id"]))
    return balanced[:limit]


@lru_cache(maxsize=1)
def default_poi_client() -> PoiClient:
    settings = get_settings()
    return OverpassPoiClient(
        global_endpoints=(
            settings.osm_overpass_url,
            settings.osm_overpass_fallback_url,
        ),
        europe_endpoint=settings.osm_overpass_europe_url,
        user_agent=settings.osm_user_agent,
        timeout_seconds=settings.osm_poi_timeout_seconds,
    )


def get_poi_client() -> PoiClient:
    return default_poi_client()
