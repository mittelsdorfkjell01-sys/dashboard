from types import SimpleNamespace

from app.api.admin_weather import SectorIn, WeatherProfileIn, _missing, _overlap
from app.live.cache import InMemoryCache
from app.live.service import get_live_conditions
from tests.live_helpers import FakeDB, FakeOpenMeteoClient, make_spot
import uuid


def test_basis_required_fields_are_explicit():
    body = WeatherProfileIn(quality_tier="coastal")
    assert _missing(body) == ["timezone", "elevation_m", "coastal_normal_deg"]


def test_sector_overlap_detects_north_wrap_and_allows_gap():
    wrap = SectorIn(start_deg=330, end_deg=20, speed_factor=1)
    north = SectorIn(start_deg=10, end_deg=40, speed_factor=1)
    east = SectorIn(start_deg=80, end_deg=120, speed_factor=1)
    assert _overlap(wrap, north)
    assert not _overlap(wrap, east)


def test_facing_is_never_a_weather_profile_fallback():
    spot = make_spot()
    spot.facing = 123
    out = get_live_conditions(spot.id, db=FakeDB(spot), client=FakeOpenMeteoClient(), cache=InMemoryCache())
    assert out["quality_tier"] == "coordinates"
    assert out["coastal_classification"] is None


def test_weather_admin_requires_authentication(anon_client):
    assert anon_client.get("/admin/weather/profiles").status_code == 401


def test_profile_api_validates_timezone_and_advanced_gating(client, db):
    from app.seed.seed import seed
    from app.models import Spot
    from sqlalchemy import select

    seed(db)
    spot = db.scalar(select(Spot).order_by(Spot.name))
    invalid = client.put(f"/admin/weather/spots/{spot.id}/profile", json={
        "quality_tier": "coastal", "timezone": "Mars/Olympus",
        "elevation_m": 2, "coastal_normal_deg": 270,
    })
    assert invalid.status_code == 422
    assert "timezone" in invalid.json()["detail"]

    advanced = client.put(f"/admin/weather/spots/{spot.id}/profile", json={
        "quality_tier": "advanced", "timezone": "Europe/Berlin",
        "elevation_m": 2, "coastal_normal_deg": 270, "reviewed": False,
        "sectors": [{"start_deg": 250, "end_deg": 290, "speed_factor": 1.1}],
    })
    assert advanced.status_code == 422


def test_profile_list_is_single_admin_endpoint_and_unknown_spot_is_404(client):
    listing = client.get("/admin/weather/profiles?country=DE")
    assert listing.status_code == 200
    assert isinstance(listing.json()["items"], list)
    assert client.put(f"/admin/weather/spots/{uuid.uuid4()}/profile", json={"quality_tier": "coordinates"}).status_code == 404
