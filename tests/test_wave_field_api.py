from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from starlette.requests import Request

from app.community.ratelimit import NoLimitRateLimiter

from app.api import weather_fields


NOW = datetime(2026, 10, 11, 0, tzinfo=timezone.utc)


def _candidate(key: str, priority: int, start: int, end: int) -> dict:
    return {
        "key": key,
        "name": key,
        "provider": "noaa" if key == "noaa-gfs-wave" else "dwd",
        "coverage": {"west": -180.0, "south": -85.0, "east": 180.0, "north": 85.0},
        "model_run": NOW,
        "primary": key == "dwd-ewam",
        "priority": priority,
        "freshness": "fresh",
        "valid_from": (NOW + timedelta(hours=start)).isoformat(),
        "valid_to": (NOW + timedelta(hours=end)).isoformat(),
    }


def _settings():
    return SimpleNamespace(
        wave_field_public_enabled=True,
        wave_field_scope_key="europe-waves",
        wave_field_primary_model="dwd-ewam",
        wave_field_fallback_model="dwd-gwam",
        wave_field_extended_model="noaa-gfs-wave",
    )


def test_wave_selection_uses_gfs_wave_for_a_ten_day_valid_time(monkeypatch) -> None:
    models = [
        _candidate("dwd-ewam", 6, 0, 78),
        _candidate("dwd-gwam", 16, 0, 174),
        _candidate("noaa-gfs-wave", 26, 168, 240),
    ]
    monkeypatch.setattr(weather_fields, "_public_models", lambda *args, **kwargs: models)
    monkeypatch.setattr(weather_fields, "configured_field_storage", lambda: object())
    monkeypatch.setattr(
        weather_fields,
        "load_active_manifest",
        lambda *args, **kwargs: SimpleNamespace(object_key="manifest", sha256="hash"),
    )

    _active, selected, available, selection = weather_fields._resolve_field_selection(
        object(),
        settings=_settings(),
        requested_model=None,
        latitude=54.4,
        longitude=11.2,
        valid_at=NOW + timedelta(hours=240),
        base_scope="europe-waves",
        primary_model="dwd-ewam",
    )

    assert selected["key"] == "noaa-gfs-wave"
    assert selection["reason"] == "forecast_horizon"
    assert [item["covers_time"] for item in available] == [False, False, True]


def test_wave_series_merges_models_by_priority_into_one_ten_day_axis(monkeypatch) -> None:
    models = [
        _candidate("dwd-ewam", 6, 0, 78),
        _candidate("dwd-gwam", 16, 0, 174),
        _candidate("noaa-gfs-wave", 26, 168, 240),
    ]
    for item in models:
        item["covers_point"] = True
    active_by_scope = {
        "europe-waves": SimpleNamespace(
            publication_id="ewam", manifest=SimpleNamespace(valid_times=[NOW])
        ),
        "europe-waves:dwd-gwam": SimpleNamespace(
            publication_id="gwam", manifest=SimpleNamespace(valid_times=[NOW + timedelta(hours=174)])
        ),
        "europe-waves:noaa-gfs-wave": SimpleNamespace(
            publication_id="gfs-wave",
            manifest=SimpleNamespace(
                valid_times=[NOW + timedelta(hours=174), NOW + timedelta(hours=240)]
            ),
        ),
    }
    monkeypatch.setattr(weather_fields, "get_settings", _settings)
    monkeypatch.setattr(weather_fields, "_public_models", lambda *args, **kwargs: models)
    monkeypatch.setattr(weather_fields, "configured_field_storage", lambda: object())
    monkeypatch.setattr(
        weather_fields,
        "load_active_manifest",
        lambda _db, *, scope_key, **kwargs: active_by_scope[scope_key],
    )

    def sample_series(*args, model_key, valid_times, **kwargs):
        return [
            {"valid_at": instant, "model": model_key, "product": "model_wave"}
            for instant in valid_times
        ]

    monkeypatch.setattr(weather_fields, "sample_active_field_series", sample_series)

    result = weather_fields.wave_field_sample_series(
        request=Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1234)}),
        lat=54.4,
        lon=11.2,
        model=None,
        db=object(),
        limiter=NoLimitRateLimiter(),
    )

    assert result["samples"][-1]["valid_at"] == NOW + timedelta(hours=240)
    assert result["samples"][-1]["model"] == "noaa-gfs-wave"
    overlap = next(
        sample
        for sample in result["samples"]
        if sample["valid_at"] == NOW + timedelta(hours=174)
    )
    assert overlap["model"] == "dwd-gwam"
    assert [source["model"] for source in result["sources"]] == [
        "dwd-ewam",
        "dwd-gwam",
        "noaa-gfs-wave",
    ]


def test_wind_manifest_asks_for_a_model_that_reaches_the_requested_day(monkeypatch) -> None:
    """The map's clock runs five days; ICON-D2 publishes two.

    Without `valid_at` the wind endpoint always answered with the highest
    priority model covering the viewport — ICON-D2 over Germany — so the
    clock's day arrows died after two days. The endpoint now forwards the
    requested instant, and the selection falls to a model whose horizon
    reaches it.
    """
    models = [
        _candidate("icon-d2", 5, 0, 48),
        _candidate("icon-eu", 10, 0, 120),
        _candidate("gfs-0p25", 20, 0, 240),
    ]
    monkeypatch.setattr(weather_fields, "_public_models", lambda *args, **kwargs: models)
    monkeypatch.setattr(weather_fields, "configured_field_storage", lambda: object())
    monkeypatch.setattr(
        weather_fields,
        "load_active_manifest",
        lambda *args, **kwargs: SimpleNamespace(object_key="manifest", sha256="hash"),
    )
    settings = SimpleNamespace(
        weather_field_public_enabled=True,
        weather_field_scope_key="europe-wind",
        weather_field_primary_model="icon-eu",
    )

    def selected_for(hours: int | None) -> tuple[str, str]:
        _active, selected, _available, selection = weather_fields._resolve_field_selection(
            object(),
            settings=settings,
            requested_model=None,
            latitude=54.4,
            longitude=10.2,
            valid_at=None if hours is None else NOW + timedelta(hours=hours),
            base_scope="europe-wind",
            primary_model="icon-eu",
        )
        return selected["key"], selection["reason"]

    # Near the present the short-range model still wins.
    assert selected_for(None)[0] == "icon-d2"
    assert selected_for(6) == ("icon-d2", "forecast_horizon")
    # Day four is beyond ICON-D2, so a model that reaches it is chosen.
    assert selected_for(96) == ("icon-eu", "forecast_horizon")


def test_wind_manifest_route_forwards_the_requested_instant(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_selection(*_args, **kwargs):
        seen.update(kwargs)
        return (
            SimpleNamespace(
                publication_id="pub",
                generation=1,
                object_key="manifest",
                sha256="hash",
                manifest=SimpleNamespace(model_dump=lambda mode="json": {"valid_times": []}),
            ),
            {"freshness": "fresh"},
            [],
            {"mode": "auto", "selected_model": "icon-eu"},
        )

    monkeypatch.setattr(weather_fields, "_resolve_field_selection", fake_selection)
    monkeypatch.setattr(weather_fields, "_series_manifests", lambda *args, **kwargs: [])
    monkeypatch.setattr(weather_fields, "configured_field_storage", lambda: SimpleNamespace(public_url=lambda key: key))
    monkeypatch.setattr(
        weather_fields,
        "get_settings",
        lambda: SimpleNamespace(
            weather_field_public_enabled=True,
            weather_field_scope_key="europe-wind",
            weather_field_primary_model="icon-eu",
        ),
    )
    monkeypatch.setattr(weather_fields, "_cached_manifest_response", lambda _key, builder: builder())

    instant = NOW + timedelta(hours=96)
    request = Request({"type": "http", "method": "GET", "path": "/weather-fields/wind", "headers": []})
    response = SimpleNamespace(headers={}, status_code=200)
    weather_fields.wind_field_manifest(
        request=request,
        response=response,
        model=None,
        lat=54.4,
        lon=10.2,
        west=None,
        south=None,
        east=None,
        north=None,
        valid_at=instant,
        db=SimpleNamespace(get_bind=lambda: object()),
    )

    assert seen["valid_at"] == instant
