from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

from app.live.public_cache import (
    get_public_forecast,
    set_public_forecast,
    set_public_live,
)


class RecordingCache:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ttl):
        self.values[key] = value
        self.ttls[key] = ttl


def test_forecast_cache_ttl_is_capped_to_snapshot_validity(monkeypatch):
    monkeypatch.setattr(
        "app.live.public_cache.get_settings",
        lambda: SimpleNamespace(
            weather_public_live_cache_ttl=300,
            weather_public_forecast_cache_ttl=10_800,
        ),
    )
    cache = RecordingCache()
    spot_id = uuid.uuid4()
    valid_until = datetime.now(timezone.utc) + timedelta(minutes=47)

    set_public_forecast(
        cache, spot_id, {"spot_id": str(spot_id), "days": []}, valid_until=valid_until
    )

    key = f"public:weather-v6:forecast:{spot_id}"
    assert 2819 <= cache.ttls[key] <= 2820
    assert cache.values[key]["_fresh_until"] == valid_until.isoformat()


def test_expired_forecast_is_not_cached(monkeypatch):
    monkeypatch.setattr(
        "app.live.public_cache.get_settings",
        lambda: SimpleNamespace(weather_public_forecast_cache_ttl=10_800),
    )
    cache = RecordingCache()
    set_public_forecast(
        cache,
        uuid.uuid4(),
        {"days": []},
        valid_until=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    assert cache.values == {}


def test_public_cache_helpers_fail_open(monkeypatch):
    monkeypatch.setattr(
        "app.live.public_cache.get_settings",
        lambda: SimpleNamespace(weather_public_live_cache_ttl=300),
    )

    class BrokenCache:
        def get(self, key):
            raise ConnectionError("down")

        def set(self, key, value, ttl):
            raise ConnectionError("down")

    spot_id = uuid.uuid4()
    assert get_public_forecast(BrokenCache(), spot_id) is None
    set_public_live(BrokenCache(), spot_id, {"spot_id": str(spot_id)})
