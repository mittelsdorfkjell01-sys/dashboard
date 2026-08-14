import inspect
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.models import ForecastProcessingJob, ForecastSnapshot
from app.weather.shadow_metrics import (
    aggregate_observations,
    circular_error,
    lead_band,
    verification_metrics,
)


def test_lead_bands_and_circular_direction_error():
    assert [lead_band(x) for x in (0, 25, 49, 73, 121, 241)] == [
        "0-24h",
        "25-48h",
        "49-72h",
        "73-120h",
        "121-240h",
        None,
    ]
    assert circular_error(355, 5) == 10


def test_observation_aggregation_is_vectorial_and_gust_is_maximum():
    result = aggregate_observations(
        [
            {
                "quality_status": "valid",
                "wind_speed_ms": 10,
                "wind_direction_deg": 350,
                "wind_gust_ms": 13,
            },
            {
                "quality_status": "valid",
                "wind_speed_ms": 10,
                "wind_direction_deg": 10,
                "wind_gust_ms": 15,
            },
            {
                "quality_status": "suspect",
                "wind_speed_ms": 99,
                "wind_direction_deg": 180,
                "wind_gust_ms": 99,
            },
        ]
    )
    assert result["wind_direction_deg"] == pytest.approx(0, abs=1e-6)
    assert result["wind_gust_ms"] == 15 and result["sample_count"] == 2


def test_metrics_include_counts_vectors_gusts_and_event_matrix():
    pairs = [
        (
            {
                "wind_speed_ms": 8,
                "wind_gust_ms": 10,
                "wind_direction_deg": 0,
                "u_ms": 0,
                "v_ms": -8,
            },
            {
                "wind_speed_ms": 7.5,
                "wind_gust_ms": 9,
                "wind_direction_deg": 350,
                "u_ms": 1.2,
                "v_ms": -7.4,
            },
        )
    ]
    result = verification_metrics(pairs)
    assert result["sample_count"] == 1 and result["speed"]["bias"] == 0.5
    assert result["direction_mae_deg"] == 10 and result["gust"]["mae"] == 1
    assert result["event_14kn"]["hits"] == 1


def test_public_forecast_modules_do_not_import_shadow_study():
    from app.forecast import publisher
    from app.live import service

    assert "weather.shadow_study" not in inspect.getsource(publisher)
    assert "weather.shadow_study" not in inspect.getsource(service)


def test_phase4_admin_requires_auth(anon_client):
    assert anon_client.get("/admin/weather/shadow-study/status").status_code in (
        401,
        403,
    )


def test_shadow_cron_contract_and_deduplication(anon_client, db, monkeypatch):
    db.execute(
        delete(ForecastProcessingJob).where(
            ForecastProcessingJob.kind == "weather_shadow_cycle"
        )
    )
    db.commit()
    monkeypatch.setattr(get_settings(), "cron_secret", "shadow-test-secret")
    assert anon_client.get("/cron/weather-shadow").status_code == 405
    assert anon_client.post("/cron/weather-shadow").status_code == 401
    assert (
        anon_client.post(
            "/cron/weather-shadow",
            headers={"Authorization": "Bearer wrong-secret"},
        ).status_code
        == 401
    )
    headers = {"Authorization": "Bearer shadow-test-secret"}
    started = time.perf_counter()
    first = anon_client.post("/cron/weather-shadow", headers=headers)
    assert time.perf_counter() - started < 2
    second = anon_client.post("/cron/weather-shadow", headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "deduplicated"
    assert first.json()["job_id"] == second.json()["job_id"]
    assert "secret" not in first.text.lower()
    db.expire_all()
    assert (
        db.scalar(
            select(func.count())
            .select_from(ForecastProcessingJob)
            .where(ForecastProcessingJob.kind == "weather_shadow_cycle")
        )
        == 1
    )


def test_shadow_cron_parallel_retry_is_race_safe(anon_client, db, monkeypatch):
    db.execute(
        delete(ForecastProcessingJob).where(
            ForecastProcessingJob.kind == "weather_shadow_cycle"
        )
    )
    db.commit()
    monkeypatch.setattr(get_settings(), "cron_secret", "parallel-test-secret")
    headers = {"Authorization": "Bearer parallel-test-secret"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: anon_client.post("/cron/weather-shadow", headers=headers),
                range(2),
            )
        )
    assert all(response.status_code == 202 for response in responses)
    assert {response.json()["status"] for response in responses} <= {
        "accepted",
        "deduplicated",
    }
    db.expire_all()
    assert (
        db.scalar(
            select(func.count())
            .select_from(ForecastProcessingJob)
            .where(ForecastProcessingJob.kind == "weather_shadow_cycle")
        )
        == 1
    )


def test_new_model_generation_gets_new_job(db):
    from app.weather.shadow_jobs import enqueue_shadow_cycle

    db.execute(
        delete(ForecastProcessingJob).where(
            ForecastProcessingJob.kind == "weather_shadow_cycle"
        )
    )
    db.commit()
    first, created_a = enqueue_shadow_cycle(
        db, now=datetime(2026, 8, 14, 6, 41, tzinfo=timezone.utc)
    )
    second, created_b = enqueue_shadow_cycle(
        db, now=datetime(2026, 8, 14, 12, 41, tzinfo=timezone.utc)
    )
    assert created_a and created_b and first.id != second.id


def test_worker_claims_once_and_never_changes_public_snapshots(db, monkeypatch):
    from app.weather.shadow_jobs import enqueue_shadow_cycle, run_next_shadow_cycle

    db.execute(
        delete(ForecastProcessingJob).where(
            ForecastProcessingJob.kind == "weather_shadow_cycle"
        )
    )
    db.commit()
    enqueue_shadow_cycle(db, now=datetime(2026, 8, 14, 18, 41, tzinfo=timezone.utc))
    before = db.scalar(
        select(func.count())
        .select_from(ForecastSnapshot)
        .where(ForecastSnapshot.active.is_(True))
    )
    collected_runs = []
    monkeypatch.setattr(
        "scripts.weather_phase4_initial.main",
        lambda **kwargs: (
            collected_runs.append(kwargs["model_run_override"])
            or {
                "status": "collecting",
                "forecast_points": 5,
                "requests": 0,
                "bytes": 0,
            }
        ),
    )
    assert run_next_shadow_cycle()["status"] == "succeeded"
    assert run_next_shadow_cycle()["status"] == "idle"
    db.expire_all()
    job = db.scalar(
        select(ForecastProcessingJob).where(
            ForecastProcessingJob.kind == "weather_shadow_cycle"
        )
    )
    after = db.scalar(
        select(func.count())
        .select_from(ForecastSnapshot)
        .where(ForecastSnapshot.active.is_(True))
    )
    assert job.status == "succeeded" and job.attempt_count == 1
    assert collected_runs == [datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)]
    assert before == after and job.diagnostics["public_effect"] == "none"


def test_failed_worker_retry_is_bounded(db, monkeypatch):
    from app.weather.shadow_jobs import enqueue_shadow_cycle, run_next_shadow_cycle

    db.execute(
        delete(ForecastProcessingJob).where(
            ForecastProcessingJob.kind == "weather_shadow_cycle"
        )
    )
    db.commit()
    enqueue_shadow_cycle(db, now=datetime(2026, 8, 14, 18, 41, tzinfo=timezone.utc))

    def fail(**_kwargs):
        raise RuntimeError("synthetic provider failure")

    monkeypatch.setattr("scripts.weather_phase4_initial.main", fail)
    assert [run_next_shadow_cycle()["status"] for _ in range(3)] == [
        "failed",
        "failed",
        "failed",
    ]
    assert run_next_shadow_cycle()["status"] == "idle"
    db.expire_all()
    job = db.scalar(
        select(ForecastProcessingJob).where(
            ForecastProcessingJob.kind == "weather_shadow_cycle"
        )
    )
    assert job.attempt_count == 3
    assert job.diagnostics["retryable"] is False
    assert job.error == "RuntimeError"
