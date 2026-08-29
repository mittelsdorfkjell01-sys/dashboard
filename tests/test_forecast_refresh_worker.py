from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.forecast.refresh_worker import RefreshPlan, build_plan, enqueue_due


NOW = datetime(2026, 8, 26, 0, tzinfo=timezone.utc)


def test_refresh_plan_includes_missing_and_two_hour_old_snapshots_idempotently():
    missing, old, fresh, draft = [uuid4() for _ in range(4)]
    spots = [SimpleNamespace(id=value, status="draft" if value == draft else "published")
             for value in (missing, old, fresh, draft)]
    snapshots = [
        SimpleNamespace(spot_id=old, generated_at=NOW - timedelta(hours=2)),
        SimpleNamespace(spot_id=fresh, generated_at=NOW - timedelta(minutes=119)),
    ]
    first = build_plan(spots, snapshots, now=NOW)
    second = build_plan(spots, snapshots, now=NOW)
    assert first == second
    assert first.due_spot_ids == (missing, old)
    assert first.estimated_provider_attempts == 4


def test_worker_dry_run_never_enqueues(monkeypatch):
    monkeypatch.setattr("app.forecast.refresh_worker.load_plan", lambda db: RefreshPlan((uuid4(),), 0, 2))
    monkeypatch.setattr("app.forecast.refresh_worker.enqueue", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    assert enqueue_due(object(), dry_run=True)["queued"] == 0


def test_worker_stops_at_run_budget_without_blocking_prior_success(monkeypatch):
    ids = (uuid4(), uuid4())
    monkeypatch.setattr("app.forecast.refresh_worker.load_plan", lambda db: RefreshPlan(ids, 0, 4))
    queued = []
    monkeypatch.setattr("app.forecast.refresh_worker.enqueue", lambda db, spot_id, **kwargs: queued.append(spot_id))
    report = enqueue_due(object(), dry_run=False, run_request_budget=2)
    assert queued == [ids[0]]
    assert report["stopped"] == "provider_budget"
