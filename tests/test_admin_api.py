"""DB-gated admin workflow tests. Skip when the test database is unavailable.

Covers the full create → curate → validate → live path, the n/a rule, and the
override → audit → provenance → recompute → revert behaviour.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.admin.deps import get_cds_client
from app.main import app
from app.models import Era5Job, Spot, SpotAudit
from app.seed.seed import seed
from tests.era5_helpers import FakeCdsClient, make_synthetic_series


@pytest.fixture(scope="module", autouse=True)
def _seeded(_migrated_db):
    from app.db.session import SessionLocal
    from tests.conftest import require_db

    require_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _cleanup_test_rows(db):
    """Delete this module's created regions after **each** test so accumulated
    spots/jobs don't collide (every fake job reuses cds_request_id 'fake-1') or
    leak into later modules.

    The spots go first, explicitly. ``db.delete(region)`` alone makes the ORM
    orphan them — ``UPDATE spots SET region_id = NULL`` — and once more than one
    orphan shares a normalized name, that update trips
    ``uq_spots_unassigned_normalized_name`` and the teardown errors out. The
    tests themselves still pass, so this surfaced only as a growing pile of
    teardown errors that made the suite useless as a regression signal.
    """
    yield
    from app.models import Region, Spot

    regions = db.scalars(
        select(Region).where(Region.slug.like("test-region-%"))
    ).all()
    if not regions:
        return
    ids = [region.id for region in regions]
    db.execute(delete(Spot).where(Spot.region_id.in_(ids)))
    db.execute(delete(Region).where(Region.id.in_(ids)))
    db.commit()


@pytest.fixture
def admin(client):
    app.dependency_overrides[get_cds_client] = lambda: FakeCdsClient(make_synthetic_series())
    yield client
    app.dependency_overrides.pop(get_cds_client, None)


@pytest.fixture
def region_id(admin):
    # Unique slug per test — the fixture is function-scoped and rows aren't torn
    # down between tests, so a fixed slug would collide on the 2nd test.
    suffix = uuid.uuid4().hex[:8]
    resp = admin.post("/admin/regions", json={
        "name": f"Test Region {suffix}", "slug": f"test-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
        "defaults": {"model_pref": "icon_d2"},
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_spot(admin, region_id, **overrides):
    suffix = uuid.uuid4().hex[:8]
    body = {
        "name": f"New Spot {suffix}", "slug": f"new-spot-{suffix}",
        "region_id": region_id, "lat": 54.41, "lon": 10.22,
        "sports": ["kitesurf"], "water_type": ["sea"], "bottom_type": ["sand"],
        "level": ["beginner"], "water_character": ["chop"],
    }
    body.update(overrides)
    resp = admin.post("/admin/spots", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_publishable(admin, sid):
    """Fill the editorial hard-gate fields (description + fully-credited image)
    so a spot passes the publish gate. Climatology is exempt from blocking
    go-live but is not derived by it — go-live only queues an async
    wind_climatology_v2 run, so the "climatology" gap stays open afterwards."""
    admin.patch(f"/admin/spots/{sid}", json={
        "editorial": {"description": "A breezy Baltic flatwater spot."},
    })
    admin.post(f"/admin/spots/{sid}/image", json={
        "url": "https://img/x.jpg", "source": "unsplash",
        "license": "Unsplash License", "credit": "Jo",
    })


def _create_region(admin, *, name: str, lat: float, lon: float, country: str = "DE"):
    suffix = uuid.uuid4().hex[:8]
    resp = admin.post("/admin/regions", json={
        "name": name,
        "slug": f"test-region-{suffix}",
        "country": country,
        "lat": lat,
        "lon": lon,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- catalogue duplicate protection ---------------------------------------

def test_exact_spot_duplicate_is_blocked_and_lists_candidate(admin, region_id):
    suffix = uuid.uuid4().hex[:8]
    existing = _create_spot(admin, region_id, name=f"Exact Coast {suffix}")
    response = admin.post("/admin/spots", json={
        "name": f"  exact   coast {suffix.upper()}  ",
        "region_id": region_id,
        "lat": 54.42,
        "lon": 10.23,
        "sports": ["kitesurf"],
    })
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "exact_duplicate"
    assert detail["override_allowed"] is False
    assert detail["candidates"][0]["id"] == existing["id"]


def test_likely_spot_duplicate_can_be_explicitly_overridden(admin, region_id, db):
    suffix = uuid.uuid4().hex[:8]
    existing = _create_spot(
        admin, region_id, name=f"Probable Long Coast {suffix} Alpha", lat=54.410, lon=10.220
    )
    body = {
        "name": f"Probable Long Coast {suffix} Alphaa",
        "region_id": region_id,
        "lat": 54.411,
        "lon": 10.221,
        "sports": ["kitesurf"],
    }
    warning = admin.post("/admin/spots", json=body)
    assert warning.status_code == 409, warning.text
    detail = warning.json()["detail"]
    assert detail["code"] == "likely_duplicate"
    assert detail["override_allowed"] is True
    candidate = detail["candidates"][0]
    assert candidate["id"] == existing["id"]
    assert candidate["region_name"]
    assert isinstance(candidate["distance_m"], int)

    created = admin.post("/admin/spots", json={**body, "allow_duplicate": True})
    assert created.status_code == 201, created.text
    audit = db.scalar(
        select(SpotAudit).where(
            SpotAudit.spot_id == created.json()["id"],
            SpotAudit.action == "create",
        )
    )
    assert existing["id"] in audit.changes["duplicate_override"]


def test_spot_duplicate_check_runs_for_coordinate_change(admin, region_id):
    other = _create_region(
        admin,
        name=f"Test Region Far {uuid.uuid4().hex[:8]}",
        lat=48.0,
        lon=8.0,
    )
    suffix = uuid.uuid4().hex[:8]
    _create_spot(
        admin, region_id, name=f"Coordinate Coast {suffix} Alpha", lat=54.4, lon=10.2
    )
    moving = _create_spot(
        admin, other["id"], name=f"Coordinate Coast {suffix} Alphaa", lat=48.0, lon=8.0
    )
    response = admin.patch(
        f"/admin/spots/{moving['id']}",
        json={"lat": 54.401, "lon": 10.201},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "likely_duplicate"


def test_spot_duplicate_check_runs_for_region_change(admin, region_id):
    other = _create_region(
        admin,
        name=f"Test Region Switch {uuid.uuid4().hex[:8]}",
        lat=48.0,
        lon=8.0,
    )
    name = f"Region Switch Coast {uuid.uuid4().hex[:8]}"
    _create_spot(admin, region_id, name=name, lat=54.4, lon=10.2)
    moving = _create_spot(admin, other["id"], name=name, lat=48.0, lon=8.0)
    response = admin.patch(
        f"/admin/spots/{moving['id']}", json={"region_id": region_id}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "exact_duplicate"


def test_database_constraint_remains_race_safe_for_exact_spots(admin, region_id, db):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    existing = _create_spot(admin, region_id, name=f"Race Coast {uuid.uuid4().hex[:8]}")
    db.add(Spot(
        slug=f"race-copy-{uuid.uuid4().hex[:8]}",
        name=existing["name"].upper(),
        region_id=uuid.UUID(region_id),
        location=from_shape(Point(10.3, 54.5), srid=4326),
        sports=[], water_type=[], level=[], water_character=[], style=[], status="draft",
    ))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_exact_region_duplicate_without_coordinates_is_blocked(admin):
    suffix = uuid.uuid4().hex[:8]
    existing = _create_region(
        admin, name=f"Test Exact Region {suffix}", lat=52.0, lon=9.0
    )
    response = admin.post("/admin/regions", json={
        "name": f" test  exact region {suffix.upper()} ",
        "country": "DE",
    })
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "exact_duplicate"
    assert detail["candidates"][0]["id"] == existing["id"]


def test_likely_region_duplicate_without_coordinates_warns_before_geocoding(admin):
    suffix = uuid.uuid4().hex[:8]
    existing = _create_region(
        admin, name=f"Test Missing Coordinates {suffix} Alpha", lat=51.0, lon=7.0
    )
    response = admin.post("/admin/regions", json={
        "name": f"Test Missing Coordinates {suffix} Alphaa",
        "country": "DE",
    })
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "likely_duplicate"
    assert detail["candidates"][0]["id"] == existing["id"]
    assert detail["candidates"][0]["distance_m"] is None


def test_likely_region_duplicate_create_update_and_admin_override(admin):
    suffix = uuid.uuid4().hex[:8]
    existing = _create_region(
        admin, name=f"Test Probable Region {suffix} Alpha", lat=52.0, lon=9.0
    )
    body = {
        "name": f"Test Probable Region {suffix} Alphaa",
        "slug": f"test-region-{uuid.uuid4().hex[:8]}",
        "country": "DE",
        "lat": 52.01,
        "lon": 9.01,
    }
    warning = admin.post("/admin/regions", json=body)
    assert warning.status_code == 409, warning.text
    assert warning.json()["detail"]["candidates"][0]["id"] == existing["id"]
    created = admin.post("/admin/regions", json={**body, "allow_duplicate": True})
    assert created.status_code == 201, created.text

    unrelated = _create_region(
        admin, name=f"Test Unrelated Region {uuid.uuid4().hex[:8]}", lat=52.02, lon=9.02
    )
    edited = admin.patch(
        f"/admin/regions/{unrelated['id']}",
        json={"name": f"Test Probable Region {suffix} Alphaaa"},
    )
    assert edited.status_code == 409
    assert edited.json()["detail"]["code"] == "likely_duplicate"


def test_curator_cannot_override_likely_duplicate(admin, curator_client):
    suffix = uuid.uuid4().hex[:8]
    existing = _create_region(
        admin, name=f"Test Curator Region {suffix} Alpha", lat=53.0, lon=8.0
    )
    other = _create_region(
        admin, name=f"Test Different Region {uuid.uuid4().hex[:8]}", lat=53.01, lon=8.01
    )
    response = curator_client.patch(
        f"/admin/regions/{other['id']}",
        json={
            "name": f"Test Curator Region {suffix} Alphaa",
            "allow_duplicate": True,
        },
    )
    assert response.status_code == 403
    assert existing["id"]


# --- create: draft + template ----------------------------------------------

def test_create_spot_waits_for_explicit_climatology_action(admin, region_id, db):
    spot = _create_spot(admin, region_id)
    assert spot["status"] == "draft"
    assert spot["model_pref"] == "icon_d2"        # inherited from region defaults
    assert spot["era5_cell"] is not None          # grid cell resolved

    status = admin.get(f"/admin/spots/{spot['id']}/era5").json()
    assert status["status"] == "missing"
    job = db.scalar(select(Era5Job).where(Era5Job.spot_id == spot["id"]))
    assert job is None


# --- readiness + go-live ---------------------------------------------------

def test_go_live_blocks_incomplete_spot(admin, region_id, db):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]

    # Publishing an editorially incomplete spot is blocked (409) — nothing
    # half-finished reaches the public site. The blocking gaps are returned.
    resp = admin.post(f"/admin/spots/{sid}/live")
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert {"editorial.description", "image"} <= set(detail["gaps"])
    # Climatology never blocks (it is derived on go-live).
    assert "climatology" not in detail["gaps"]
    # The spot stayed a draft.
    assert db.get(Spot, sid).status == "draft"

    # Complete the editorial hard-gate fields → go-live now succeeds. The
    # climatology gap stays open (it is only ever exempt from *blocking*,
    # never satisfied by go-live itself): go-live no longer derives it
    # synchronously, it only queues a wind_climatology_v2 run — see
    # app/api/admin.py's go_live and test_go_live_enqueues_wind_climatology_v2.
    _make_publishable(admin, sid)
    again = admin.post(f"/admin/spots/{sid}/live")
    assert again.status_code == 200, again.text
    body = again.json()
    assert body["status"] == "published"
    assert body["ready"] is False and body["gaps"] == ["climatology"]


def test_go_live_enqueues_wind_climatology_v2(admin, region_id, db):
    """Go-live no longer derives the legacy per-spot climatology snapshot
    synchronously (that in-memory ``compute_now`` path — and the failure/retry
    reporting built around it — was retired together with the region season
    aggregate; see app/api/admin.py's go_live). It only queues an async
    wind_climatology_v2 run, surfaced under ``wind_climatology_v2`` in the
    response. Manual retry-on-failure behaviour for the legacy pipeline is
    still covered via the ``/admin/spots/{id}/era5`` path by
    test_manual_climatology_failure_can_be_retried and
    test_climatology_job_fails_permanently_after_three_attempts below."""
    from app.models import WindClimatologyRun

    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    _make_publishable(admin, sid)

    body = admin.post(f"/admin/spots/{sid}/live").json()
    assert body["status"] == "published"
    # Legacy climatology is untouched by go-live — still absent.
    assert "climatology_job" not in body
    db.expire_all()
    assert db.get(Spot, sid).climatology is None

    run_info = body["wind_climatology_v2"]
    assert run_info["created"] is True
    run = db.get(WindClimatologyRun, uuid.UUID(run_info["run_id"]))
    assert run is not None and run.spot_id == uuid.UUID(sid)
    assert run.status == run_info["status"] == "pending"


def test_manual_climatology_failure_can_be_retried(admin, region_id, db):
    class FailingClient:
        def submit(self, dataset, request):
            return "failing-request"

        def poll(self, request_id):
            return "completed"

        def fetch_series(self, request_id):
            raise RuntimeError("temporary upstream failure")

    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    app.dependency_overrides[get_cds_client] = lambda: FailingClient()
    failed = admin.post(f"/admin/spots/{sid}/era5")
    assert failed.status_code == 502
    failed_status = admin.get(f"/admin/spots/{sid}/era5").json()
    assert failed_status["status"] == "queued"
    assert failed_status["attempt_count"] == 1

    app.dependency_overrides[get_cds_client] = lambda: FakeCdsClient(
        make_synthetic_series()
    )
    retried = admin.post(f"/admin/spots/{sid}/era5")
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "current"
    db.expire_all()
    assert db.get(Spot, sid).climatology.get("weeks")


def test_climatology_job_fails_permanently_after_three_attempts(
    admin, region_id, db
):
    from app.admin import era5_worker
    from app.admin.jobs import trigger_era5_job

    class FailingClient:
        def submit(self, dataset, request):
            return "retry-request"

        def poll(self, request_id):
            return "completed"

        def fetch_series(self, request_id):
            raise RuntimeError("provider still unavailable")

    spot = _create_spot(admin, region_id)
    client = FailingClient()
    job = trigger_era5_job(
        spot["id"], db=db, client=client, force=True, reason="annual_refresh"
    )

    for attempt in range(1, 4):
        outcome, _ = era5_worker.compute_now(
            spot["id"], client=client, job_id=job.id
        )
        assert outcome == "fail"
        db.expire_all()
        job = db.get(Era5Job, job.id)
        assert job.params["attempt_count"] == attempt
        assert job.status == ("failed" if attempt == 3 else "queued")


def test_grid_cell_change_keeps_old_snapshot_and_queues_refresh(
    admin, region_id, db
):
    from app.era5.freshness import state

    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    _make_publishable(admin, sid)
    assert admin.post(f"/admin/spots/{sid}/era5").status_code == 200
    db.expire_all()
    before = db.get(Spot, sid)
    generated_at = before.climatology["generated_at"]
    assert before.climatology["weeks"]

    moved = admin.patch(
        f"/admin/spots/{sid}", json={"lat": 55.1, "lon": 12.1}
    )
    assert moved.status_code == 200, moved.text
    db.expire_all()
    row = db.get(Spot, sid)
    assert row.climatology["generated_at"] == generated_at
    assert row.climatology["weeks"]
    assert state(row) == "stale"
    latest = db.scalar(
        select(Era5Job)
        .where(Era5Job.spot_id == sid)
        .order_by(Era5Job.created_at.desc())
    )
    assert latest.status == "queued"
    assert latest.params["reason"] == "location_changed"

    # Existing weekly values mean Go Live does not run a second inline compute.
    live = admin.post(f"/admin/spots/{sid}/live")
    assert live.status_code == 200
    assert "climatology_job" not in live.json()
    db.expire_all()
    assert db.get(Era5Job, latest.id).params["attempt_count"] == 0


def test_unpublish_and_archive(admin, region_id, db):
    """A spot can be taken offline (→ draft) and archived, each audited."""
    spot = _create_spot(admin, region_id)
    sid = spot["id"]

    arch = admin.post(f"/admin/spots/{sid}/archive")
    assert arch.status_code == 200 and arch.json()["status"] == "archived"
    assert db.get(Spot, sid).status == "archived"

    off = admin.post(f"/admin/spots/{sid}/unpublish")
    assert off.status_code == 200 and off.json()["status"] == "draft"
    assert db.get(Spot, sid).status == "draft"

    actions = {
        a.action
        for a in db.scalars(select(SpotAudit).where(SpotAudit.spot_id == sid)).all()
    }
    assert {"archive", "unpublish"} <= actions


def test_reactivate_archived_spot_back_to_draft(admin, region_id, db):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    admin.post(f"/admin/spots/{sid}/archive")

    resp = admin.post(f"/admin/spots/{sid}/reactivate")
    assert resp.status_code == 200 and resp.json()["status"] == "draft"
    assert db.get(Spot, sid).status == "draft"
    actions = {
        a.action
        for a in db.scalars(select(SpotAudit).where(SpotAudit.spot_id == sid)).all()
    }
    assert "reactivate" in actions


def test_delete_spot_removes_row(admin, region_id, db):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]

    resp = admin.delete(f"/admin/spots/{sid}")
    assert resp.status_code == 204
    assert db.get(Spot, sid) is None
    # Deleting a second time is a 404.
    assert admin.delete(f"/admin/spots/{sid}").status_code == 404


def test_list_exclude_status_hides_archived(admin, region_id):
    active = _create_spot(admin, region_id)["id"]
    archived = _create_spot(admin, region_id)["id"]
    admin.post(f"/admin/spots/{archived}/archive")

    ids = {
        s["id"]
        for s in admin.get(
            "/admin/spots", params={"region_id": region_id, "exclude_status": "archived"}
        ).json()["items"]
    }
    assert active in ids
    assert archived not in ids


def test_list_spots_can_sort_by_most_recently_edited(admin, region_id):
    first = _create_spot(admin, region_id)
    second = _create_spot(admin, region_id)
    admin.patch(f"/admin/spots/{first['id']}", json={"name": "Recently edited"})

    items = admin.get(
        "/admin/spots",
        params={"region_id": region_id, "sort": "-updated"},
    ).json()["items"]

    assert items[0]["id"] == first["id"]
    assert any(item["id"] == second["id"] for item in items)


def test_overview_recent_has_last_change(admin, region_id):
    """A freshly created spot surfaces in the dashboard 'recent' list with its
    latest audited change (here: the create)."""
    spot = _create_spot(admin, region_id)
    recent = admin.get("/admin/overview").json()["recent"]
    entry = next((r for r in recent if r["id"] == spot["id"]), None)
    assert entry is not None
    assert entry["last_change"] is not None
    assert entry["last_change"]["action"] == "create"


def test_create_never_autoprocesses_climatology(admin, region_id, db):
    """Creating a draft waits for the explicit form button or Go Live."""
    spot = _create_spot(admin, region_id)
    db.expire_all()
    row = db.get(Spot, spot["id"])
    assert row.climatology is None
    assert db.scalar(select(Era5Job).where(Era5Job.spot_id == row.id)) is None


def test_era5_process_queue(admin, region_id, db, tmp_path, monkeypatch):
    """The maintenance path computes an already persisted queued job."""
    from app.admin.jobs import trigger_era5_job
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "era5_raw_dir", str(tmp_path))
    spot = _create_spot(admin, region_id)
    db.execute(
        delete(Era5Job).where(
            Era5Job.status.in_(("queued", "processing", "extracting"))
        )
    )
    db.commit()
    trigger_era5_job(
        spot["id"],
        db=db,
        client=FakeCdsClient(make_synthetic_series()),
        force=True,
        reason="annual_refresh",
    )
    resp = admin.post("/admin/era5/process-queue", params={"limit": 1})
    assert resp.status_code == 200, resp.text
    assert resp.json()["processed"] == 1

    db.expire_all()
    row = db.get(Spot, spot["id"])
    assert row.climatology and row.climatology.get("weeks")


def test_climatology_cron_is_secret_guarded_and_processes_a_batch(
    admin, region_id, db, monkeypatch
):
    """/cron/climatology now runs several unrelated housekeeping sweeps in one
    call (media cache, forecast jobs, featured warmup, wind_climatology_v2).
    The old legacy-ERA5-only batch (keyed "processed", driven by the
    now-unused ``climatology_cron_batch_size`` setting) was retired alongside
    go-live's synchronous climatology derivation — see app/api/cron.py and
    test_go_live_enqueues_wind_climatology_v2. The legacy Era5Job queue is
    still processed, just no longer by this cron — see
    test_era5_process_queue's manual ``/admin/era5/process-queue`` instead."""
    from datetime import date, datetime, timedelta, timezone as dt_timezone

    from app.config import get_settings
    from app.models import WindClimatologyRun
    from app.wind_climatology.service import enqueue, full_year_window

    monkeypatch.setattr(get_settings(), "cron_secret", "cron-test-secret")
    spot = _create_spot(admin, region_id)

    # cron's wind_climatology_v2 step always picks the *globally* oldest
    # pending run (no per-test scoping) — clear stray pending runs first so
    # the batch it processes below is deterministically ours.
    db.execute(delete(WindClimatologyRun).where(WindClimatologyRun.status == "pending"))
    db.commit()
    run, created = enqueue(db, uuid.UUID(spot["id"]))
    assert created

    start, end = full_year_window()
    expected_hours = (date(end + 1, 1, 1) - date(start, 1, 1)).days * 24
    # One real, sequential hourly timestamp per hour of the 20-year window —
    # aggregate() buckets by actual year/month/day, so (unlike the fetch-layer
    # unit tests) a placeholder timestamp repeated for every hour leaves every
    # bucket empty. Real (not stubbed) daylight_mask + a full hourly series at
    # a real coordinate keeps every bucket's "hours_per_day" safely under 24
    # even across DST transitions — an all-hours-are-daylight stub pushes an
    # October DST fall-back bucket slightly over that ceiling instead.
    window_start = datetime(start, 1, 1, tzinfo=dt_timezone.utc)
    hourly_times = [int((window_start + timedelta(hours=h)).timestamp()) for h in range(expected_hours)]

    class _FakeOpenMeteoResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "latitude": 54.25, "longitude": 10.0, "timezone": "Europe/Berlin",
                "hourly_units": {"wind_speed_10m": "kn"},
                "hourly": {"time": hourly_times, "wind_speed_10m": [15.0] * expected_hours},
            }

    monkeypatch.setattr(
        "app.wind_climatology.client.httpx.get",
        lambda *a, **k: _FakeOpenMeteoResponse(),
    )

    assert admin.get("/cron/climatology").status_code == 401
    response = admin.get(
        "/cron/climatology",
        headers={"Authorization": "Bearer cron-test-secret"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["wind_climatology_v2"] == [{"id": str(run.id), "status": "ready"}]

    db.expire_all()
    assert db.get(WindClimatologyRun, run.id).status == "ready"


def test_na_counts_as_fulfilled(admin, region_id, db):
    # a spot whose description is explicitly n/a still satisfies that rule
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    admin.patch(f"/admin/spots/{sid}", json={"editorial": {
        "description": "n/a", "usable_wind_directions": "n/a",
    }})
    ready = admin.get(f"/admin/spots/{sid}/readiness").json()
    gaps = set(ready["gaps"])
    assert "editorial.description" not in gaps
    assert "editorial.usable_wind_directions" not in gaps


# --- override / provenance / audit / revert --------------------------------

def test_override_writes_provenance_and_audit_then_revert(admin, region_id, db):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]

    resp = admin.post(f"/admin/spots/{sid}/override",
                      json={"field": "confidence", "value": 0.95})
    assert resp.status_code == 200
    view = resp.json()
    assert view["fields"]["confidence"] == 0.95
    assert view["provenance"]["confidence"] == "überschrieben"

    audit = db.scalar(
        select(SpotAudit).where(SpotAudit.spot_id == sid)
        .where(SpotAudit.action == "override")
    )
    assert audit is not None and audit.changes["field"] == "confidence"

    # revert restores the auto provenance
    reverted = admin.post(f"/admin/spots/{sid}/revert", json={"field": "confidence"})
    assert reverted.status_code == 200
    assert reverted.json()["provenance"]["confidence"] == "auto"


def test_recompute_climatology_leaves_override(admin, region_id, db, tmp_path):
    from app.era5 import cds, pipeline

    spot = _create_spot(admin, region_id)
    sid = spot["id"]

    # stand up a raw extract + job, build the climatology (Sprint 2 path)
    client = FakeCdsClient(make_synthetic_series())
    job = cds.request_era5_extract(
        sid,
        db.get(Spot, sid).era5_cell,
        db=db,
        client=client,
    )
    cds.poll_cds_job(
        job.params["cds_request_id"],
        db=db, client=client, raw_dir=str(tmp_path),
    )
    pipeline.build_climatology_record(sid, db=db)

    # editor pins confidence
    admin.post(f"/admin/spots/{sid}/override", json={"field": "confidence", "value": 0.9})
    # re-derive from the raw file
    pipeline.recompute_climatology(sid, db=db)

    db.expire_all()
    spot_row = db.get(Spot, sid)
    assert spot_row.overrides == {"confidence": 0.9}   # override untouched
    assert spot_row.climatology["weeks"]               # climatology refreshed


# --- region edit (Sprint: admin UX) ----------------------------------------

def test_region_update_and_manual_image(admin, region_id):
    r = admin.patch(f"/admin/regions/{region_id}", json={
        "description": "Schöne Ostsee-Region",
        "season": {"weeks": [{"week": 1, "wind_p50": 12}]},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["description"] == "Schöne Ostsee-Region"
    # The write is accepted (still persisted to regions.season for whenever a
    # V2 region aggregation is product-approved), but RegionRead deliberately
    # never echoes it back — see app/schemas/region.py's from_orm_region.
    assert body["season"] is None

    img = admin.post(f"/admin/regions/{region_id}/image", json={
        "url": "https://img/region.jpg", "credit": "Jo",
    })
    assert img.status_code == 200
    assert img.json()["image"]["url"] == "https://img/region.jpg"


def test_reassign_spot_between_regions(admin, region_id):
    spot = _create_spot(admin, region_id)
    suffix = uuid.uuid4().hex[:8]
    rid2 = admin.post("/admin/regions", json={
        "name": f"Test Region {suffix}", "slug": f"test-region-{suffix}",
        "country": "DE", "lat": 54.5, "lon": 10.5,
        "defaults": {"model_pref": "icon_d2"},
    }).json()["id"]
    moved = admin.post(
        f"/admin/spots/{spot['id']}/assign-region", json={"region_id": rid2}
    )
    assert moved.status_code == 200
    assert moved.json()["region_id"] == rid2


# --- team notes + activity -------------------------------------------------

def test_team_notes_crud(admin):
    created = admin.post("/admin/team-notes", json={"body": "Bitte Laboe prüfen"})
    assert created.status_code == 201, created.text
    nid = created.json()["id"]
    assert created.json()["author"]  # actor recorded

    assert any(n["id"] == nid for n in admin.get("/admin/team-notes").json())
    assert admin.post("/admin/team-notes", json={"body": "   "}).status_code == 422

    assert admin.delete(f"/admin/team-notes/{nid}").status_code == 204
    assert all(n["id"] != nid for n in admin.get("/admin/team-notes").json())


def test_activity_lists_real_changes(admin, region_id):
    spot = _create_spot(admin, region_id)
    acts = admin.get("/admin/activity").json()
    assert any(
        a["kind"] == "spot" and a["actor"] and a["target"] == spot["name"]
        for a in acts
    )


def test_activity_groups_multiple_actions_into_one_slot_per_spot(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    # Three separate edits on the same spot → still ONE activity slot.
    admin.patch(f"/admin/spots/{sid}", json={"name": "Edit A"})
    admin.patch(f"/admin/spots/{sid}", json={"water_type": ["lake"]})
    admin.patch(f"/admin/spots/{sid}", json={"bottom_type": ["rock"]})

    acts = admin.get("/admin/activity").json()
    mine = [a for a in acts if a["kind"] == "spot" and a["target_id"] == sid]
    assert len(mine) == 1                       # one slot per spot, not per action
    assert mine[0]["actions"] >= 4              # create + 3 edits aggregated
    # Changed fields are the union across the spot's recent audits.
    assert {"water_type", "bottom_type"} <= set(mine[0]["fields"])


def test_map_spots_lists_all_with_coordinates(admin, region_id):
    spot = _create_spot(admin, region_id)  # created at lat 54.41 / lon 10.22
    rows = admin.get("/admin/map-spots").json()
    mine = next(r for r in rows if r["id"] == spot["id"])
    assert mine["status"] == "draft"
    assert mine["lat"] == pytest.approx(54.41) and mine["lon"] == pytest.approx(10.22)
    assert mine["name"] == spot["name"]


def test_map_spots_can_be_limited_to_viewport(admin, region_id):
    spot = _create_spot(admin, region_id)  # lat 54.41 / lon 10.22

    inside = admin.get(
        "/admin/map-spots",
        params={"west": 10, "south": 54, "east": 11, "north": 55},
    )
    outside = admin.get(
        "/admin/map-spots",
        params={"west": -10, "south": 30, "east": 0, "north": 40},
    )

    assert inside.status_code == 200
    assert any(row["id"] == spot["id"] for row in inside.json())
    assert all(row["id"] != spot["id"] for row in outside.json())
    assert admin.get("/admin/map-spots", params={"west": 10}).status_code == 422


def test_overview_has_team_notes_and_review(admin):
    body = admin.get("/admin/overview").json()
    assert "team_notes" in body and isinstance(body["team_notes"], list)
    assert "review" in body and "submissions_pending" in body["review"]


def test_spot_image_focal(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    admin.post(f"/admin/spots/{sid}/image", json={
        "url": "https://img/x.jpg", "source": "unsplash",
        "license": "Unsplash License", "credit": "Jo",
    })
    resp = admin.post(f"/admin/spots/{sid}/image/focal", json={"x": 30, "y": 70})
    assert resp.status_code == 200, resp.text
    assert resp.json()["image"]["focal"] == {"x": 30.0, "y": 70.0}


def test_spot_image_rotation(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    admin.post(f"/admin/spots/{sid}/image", json={
        "url": "https://img/x.jpg", "source": "unsplash",
        "license": "Unsplash License", "credit": "Jo",
    })
    resp = admin.post(f"/admin/spots/{sid}/image/rotation", json={"rotation": -2.3})
    assert resp.status_code == 200, resp.text
    assert resp.json()["image"]["rotation"] == -2.3


def test_region_image_focal(admin, region_id):
    admin.post(f"/admin/regions/{region_id}/image", json={
        "url": "https://img/r.jpg", "credit": "Jo",
    })
    resp = admin.post(f"/admin/regions/{region_id}/image/focal", json={"x": 25, "y": 40})
    assert resp.status_code == 200, resp.text
    assert resp.json()["image"]["focal"] == {"x": 25.0, "y": 40.0}


def test_focal_without_image_422(admin, region_id):
    spot = _create_spot(admin, region_id)
    resp = admin.post(f"/admin/spots/{spot['id']}/image/focal", json={"x": 10, "y": 10})
    assert resp.status_code == 422


def test_board_task_crud(admin):
    created = admin.post("/admin/board/tasks", json={"title": "Laboe prüfen", "body": "Hero fehlt"})
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    assert created.json()["status"] == "open"
    assert "@" not in created.json()["author"]

    assert any(t["id"] == tid for t in admin.get("/admin/board/tasks").json())
    assert admin.post("/admin/board/tasks", json={"title": "  "}).status_code == 422

    moved = admin.patch(f"/admin/board/tasks/{tid}", json={"status": "done"})
    assert moved.status_code == 200 and moved.json()["status"] == "done"

    edited = admin.patch(
        f"/admin/board/tasks/{tid}",
        json={"title": "Laboe vollständig prüfen", "body": "- Hero\n- Details"},
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "Laboe vollständig prüfen"
    assert edited.json()["body"] == "- Hero\n- Details"

    assert admin.delete(f"/admin/board/tasks/{tid}").status_code == 204
    assert all(t["id"] != tid for t in admin.get("/admin/board/tasks").json())


def test_admin_spot_list_includes_and_filters_canonical_readiness(admin, region_id):
    spot = _create_spot(admin, region_id, name=f"Readiness {uuid.uuid4().hex[:8]}")
    response = admin.get(
        "/admin/spots", params={"q": spot["name"], "completeness": "incomplete"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["readiness"]["ready"] is False
    assert body["items"][0]["readiness"]["missing_count"] == len(
        body["items"][0]["readiness"]["gaps"]
    )


def test_admin_region_searches_normalized_name_and_country(admin):
    suffix = uuid.uuid4().hex[:8]
    region = _create_region(
        admin, name=f"Côte Test {suffix}", country="FR", lat=47.0, lon=2.0
    )
    by_name = admin.get("/admin/regions", params={"q": f"cote test {suffix}"})
    assert [entry["region"]["id"] for entry in by_name.json()] == [region["id"]]
    by_country = admin.get("/admin/regions", params={"q": "fr"})
    assert region["id"] in {entry["region"]["id"] for entry in by_country.json()}


def test_activity_shows_changed_fields(admin, region_id):
    spot = _create_spot(admin, region_id)
    admin.patch(f"/admin/spots/{spot['id']}", json={"level": ["advanced"]})
    acts = admin.get("/admin/activity").json()
    upd = next(
        (a for a in acts if a["target"] == spot["name"] and a["action"] == "update"),
        None,
    )
    assert upd is not None
    assert "level" in upd["fields"]


def test_region_create_geocodes_without_coords(admin):
    from app.search.deps import get_geocoder
    from app.search.geocode import GeocodeResult

    class _Geo:
        def geocode(self, q):
            return [GeocodeResult(name="Sardinien", lat=40.0, lon=9.0,
                                  feature_code="ISL", country="IT")]

    app.dependency_overrides[get_geocoder] = lambda: _Geo()
    try:
        suffix = uuid.uuid4().hex[:8]
        resp = admin.post("/admin/regions", json={
            "name": f"Test Region {suffix}", "slug": f"test-region-{suffix}",
            "country": "IT",
        })
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["center"]["lat"] == 40.0 and body["center"]["lon"] == 9.0
        assert body["bounds"] is not None  # island → area bounds derived
    finally:
        app.dependency_overrides.pop(get_geocoder, None)


def test_geocode_endpoint(admin):
    from app.search.deps import get_geocoder
    from app.search.geocode import GeocodeResult
    from tests.search_helpers import FakeGeocoder

    app.dependency_overrides[get_geocoder] = lambda: FakeGeocoder(
        {"laboe": [GeocodeResult(name="Laboe", lat=54.4, lon=10.2,
                                 feature_code="PPL", country="DE")]}
    )
    try:
        resp = admin.get("/admin/geocode", params={"q": "Laboe"})
        assert resp.status_code == 200, resp.text
        hits = resp.json()
        assert hits, "expected at least one geocode hit"
        hit = hits[0]
        assert hit["name"] and isinstance(hit["lat"], float) and isinstance(hit["lon"], float)
    finally:
        app.dependency_overrides.pop(get_geocoder, None)


# --- optimistic locking (Sprint 1) -----------------------------------------
# This is a multi-operator tool: a PATCH carrying a stale ``updated_at`` must be
# rejected (409) instead of silently clobbering a concurrent edit. Omitting the
# token forces the write through (the "Trotzdem überschreiben" path).

def test_spot_patch_stale_updated_at_conflicts(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]

    # A clearly-outdated token → 409 with the fresh timestamp echoed back.
    stale = admin.patch(
        f"/admin/spots/{sid}",
        json={"name": "Renamed", "expected_updated_at": "2000-01-01T00:00:00+00:00"},
    )
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail["code"] == "stale_write"
    assert detail["current_updated_at"]


def test_spot_patch_current_and_forced_updated_at_succeed(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]

    # The exact loaded token → 200.
    ok = admin.patch(
        f"/admin/spots/{sid}",
        json={"name": "Fresh", "expected_updated_at": spot["updated_at"]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["name"] == "Fresh"
    assert ok.json()["updated_at"] != spot["updated_at"]

    # No token → force overwrite, always 200.
    forced = admin.patch(f"/admin/spots/{sid}", json={"name": "Forced"})
    assert forced.status_code == 200, forced.text
    assert forced.json()["name"] == "Forced"


def test_spot_patch_merges_unrelated_concurrent_fields(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    assert admin.patch(f"/admin/spots/{sid}", json={"level": ["advanced"]}).status_code == 200
    response = admin.patch(
        f"/admin/spots/{sid}",
        json={"name": "Field merge", "expected_values": {"name": spot["name"]}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Field merge"
    assert admin.get(f"/admin/spots/{sid}/record").json()["level"] == ["advanced"]


def test_spot_patch_same_field_conflict_is_specific(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    admin.patch(f"/admin/spots/{sid}", json={"name": "Concurrent"})
    response = admin.patch(
        f"/admin/spots/{sid}",
        json={"name": "Mine", "expected_values": {"name": spot["name"]}},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "field_conflict"
    assert response.json()["detail"]["fields"] == ["name"]
    assert admin.get(f"/admin/spots/{sid}/record").json()["name"] == "Concurrent"


def test_spot_patch_can_clear_optional_editorial_field(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    admin.patch(f"/admin/spots/{sid}", json={"editorial": {"description": "Text"}})
    response = admin.patch(
        f"/admin/spots/{sid}",
        json={"editorial": {"description": None}, "expected_values": {"editorial": {"description": "Text"}}},
    )
    assert response.status_code == 200, response.text
    assert admin.get(f"/admin/spots/{sid}/record").json()["editorial"]["description"] is None


def test_spot_patch_moves_pin_and_reresolves_era5_cell(admin, region_id):
    """Correcting the pin (lat/lon) must persist — regression: SpotUpdate used to
    drop lat/lon, so the marker snapped back on the next open."""
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    old_cell = spot["era5_cell"]

    resp = admin.patch(f"/admin/spots/{sid}", json={"lat": 28.09, "lon": -14.35})
    assert resp.status_code == 200, resp.text
    # PATCH response is refreshed from the DB → proves the write persisted.
    assert resp.json()["location"]["lat"] == pytest.approx(28.09)
    assert resp.json()["location"]["lon"] == pytest.approx(-14.35)
    # A large move must land in a different ERA5 grid cell.
    assert resp.json()["era5_cell"] != old_cell

    # And the form's own load path (admin record GET) reflects it on the next
    # open. Public GET filters to published; new spots start as draft.
    reloaded = admin.get(f"/admin/spots/{sid}/record").json()
    assert reloaded["location"]["lat"] == pytest.approx(28.09)
    assert reloaded["location"]["lon"] == pytest.approx(-14.35)


def test_finish_rank_auto_and_manual_override(admin, region_id):
    """Overview ranks every spot (red/yellow/green); a manual override wins and
    can be cleared back to the automatic value."""
    spot = _create_spot(admin, region_id)  # no hero image → important gap
    sid = spot["id"]

    entry = next(r for r in admin.get("/admin/overview").json()["finish"] if r["id"] == sid)
    assert entry["rank"] == "red"          # missing hero image forces red
    assert entry["rank_auto"] == "red"
    assert entry["finish_rank"] is None

    resp = admin.patch(f"/admin/spots/{sid}/finish-rank", json={"rank": "green"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["finish_rank"] == "green"

    entry2 = next(r for r in admin.get("/admin/overview").json()["finish"] if r["id"] == sid)
    assert entry2["rank"] == "green"       # override shown
    assert entry2["rank_auto"] == "red"    # auto untouched

    admin.patch(f"/admin/spots/{sid}/finish-rank", json={"rank": None})
    entry3 = next(r for r in admin.get("/admin/overview").json()["finish"] if r["id"] == sid)
    assert entry3["rank"] == "red" and entry3["finish_rank"] is None

    assert admin.patch(f"/admin/spots/{sid}/finish-rank", json={"rank": "purple"}).status_code == 422


def test_authenticated_request_records_presence_heartbeat(admin):
    """Any authenticated admin request refreshes the acting user's last_seen_at,
    which powers the online/offline indicator in the user table."""
    users = admin.get("/admin/users").json()
    me = next(u for u in users if u["email"] == "admin@test.example")
    assert me["last_seen_at"] is not None


def test_region_patch_stale_updated_at_conflicts(admin, region_id):
    current = admin.get(f"/admin/regions/{region_id}/record").json()

    stale = admin.patch(
        f"/admin/regions/{region_id}",
        json={"name": "New Name", "expected_updated_at": "2000-01-01T00:00:00+00:00"},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "stale_write"

    ok = admin.patch(
        f"/admin/regions/{region_id}",
        json={"name": "New Name", "expected_updated_at": current["updated_at"]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["name"] == "New Name"


# --- per-spot comment moderation (Sprint 2) --------------------------------
# The admin lists ALL comments on a spot (published + hidden) with parent_id so
# the UI can show threads, and can hide/restore any of them — not just flagged.

def _post_tip(admin, spot_id, body, parent_id=None):
    payload = {"body": body, "author_name": "Tester"}
    if parent_id:
        payload["parent_id"] = parent_id
    resp = admin.post(f"/spots/{spot_id}/tips", json=payload)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def test_spot_tips_lists_all_with_thread_and_hide_restore(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    # The community tips route rejects non-public spots — publish first.
    _make_publishable(admin, sid)
    admin.post(f"/admin/spots/{sid}/live")

    root = _post_tip(admin, sid, "top-level")
    reply = _post_tip(admin, sid, "a reply", parent_id=root["id"])

    listed = admin.get(f"/admin/spots/{sid}/tips")
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) == 2
    by_id = {t["id"]: t for t in items}
    assert by_id[reply["id"]]["parent_id"] == root["id"]
    assert by_id[root["id"]]["parent_id"] is None

    # Hiding the reply keeps it in the per-spot list (so it can be restored),
    # unlike the published-only public feed.
    assert admin.post(f"/admin/tips/{reply['id']}/hide").status_code == 200
    after_hide = {t["id"]: t for t in admin.get(f"/admin/spots/{sid}/tips").json()["items"]}
    assert after_hide[reply["id"]]["status"] == "hidden"

    assert admin.post(f"/admin/tips/{reply['id']}/restore").status_code == 200
    after_restore = {t["id"]: t for t in admin.get(f"/admin/spots/{sid}/tips").json()["items"]}
    assert after_restore[reply["id"]]["status"] == "published"


# --- hero attribution editing (Sprint 5) -----------------------------------
# Edit the current hero's credit/license/source in place — url + focal preserved.

def test_image_attribution_edits_in_place(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    # Set a hero by URL first (full rights fields).
    admin.post(
        f"/admin/spots/{sid}/image",
        json={
            "url": "https://example.test/a.jpg",
            "source": "wikimedia_commons",
            "license": "CC BY-SA 4.0",
            "credit": "Alice",
        },
    )
    # Give it a focal point so we can prove it survives the attribution edit.
    admin.post(f"/admin/spots/{sid}/image/focal", json={"x": 40, "y": 60})

    resp = admin.post(
        f"/admin/spots/{sid}/image/attribution",
        json={"credit": "Bob", "license": "CC0", "source": "own"},
    )
    assert resp.status_code == 200, resp.text
    img = resp.json()["image"]
    assert img["credit"] == "Bob" and img["license"] == "CC0" and img["source"] == "own"
    assert img["url"] == "https://example.test/a.jpg"  # url preserved
    assert img["focal"] == {"x": 40, "y": 60}  # focal preserved


def test_image_attribution_requires_existing_image(admin, region_id):
    spot = _create_spot(admin, region_id)
    resp = admin.post(
        f"/admin/spots/{spot['id']}/image/attribution",
        json={"credit": "X", "license": "Y", "source": "Z"},
    )
    assert resp.status_code == 422, resp.text


# Attribution is mandatory for every image source — an API condition for
# Unsplash/Pexels, a legal one for CC BY / BY-SA. It may be corrected (Wikimedia
# author fields are unreliable) but never emptied, and that is enforced on the
# server rather than only in the form.

def test_a_credit_can_be_corrected_but_not_emptied(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]
    admin.post(f"/admin/spots/{sid}/image", json={
        "url": "https://img/x.jpg", "source": "wikimedia_commons",
        "license": "CC BY-SA 4.0", "credit": "<b>Ana  Ruiz</b>",
    })

    corrected = admin.post(
        f"/admin/spots/{sid}/image/attribution",
        json={"credit": "Ana Ruiz", "license": "CC BY-SA 4.0", "source": "wikimedia_commons"},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["image"]["credit"] == "Ana Ruiz"

    for blank in ("", "   "):
        emptied = admin.post(
            f"/admin/spots/{sid}/image/attribution",
            json={"credit": blank, "license": "CC BY-SA 4.0", "source": "wikimedia_commons"},
        )
        assert emptied.status_code == 422, emptied.text

    # The stored credit survived every rejected attempt. Read back through the
    # list endpoint, which serves the SpotSummary shape including `image`
    # (GET /admin/spots/{id} returns the override-provenance view instead).
    listed = admin.get("/admin/spots", params={"q": spot["name"], "limit": 5}).json()
    stored = next(item for item in listed["items"] if item["id"] == sid)
    assert stored["image"]["credit"] == "Ana Ruiz"


def test_a_spot_image_cannot_be_set_without_a_credit(admin, region_id):
    spot = _create_spot(admin, region_id)
    resp = admin.post(f"/admin/spots/{spot['id']}/image", json={
        "url": "https://img/x.jpg", "source": "unsplash",
        "license": "Unsplash License", "credit": "  ",
    })
    assert resp.status_code == 422, resp.text


def test_a_region_image_cannot_be_set_without_a_credit(admin, region_id):
    resp = admin.post(f"/admin/regions/{region_id}/image", json={
        "url": "https://img/r.jpg", "credit": "",
    })
    assert resp.status_code == 422, resp.text


# --- bulk region transfer (Sprint 6) ---------------------------------------

def test_bulk_assign_region_moves_both_directions(admin, region_id):
    # A second region to move spots into.
    suffix = uuid.uuid4().hex[:8]
    other = admin.post("/admin/regions", json={
        "name": f"Test Region {suffix}", "slug": f"test-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
        "defaults": {"model_pref": "icon_d2"},
    }).json()["id"]

    a = _create_spot(admin, region_id)["id"]
    b = _create_spot(admin, region_id)["id"]

    # Move both from region_id → other in one call.
    resp = admin.post(
        "/admin/spots/bulk-assign-region",
        json={"spot_ids": [a, b], "region_id": other},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["moved"] == 2
    assert admin.get(f"/admin/spots?region_id={other}").json()["total"] >= 2

    # And back the other direction.
    back = admin.post(
        "/admin/spots/bulk-assign-region",
        json={"spot_ids": [a], "region_id": region_id},
    )
    assert back.json()["moved"] == 1


def test_bulk_assign_region_unknown_spot_rolls_back(admin, region_id):
    suffix = uuid.uuid4().hex[:8]
    other = admin.post("/admin/regions", json={
        "name": f"Test Region {suffix}", "slug": f"test-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    }).json()["id"]
    a = _create_spot(admin, region_id)["id"]

    # a would move to `other`, but the unknown id aborts the whole batch.
    resp = admin.post(
        "/admin/spots/bulk-assign-region",
        json={"spot_ids": [a, str(uuid.uuid4())], "region_id": other},
    )
    assert resp.status_code == 404, resp.text
    # a must still be in its original region (nothing committed).
    assert admin.get(f"/admin/spots/{a}/record").json()["region_id"] == region_id


# --- region delete + country (Sprint 7) ------------------------------------

def test_region_delete_blocked_when_spots_assigned(admin, region_id):
    _create_spot(admin, region_id)  # region now has a spot
    resp = admin.delete(f"/admin/regions/{region_id}")
    assert resp.status_code == 409, resp.text
    assert "Spot" in resp.json()["detail"]
    # Still there.
    assert admin.get(f"/admin/regions/{region_id}/record").status_code == 200


def test_region_delete_when_empty(admin):
    suffix = uuid.uuid4().hex[:8]
    rid = admin.post("/admin/regions", json={
        "name": f"Test Region {suffix}", "slug": f"test-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    }).json()["id"]
    assert admin.delete(f"/admin/regions/{rid}").status_code == 204
    assert admin.get(f"/admin/regions/{rid}/record").status_code == 404


def test_region_country_editable(admin):
    suffix = uuid.uuid4().hex[:8]
    rid = admin.post("/admin/regions", json={
        "name": f"Test Region {suffix}", "slug": f"test-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    }).json()["id"]
    resp = admin.patch(f"/admin/regions/{rid}", json={"country": "ES"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["country"] == "ES"


# --- operator notifications (Sprint 9) -------------------------------------
# A community submission creates an operator notification; the admin can list,
# mark one read, and clear all.

def test_admin_notifications_flow(admin, region_id, db):
    from app.community import service as community

    community.create_submission(
        db,
        payload={
            "name": "Vorschlag X", "slug": f"vorschlag-{uuid.uuid4().hex[:8]}",
            "region_id": region_id, "lat": 54.4, "lon": 10.2,
            "sports": ["kitesurf"], "water_type": ["sea"], "bottom_type": ["sand"],
            "level": ["beginner"], "water_character": ["chop"],
        },
        submitter_name="Gast",
    )

    listed = admin.get("/admin/notifications").json()
    assert listed["unread"] >= 1
    sub = next((n for n in listed["items"] if n["type"] == "submission"), None)
    assert sub is not None and not sub["read"]

    assert admin.get("/admin/notifications/unread-count").json()["count"] >= 1
    assert admin.post(f"/admin/notifications/{sub['id']}/read").json()["read"] is True

    admin.post("/admin/notifications/read-all")
    assert admin.get("/admin/notifications/unread-count").json()["count"] == 0


# --- region-less spots (WP-B) ----------------------------------------------

def test_unassign_region_makes_spot_region_less_and_overview_lists_it(admin, region_id):
    spot = _create_spot(admin, region_id)
    sid = spot["id"]

    resp = admin.post("/admin/spots/bulk-unassign-region", json={"spot_ids": [sid]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["changed"] == 1
    assert admin.get(f"/admin/spots/{sid}/record").json()["region_id"] is None

    ov = admin.get("/admin/overview").json()
    assert any(s["id"] == sid for s in ov["no_region"])

    # Re-assign so the region-cascade cleanup reclaims it (no leak into other tests).
    admin.post(f"/admin/spots/{sid}/assign-region", json={"region_id": region_id})


# --- region publish status (WP-C) ------------------------------------------

def test_region_publish_status_and_public_filter(admin):
    suffix = uuid.uuid4().hex[:8]
    rid = admin.post("/admin/regions", json={
        "name": f"Test Region {suffix}", "slug": f"test-region-{suffix}",
        "country": "DE", "lat": 54.4, "lon": 10.2,
    }).json()["id"]

    # New regions start as draft. The public GET /regions/{id} filters to
    # published, so read the draft through the admin record endpoint.
    assert admin.get(f"/admin/regions/{rid}/record").json()["status"] == "draft"
    # Public listing hides drafts; the admin endpoint shows every status.
    assert all(r["id"] != rid for r in admin.get("/regions").json())
    assert any(
        entry["region"]["id"] == rid for entry in admin.get("/admin/regions").json()
    )
    # Drafts are not exposed on the public by-slug route (both by-id and
    # by-slug filter to published); admin lookup uses id via /admin/regions.
    assert admin.get(f"/regions/by-slug/test-region-{suffix}").status_code == 404

    # Publish → live + shows publicly.
    assert admin.post(f"/admin/regions/{rid}/publish").json()["status"] == "published"
    assert any(r["id"] == rid for r in admin.get("/regions").json())
    # Unpublish → draft again.
    assert admin.post(f"/admin/regions/{rid}/unpublish").json()["status"] == "draft"



# --- activity: actor names + search (WP-E) ---------------------------------

def test_activity_resolves_actor_and_search(admin, region_id):
    spot = _create_spot(admin, region_id)
    acts = admin.get("/admin/activity").json()
    entry = next((a for a in acts if a["target_id"] == spot["id"]), None)
    assert entry is not None
    assert entry["actor_email"]           # raw email retained
    assert entry["actor"]                 # resolved display (name or email)

    # Search by the spot name surfaces it; an unrelated query does not.
    hits = admin.get("/admin/activity", params={"q": spot["name"]}).json()
    assert any(a["target_id"] == spot["id"] for a in hits)
    miss = admin.get("/admin/activity", params={"q": "zzz-nomatch-zzz"}).json()
    assert all(a["target_id"] != spot["id"] for a in miss)
