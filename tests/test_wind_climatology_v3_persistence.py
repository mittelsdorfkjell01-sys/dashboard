"""Postgres integration coverage for additive V3 persistence invariants."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models import Spot, WindClimatologyCell, WindClimatologyV3Run
from app.seed.seed import seed
from app.wind_climatology.v3_engine import ALGORITHM_VERSION


def _spot_and_cell(db):
    seed(db)
    spot = db.scalar(select(Spot).order_by(Spot.name))
    db.execute(delete(WindClimatologyV3Run).where(WindClimatologyV3Run.spot_id == spot.id))
    db.commit()
    cell = db.scalar(select(WindClimatologyCell).where(WindClimatologyCell.spot_id == spot.id))
    if cell is None:
        cell = WindClimatologyCell(spot_id=spot.id, spot_lat=1, spot_lon=2, requested_lat=1, requested_lon=2)
        db.add(cell)
        db.commit()
    return spot, cell


def _run(spot, cell, **values):
    return WindClimatologyV3Run(spot_id=spot.id, cell_id=cell.id, start_year=2006, end_year=2025, algorithm_version=ALGORITHM_VERSION, config_hash=values.pop("config_hash", uuid.uuid4().hex), **values)


def test_only_one_successful_v3_run_can_be_active(db):
    spot, cell = _spot_and_cell(db)
    db.add(_run(spot, cell, status="ready", is_active=True))
    db.commit()
    db.add(_run(spot, cell, status="ready", is_active=True))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_failed_refresh_does_not_deactivate_previous_ready_run(db):
    spot, cell = _spot_and_cell(db)
    active = _run(spot, cell, status="ready", is_active=True)
    failed = _run(spot, cell, status="failed", is_active=False, error="provider unavailable")
    db.add_all([active, failed])
    db.commit()
    db.refresh(active)
    assert active.is_active is True


def test_identical_v3_configuration_cannot_be_inflight_twice(db):
    spot, cell = _spot_and_cell(db)
    digest = uuid.uuid4().hex
    db.add(_run(spot, cell, status="pending", config_hash=digest))
    db.commit()
    db.add(_run(spot, cell, status="processing", config_hash=digest))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
