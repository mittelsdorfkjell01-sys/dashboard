from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

from app.live.public_cache import (
    get_public_forecast,
    invalidate_public_weather,
    get_public_live,
    public_forecast_key,
    public_live_key,
    public_weather_generation,
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

    def delete(self, key):
        self.values.pop(key, None)
        self.ttls.pop(key, None)


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

    key = public_forecast_key(spot_id)
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


def test_weather_invalidation_drops_only_assembled_spot_entries(monkeypatch):
    cache = RecordingCache()
    spot_id = uuid.uuid4()
    cache.values = {
        public_live_key(spot_id): {"kind": "live"},
        public_forecast_key(spot_id): {"kind": "forecast"},
        "om:provider:raw": {"kind": "provider"},
    }

    events = []
    monkeypatch.setattr(
        "app.live.public_cache.logger.info",
        lambda message, **kwargs: events.append((message, kwargs["extra"])),
    )
    invalidate_public_weather(cache, spot_id)

    assert public_live_key(spot_id) not in cache.values
    assert public_forecast_key(spot_id) not in cache.values
    assert cache.values["om:provider:raw"] == {"kind": "provider"}
    (message, event), = events
    assert message == "public_weather_cache_generation_advanced"
    assert event["weather_spot_id"] == str(spot_id)
    assert event["weather_previous_cache_generation"] == "0"
    assert event["weather_cache_generation"] == public_weather_generation(
        cache, spot_id
    )


def test_inflight_response_cannot_repopulate_the_new_cache_generation():
    cache = RecordingCache()
    spot_id = uuid.uuid4()
    old_generation = public_weather_generation(cache, spot_id)

    invalidate_public_weather(cache, spot_id)
    set_public_live(
        cache,
        spot_id,
        {"old": True},
        generation=old_generation,
    )

    assert public_weather_generation(cache, spot_id) != old_generation
    assert get_public_live(cache, spot_id) is None
