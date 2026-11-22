import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.map_pois import get_poi_cache, router
from app.live.cache import InMemoryCache
from app.map_pois import OverpassPoiClient, PoiProviderError, get_poi_client, parse_overpass_pois


class FakePoiClient:
    def __init__(self, items=None, error: Exception | None = None):
        self.items = items or []
        self.error = error
        self.calls = 0

    def nearby(self, latitude: float, longitude: float, radius_m: int):
        self.calls += 1
        if self.error:
            raise self.error
        return self.items


def _app(fake: FakePoiClient) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    cache = InMemoryCache()
    app.dependency_overrides[get_poi_client] = lambda: fake
    app.dependency_overrides[get_poi_cache] = lambda: cache
    return TestClient(app)


def test_parse_overpass_pois_classifies_centres_sorts_and_deduplicates():
    elements = [
        {"type": "node", "id": 2, "lat": 54.401, "lon": 10.201, "tags": {"amenity": "cafe", "name": "Küsten Café"}},
        {"type": "way", "id": 3, "center": {"lat": 54.405, "lon": 10.205}, "tags": {"tourism": "camp_site"}},
        {"type": "node", "id": 1, "lat": 54.4001, "lon": 10.2001, "tags": {"education": "surf_school", "operator": "Windwerk"}},
        {"type": "node", "id": 1, "lat": 54.4001, "lon": 10.2001, "tags": {"education": "surf_school"}},
        {"type": "node", "id": 4, "lat": 54.4, "lon": 10.2, "tags": {"amenity": "bench"}},
        {"type": "node", "id": 5, "lat": 54.406, "lon": 10.206, "tags": {"amenity": "parking"}},
        {"type": "node", "id": 6, "lat": 54.407, "lon": 10.207, "tags": {"amenity": "pub", "name": "Küstenbar"}},
    ]

    result = parse_overpass_pois(elements, 54.4, 10.2)

    assert {item["category"] for item in result} == {"surf_school", "cafe", "campsite", "parking", "bar"}
    assert result[0]["name"] == "Windwerk"
    assert result[1]["osm_url"] == "https://www.openstreetmap.org/node/2"


def test_map_pois_uses_the_shared_cache_and_exposes_attribution():
    fake = FakePoiClient([{
        "id": "node/7", "category": "parking", "name": "Strandparkplatz",
        "lat": 54.4, "lon": 10.2, "distance_m": 25,
        "osm_url": "https://www.openstreetmap.org/node/7",
    }])
    client = _app(fake)

    first = client.get("/map/pois", params={"lat": 54.4, "lon": 10.2})
    second = client.get("/map/pois", params={"lat": 54.4, "lon": 10.2})

    assert first.status_code == second.status_code == 200
    assert fake.calls == 1
    assert first.json()["items"][0]["category"] == "parking"
    assert first.json()["attribution"] == "© OpenStreetMap-Mitwirkende"
    assert "s-maxage=86400" in first.headers["cache-control"]


def test_map_pois_returns_a_recoverable_provider_error():
    client = _app(FakePoiClient(error=PoiProviderError("offline")))

    response = client.get("/map/pois", params={"lat": 54.4, "lon": 10.2})

    assert response.status_code == 503
    assert response.headers["retry-after"] == "30"
    assert "momentan nicht verfügbar" in response.json()["detail"]


def test_european_overpass_request_falls_back_after_a_provider_error():
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        if request.url.host == "europe.test":
            return httpx.Response(503, request=request)
        return httpx.Response(200, request=request, json={"elements": []})

    provider = OverpassPoiClient(
        global_endpoints=("https://global.test/interpreter",),
        europe_endpoint="https://europe.test/interpreter",
        user_agent="test/1.0",
        timeout_seconds=2,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.nearby(54.4, 10.2, 3_000) == []
    assert requested_hosts == ["europe.test", "global.test"]


def test_parse_overpass_pois_keeps_only_mapped_details():
    elements = [
        {"type": "node", "id": 9, "lat": 54.401, "lon": 10.201, "tags": {
            "amenity": "cafe", "name": "Dünen Café", "opening_hours": "Mo-Su 09:00-18:00",
            "website": "duenencafe.example", "phone": "+49 4343 1234; +49 170 1",
            "addr:street": "Strandstraße", "addr:housenumber": "4", "addr:postcode": "24235",
            "addr:city": "Laboe", "cuisine": "coffee_shop;cake", "outdoor_seating": "yes",
            "wheelchair": "limited",
        }},
        {"type": "node", "id": 10, "lat": 54.402, "lon": 10.202, "tags": {
            "amenity": "parking", "fee": "no", "capacity": "120", "website": "javascript alert", "phone": "call us",
        }},
    ]

    cafe, parking = parse_overpass_pois(elements, 54.4, 10.2)

    assert cafe["opening_hours"] == "Mo-Su 09:00-18:00"
    assert cafe["website"] == "https://duenencafe.example"
    assert cafe["phone"] == "+49 4343 1234"
    assert cafe["address"] == "Strandstraße 4, 24235 Laboe"
    assert cafe["cuisine"] == ["coffee shop", "cake"]
    assert cafe["outdoor_seating"] is True
    assert cafe["wheelchair"] == "limited"
    assert cafe["fee"] is None
    assert parking["fee"] is False
    assert parking["capacity"] == 120
    assert parking["website"] is None
    assert parking["phone"] is None
    assert parking["opening_hours"] is None


def test_parse_overpass_pois_reads_cafe_and_bar_details():
    elements = [{"type": "node", "id": 11, "lat": 54.401, "lon": 10.201, "tags": {
        "amenity": "bar", "name": "Strandbar", "takeaway": "only", "internet_access": "wlan",
        "diet:vegetarian": "yes", "diet:vegan": "limited", "dog": "leashed", "payment:debit_cards": "yes",
        "toilets": "yes", "reservation": "recommended", "smoking": "outside",
        "contact:instagram": "https://www.instagram.com/strandbar_laboe/?hl=de", "check_date": "2026-05-14",
    }}, {"type": "node", "id": 12, "lat": 54.402, "lon": 10.202, "tags": {
        "amenity": "cafe", "payment:cash_only": "yes", "internet_access": "terminal",
        "contact:instagram": "not a handle!", "check_date": "last summer", "dog": "maybe",
    }}]

    bar, cafe = parse_overpass_pois(elements, 54.4, 10.2)

    assert bar["takeaway"] == "only"
    assert bar["wifi"] is True
    assert (bar["vegetarian"], bar["vegan"]) == ("yes", "limited")
    assert bar["dogs"] == "leashed"
    assert bar["card_payment"] is True
    assert bar["toilets"] is True
    assert bar["reservation"] == "recommended"
    assert bar["smoking"] == "outside"
    assert bar["instagram"] == "https://www.instagram.com/strandbar_laboe/"
    assert bar["check_date"] == "2026-05-14"
    assert cafe["card_payment"] is False
    assert cafe["wifi"] is None
    assert cafe["instagram"] is None
    assert cafe["check_date"] is None
    assert cafe["dogs"] is None
