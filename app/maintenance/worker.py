"""Single-VPS scheduler for provider, retention, and calibration workloads."""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
stopping = False


@dataclass
class Task:
    name: str
    interval: int
    run: Callable[[], Any]
    next_run: float


def _with_db(function: Callable[..., Any]) -> Any:
    with SessionLocal() as db:
        return function(db=db)


def _shadow_worker() -> Any:
    from app.weather.shadow_jobs import run_next_shadow_cycle

    return run_next_shadow_cycle()


def _live_wind_worker() -> Any:
    from app.weather.live_wind_jobs import run_live_wind_worker

    return run_live_wind_worker()


def _tide_worker() -> Any:
    from app.tides.worker import TideWorker

    return TideWorker().process_queue()


def _forecast_refresh_worker() -> Any:
    from app.forecast.refresh_worker import run_refresh_cycle

    return _with_db(run_refresh_cycle)


def _weather_field_health_monitor() -> dict:
    from app.config import get_settings
    from app.spatial_fields.doctor import build_weather_field_doctor_report
    from app.spatial_fields.storage import configured_field_storage

    settings = get_settings()
    storage = configured_field_storage()
    with SessionLocal() as db:
        report = build_weather_field_doctor_report(
            db,
            storage=storage,
            settings=settings,
            require_public=False,
        )
    result = {
        "status": report["status"],
        "wind": report["wind"]["status"],
        "waves": report["waves"]["status"],
        "spot_sync": report["spot_sync"]["status"],
        "alerts": len(report["alerts"]),
    }
    extra = {
        "weather_event": "weather_field_doctor",
        "weather_status": report["status"],
        "weather_alert_codes": [item["code"] for item in report["alerts"]],
    }
    if report["status"] == "error":
        logger.error("weather field doctor found critical alerts", extra=extra)
    elif report["status"] == "degraded":
        logger.warning("weather field doctor found warnings", extra=extra)
    return result


def _tasks(now: float) -> list[Task]:
    from app.api import cron
    from app.config import get_settings

    settings = get_settings()

    return [
        Task("observations", 15 * 60, lambda: _with_db(cron.collect_observations), now),
        Task("live-wind-enqueue", 15 * 60, lambda: _with_db(cron.enqueue_live_wind), now + 20),
        Task("live-wind-worker", 60, _live_wind_worker, now + 30),
        Task("weather-shadow-enqueue", 6 * 60 * 60, lambda: _with_db(cron.collect_weather_shadow), now + 60),
        Task("weather-shadow-worker", 5 * 60, _shadow_worker, now + 90),
        Task(
            "weather-fields-enqueue",
            settings.weather_field_discovery_interval_seconds,
            lambda: _with_db(cron.enqueue_weather_fields),
            now + 100,
        ),
        Task(
            "weather-fields-health",
            getattr(settings, "weather_field_health_interval_seconds", 15 * 60),
            _weather_field_health_monitor,
            now + 110,
        ),
        Task(
            "forecast-refresh",
            settings.forecast_refresh_interval_seconds,
            _forecast_refresh_worker,
            now + 120,
        ),
        Task("climatology", 6 * 60 * 60, lambda: _with_db(cron.maintain_climatology), now + 150),
        Task("build-sectors", 6 * 60 * 60, lambda: _with_db(cron.build_sectors), now + 5 * 60),
        Task("wind-climatology", 6 * 60 * 60, lambda: _with_db(cron.maintain_wind_climatology), now + 8 * 60),
        Task("station-catalog", 24 * 60 * 60, lambda: _with_db(cron.refresh_station_catalog), now + 10 * 60),
        Task("verification", 24 * 60 * 60, lambda: _with_db(cron.run_verification), now + 15 * 60),
        Task("tides", 6 * 60 * 60, _tide_worker, now + 20 * 60),
    ]


def _stop(_signum, _frame) -> None:
    global stopping
    stopping = True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    tasks = _tasks(time.monotonic())
    logger.info("maintenance worker started with %d tasks", len(tasks))
    while not stopping:
        now = time.monotonic()
        for task in tasks:
            if now < task.next_run:
                continue
            started = time.monotonic()
            try:
                result = task.run()
                logger.info("maintenance task %s completed: %s", task.name, result)
            except Exception:
                logger.exception("maintenance task %s failed", task.name)
            finally:
                task.next_run = started + task.interval
        time.sleep(5)


if __name__ == "__main__":
    main()
