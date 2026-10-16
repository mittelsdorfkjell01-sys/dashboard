import uuid

from sqlalchemy import select

from app.forecast.publisher import enqueue, run_job
from app.forecast.refresh_worker import build_plan
from app.live.cache import InMemoryCache
from app.live.public_cache import get_public_forecast
from app.models import ForecastSnapshot, Spot
from app.seed.seed import seed
from app.spatial_fields.spot_forecast import SpotFieldResult
from tests.live_helpers import FakeOpenMeteoClient


def test_successful_publisher_job_populates_public_forecast_cache(db):
    seed(db)
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    cache = InMemoryCache()
    job = enqueue(db, spot.id, reason=f"cache-test-{uuid.uuid4()}")

    result = run_job(
        db,
        job.id,
        client=FakeOpenMeteoClient(data_days=11),
        cache=cache,
    )

    assert result.status == "succeeded"
    cached = get_public_forecast(cache, spot.id)
    assert cached is not None
    assert cached["spot_id"] == str(spot.id)
    assert len(cached["days"]) == 10


def test_publisher_persists_field_primary_status_within_database_contract(
    db, monkeypatch
):
    seed(db)
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    cache = InMemoryCache()
    job = enqueue(db, spot.id, reason=f"field-status-test-{uuid.uuid4()}")
    monkeypatch.setattr(
        "app.forecast.publisher.apply_spot_field_baseline",
        lambda _db, **kwargs: SpotFieldResult(
            kwargs["payload"], True, {"operator_override": True}
        ),
    )

    result = run_job(
        db,
        job.id,
        client=FakeOpenMeteoClient(data_days=11),
        cache=cache,
    )

    snapshot = db.scalar(
        select(ForecastSnapshot).where(
            ForecastSnapshot.spot_id == spot.id,
            ForecastSnapshot.active.is_(True),
        )
    )
    assert result.status == "succeeded"
    assert snapshot.fallback_status == "field_primary_open_meteo_aux"
    assert snapshot.internal["source"] == "weather-field"


def test_publisher_does_not_resurrect_snapshot_after_context_change(
    db, monkeypatch
):
    seed(db)
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    cache = InMemoryCache()
    job = enqueue(db, spot.id, reason=f"context-race-{uuid.uuid4()}")
    contexts = iter(("before", "before", "after"))
    monkeypatch.setattr(
        "app.forecast.publisher.serving_context_hash",
        lambda *args, **kwargs: next(contexts),
    )

    events = []
    monkeypatch.setattr(
        "app.forecast.publisher.logger.warning",
        lambda message, **kwargs: events.append((message, kwargs["extra"])),
    )
    result = run_job(
        db,
        job.id,
        client=FakeOpenMeteoClient(data_days=11),
        cache=cache,
    )

    assert result.status == "superseded"
    assert result.diagnostics["reason"] == "weather_serving_context_changed"
    assert get_public_forecast(cache, spot.id) is None
    (message, event), = events
    assert message == "weather_forecast_publisher_superseded"
    assert event["weather_reason_code"] == "weather_serving_context_changed"
    assert event["weather_phase"] == "before_promotion"
    assert event["weather_spot_id"] == str(spot.id)


def test_wave_publication_refresh_converges_snapshot_and_public_cache(
    db, monkeypatch
):
    seed(db)
    spot = db.scalar(select(Spot).where(Spot.slug == "tarifa-los-lances"))
    cache = InMemoryCache()
    publication_ids = ["ewam-publication", "gwam-publication"]
    job = enqueue(db, spot.id, reason="wave-publication-integration")
    monkeypatch.setattr(
        "app.forecast.publisher.apply_spot_wave_baseline",
        lambda _db, **kwargs: SpotFieldResult(
            kwargs["payload"],
            True,
            {
                "source": "weather-field",
                "active_publication_ids": publication_ids,
                "publication_ids": publication_ids,
                "replaced_hours": 2,
                "tail_fallback": "open-meteo-marine",
            },
        ),
    )

    result = run_job(
        db,
        job.id,
        client=FakeOpenMeteoClient(data_days=11),
        cache=cache,
    )
    snapshot = db.scalar(
        select(ForecastSnapshot).where(
            ForecastSnapshot.spot_id == spot.id,
            ForecastSnapshot.active.is_(True),
        )
    )
    plan = build_plan(
        [spot],
        [snapshot],
        active_wave_publication_ids=publication_ids,
    )

    assert result.status == "succeeded"
    assert snapshot.internal["wave_field"]["active_publication_ids"] == publication_ids
    assert get_public_forecast(cache, spot.id) is not None
    assert plan.wave_context_changed_spot_ids == ()
