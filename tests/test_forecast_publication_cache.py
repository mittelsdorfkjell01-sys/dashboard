import uuid

from sqlalchemy import select

from app.forecast.publisher import enqueue, run_job
from app.live.cache import InMemoryCache
from app.live.public_cache import get_public_forecast
from app.models import Spot
from app.seed.seed import seed
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
