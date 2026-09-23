"""Guard test: after seed + climatology batch, the content is actually there.

Fails if the batch leaves **0** spots with climatology, if the protected season
inspector cannot read it, or if ``/search/best-spots`` cannot rank it.
This is the regression guard for the "spots invisible / unsearchable" state — it
must not silently return.

Runs against the test database with a **fake** extraction client (the same
synthetic series the pipeline tests use), so no network is touched. Skips cleanly
when the test database is unreachable (see conftest).
"""

from __future__ import annotations

import argparse

import pytest
from sqlalchemy import delete, func, select

from app.era5 import batch
from app.era5.bins import N_WEEKS
from app.models import Era5Job, Spot
from app.seed.seed import seed
from tests.era5_helpers import FakeCdsClient, make_synthetic_series

SLUG = "tarifa-los-lances"


def _args(**over) -> argparse.Namespace:
    """A batch args namespace with the CLI defaults, overridable per test."""
    base = dict(
        status="all", region=None, slug=None, force=False, dry_run=False,
        sleep=0.0, years=20, retries=3, timeout=60.0, cds=False,
    )
    base.update(over)
    return argparse.Namespace(**base)


@pytest.fixture
def seeded_spot(db):
    seed(db)
    spot = db.scalar(select(Spot).where(Spot.slug == SLUG))
    assert spot is not None

    def _reset():
        db.execute(delete(Era5Job).where(Era5Job.spot_id == spot.id))
        spot.climatology = None
        spot.overrides = None
        db.commit()

    _reset()
    yield spot
    _reset()


def test_batch_populates_climatology_and_makes_spot_rankable(
    db, client, seeded_spot, tmp_path
):
    fake = FakeCdsClient(make_synthetic_series())

    report = batch.run_batch(
        _args(slug=[SLUG]), db=db, client=fake, raw_dir=str(tmp_path)
    )

    # 1) the batch reports success and writes climatology
    assert report.ok == [SLUG]
    assert not report.fail
    db.refresh(seeded_spot)
    assert seeded_spot.climatology is not None
    assert len(seeded_spot.climatology["weeks"]) == N_WEEKS
    # the batch must never touch overrides
    assert seeded_spot.overrides is None
    # at least one spot in the catalogue now carries climatology
    assert db.scalar(select(func.count()).select_from(Spot).where(
        Spot.climatology.is_not(None))) >= 1

    sport = seeded_spot.sports[0]

    # 2) The admin inspector returns a non-flat 52-week curve. The equivalent
    # public scoring route intentionally does not exist.
    assert client.get(f"/spots/{seeded_spot.id}/season").status_code == 404
    r = client.get(
        f"/admin/scoring/spots/{seeded_spot.id}/season", params={"sport": sport}
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["curve"]) == N_WEEKS
    assert any(value > 0 for value in r.json()["curve"])

    # 3) /search/best-spots can rank it without exposing the ranking inputs.
    r = client.get("/search/best-spots", params={"sport": sport})
    assert r.status_code == 200, r.text
    spots = r.json()["spots"]
    assert spots, "best-spots returned no candidates"
    ours = next((s for s in spots if s["slug"] == SLUG), None)
    assert ours is not None, f"{SLUG} missing from best-spots"
    assert "coverage" not in ours and "intensity" not in ours


def test_batch_skips_spot_that_already_has_climatology(
    db, seeded_spot, tmp_path
):
    fake = FakeCdsClient(make_synthetic_series())
    first = batch.run_batch(
        _args(slug=[SLUG]), db=db, client=fake, raw_dir=str(tmp_path)
    )
    assert first.ok == [SLUG]

    # a second run is idempotent: the spot is skipped, nothing re-submitted
    again = batch.run_batch(
        _args(slug=[SLUG]), db=db, client=fake, raw_dir=str(tmp_path)
    )
    assert again.ok == []
    assert [s for s, _ in again.skip] == [SLUG]
