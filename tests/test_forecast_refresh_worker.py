from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.forecast.refresh_worker import (
    RefreshPlan,
    build_plan,
    enqueue_due,
    run_refresh_cycle,
)


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
    monkeypatch.setattr("app.forecast.refresh_worker.load_plan", lambda db, **kwargs: RefreshPlan((uuid4(),), 0, 2))
    monkeypatch.setattr("app.forecast.refresh_worker.enqueue", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    assert enqueue_due(object(), dry_run=True)["queued"] == 0


def test_worker_stops_at_run_budget_without_blocking_prior_success(monkeypatch):
    ids = (uuid4(), uuid4())
    monkeypatch.setattr("app.forecast.refresh_worker.load_plan", lambda db, **kwargs: RefreshPlan(ids, 0, 4))
    queued = []
    monkeypatch.setattr("app.forecast.refresh_worker.enqueue", lambda db, spot_id, **kwargs: queued.append(spot_id))
    report = enqueue_due(object(), dry_run=False, run_request_budget=2)
    assert queued == [ids[0]]
    assert report["stopped"] == "provider_budget"


def test_fresh_snapshot_is_due_when_active_wave_publications_changed():
    spot_id = uuid4()
    spot = SimpleNamespace(id=spot_id, status="published")
    snapshot = SimpleNamespace(
        spot_id=spot_id,
        generated_at=NOW - timedelta(minutes=5),
        internal={"wave_field": {"active_publication_ids": ["old-ewam", "old-gwam"]}},
    )

    plan = build_plan(
        [spot],
        [snapshot],
        now=NOW,
        active_wave_publication_ids=("new-ewam", "old-gwam"),
    )

    assert plan.due_spot_ids == (spot_id,)
    assert plan.wave_context_changed_spot_ids == (spot_id,)
    assert plan.wave_context is not None


def test_fresh_snapshot_with_matching_wave_context_stays_skipped_even_without_wave_values():
    spot_id = uuid4()
    spot = SimpleNamespace(id=spot_id, status="published")
    snapshot = SimpleNamespace(
        spot_id=spot_id,
        generated_at=NOW - timedelta(minutes=5),
        internal={
            "wave_field": {
                "reason": "wave_field_horizon_unavailable",
                "active_publication_ids": ["ewam", "gwam"],
            }
        },
    )

    plan = build_plan(
        [spot],
        [snapshot],
        now=NOW,
        active_wave_publication_ids=("gwam", "ewam"),
    )

    assert plan.due_spot_ids == ()
    assert plan.wave_context_changed_spot_ids == ()
    assert plan.skipped_fresh == 1


def test_wave_publication_refresh_uses_context_specific_idempotency_reason(monkeypatch):
    spot_id = uuid4()
    plan = RefreshPlan(
        (spot_id,),
        0,
        2,
        wave_context_changed_spot_ids=(spot_id,),
        wave_context="abc123",
    )
    monkeypatch.setattr("app.forecast.refresh_worker.load_plan", lambda db, **kwargs: plan)
    queued = []
    monkeypatch.setattr(
        "app.forecast.refresh_worker.enqueue",
        lambda db, queued_spot_id, **kwargs: queued.append((queued_spot_id, kwargs["reason"])),
    )

    report = enqueue_due(object(), dry_run=False)

    assert queued == [(spot_id, "wave-publication-abc123")]
    assert report["wave_context_changed"] == 1
    assert report["wave_context"] == "abc123"


def test_refresh_cycle_enqueues_all_due_but_processes_bounded_batch(monkeypatch):
    ids = (uuid4(), uuid4(), uuid4())
    monkeypatch.setattr(
        "app.forecast.refresh_worker.enqueue_due",
        lambda *args, **kwargs: {
            "due": 3,
            "queued": 3,
            "failed": 0,
            "estimated_provider_attempts": 6,
            "stopped": None,
            "dry_run": False,
        },
    )
    jobs = [
        SimpleNamespace(id=value, spot_id=uuid4(), status="succeeded", error=None)
        for value in ids[:2]
    ]

    class Scalars:
        def __iter__(self):
            return iter(ids[:2])

    class DB:
        def scalars(self, _query):
            return Scalars()

    completed = []

    def run_job(_db, job_id):
        completed.append(job_id)
        return jobs[len(completed) - 1]

    monkeypatch.setattr("app.forecast.publisher.run_job", run_job)
    settings = SimpleNamespace(
        forecast_refresh_request_budget=20,
        forecast_job_batch_size=2,
    )
    result = run_refresh_cycle(DB(), settings=settings, now=NOW)

    assert completed == list(ids[:2])
    assert result["enqueue"]["queued"] == 3
    assert len(result["processed"]) == 2
    assert result["status"] == "ok"
