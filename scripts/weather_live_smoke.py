"""Explicit, budgeted Open-Meteo smoke run; never stores provider values.

Usage (PowerShell):
  $env:WEATHER_LIVE_SMOKE='1'
  $env:WEATHER_SMOKE_SPOT_IDS='uuid,uuid,uuid'
  $env:WEATHER_SMOKE_MAX_CALLS='6'
  python scripts/weather_live_smoke.py
"""

from __future__ import annotations

import os
import json
import sys
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.live.cache import InMemoryCache
from app.live.client import HttpOpenMeteoClient
from app.live.service import get_forecast_series, get_live_conditions
from app.live.service import InvalidSpotCoordinates, _spot_coords
from app.models import Region, Spot
from sqlalchemy import select
from app.weather.budget import ProviderBudgetExceeded

MAX_RUN_REQUESTS = 400
MAX_DAILY_REQUESTS = 800
MAX_PER_MINUTE = 60
MAX_PARALLEL = 4


class SmokeBudget:
    """Counts every HTTP attempt, including retries, with a durable daily cap."""
    def __init__(self, run_limit: int, state_path: Path, mode: str) -> None:
        self.run_limit = min(run_limit, MAX_RUN_REQUESTS)
        self.state_path = state_path
        self.mode = mode
        self.run_count = 0
        self.minute: deque[float] = deque()
        self.lock = threading.Lock()
        self.day = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
        self.state = self._read()
        if self.state.get("day") != self.day:
            self.state = {"day": self.day, "requests": 0, "automated_runs": 0, "manual_runs": 0}
        if mode == "automated" and self.state.get("automated_runs", 0) >= 1:
            raise ProviderBudgetExceeded("automated full run already used today")
        if mode == "manual" and self.state.get("manual_runs", 0) >= 1:
            raise ProviderBudgetExceeded("manual second run already used today")
        key = "automated_runs" if mode == "automated" else "manual_runs"
        self.state[key] = self.state.get(key, 0) + 1
        self._write()

    def _read(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}

    def _write(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, sort_keys=True), encoding="utf-8")

    def consume(self) -> None:
        now = time.monotonic()
        with self.lock:
            while self.minute and self.minute[0] <= now - 60:
                self.minute.popleft()
            if len(self.minute) >= MAX_PER_MINUTE:
                raise ProviderBudgetExceeded("60 requests/minute smoke limit reached")
            if self.run_count >= self.run_limit:
                raise ProviderBudgetExceeded("per-run smoke limit reached")
            if self.state.get("requests", 0) >= MAX_DAILY_REQUESTS:
                raise ProviderBudgetExceeded("800 requests/day smoke limit reached")
            self.minute.append(now)
            self.run_count += 1
            self.state["requests"] = self.state.get("requests", 0) + 1
            self._write()


def main() -> int:
    if os.getenv("WEATHER_LIVE_SMOKE") != "1":
        print("SKIP: set WEATHER_LIVE_SMOKE=1 for an explicit live run")
        return 2
    raw_ids = [token.strip() for token in os.getenv("WEATHER_SMOKE_SPOT_IDS", "").split(",") if token.strip()]
    if not raw_ids:
        size = int(os.getenv("WEATHER_SMOKE_SIZE", "3"))
        if size not in {3, 20}:
            print("BLOCKED: WEATHER_SMOKE_SIZE must be 3 or 20")
            return 2
        with SessionLocal() as db:
            rows = db.execute(select(Spot, Region).outerjoin(Region, Spot.region_id == Region.id).where(Spot.status == "published").order_by(Region.country, Spot.name)).all()
            valid = []
            for spot, region in rows:
                try:
                    _spot_coords(spot)
                except (InvalidSpotCoordinates, TypeError, ValueError):
                    continue
                valid.append((spot.id, region.country if region else None))
            selected = []
            for country in ("DE", "NL", "DK"):
                match = next((spot_id for spot_id, code in valid if code == country and spot_id not in selected), None)
                if match:
                    selected.append(match)
            selected.extend(spot_id for spot_id, _ in valid if spot_id not in selected)
            spot_ids = selected[:size]
        if len(spot_ids) < min(3, size):
            print("BLOCKED: fewer than three published canonical spots with valid coordinates")
            return 2
    else:
        try:
            spot_ids = [uuid.UUID(token) for token in raw_ids]
        except ValueError:
            print("BLOCKED: invalid UUID in WEATHER_SMOKE_SPOT_IDS")
            return 2
    try:
        max_calls = int(os.getenv("WEATHER_SMOKE_MAX_CALLS", "400"))
    except ValueError:
        print("BLOCKED: invalid WEATHER_SMOKE_MAX_CALLS")
        return 2
    worst_case_calls = len(spot_ids) * 2 * 3  # two endpoints, up to three attempts
    if max_calls < worst_case_calls or max_calls <= 0 or max_calls > MAX_RUN_REQUESTS:
        print(f"BLOCKED: budget must cover retry worst case {worst_case_calls} and be <= {MAX_RUN_REQUESTS}")
        return 2

    started = time.monotonic()
    summaries: list[dict] = []
    try:
        mode = os.getenv("WEATHER_SMOKE_MODE", "manual")
        if mode not in {"manual", "automated"}:
            raise ValueError("WEATHER_SMOKE_MODE must be manual or automated")
        budget = SmokeBudget(max_calls, Path(os.getenv("WEATHER_SMOKE_BUDGET_FILE", "data/weather-smoke-budget.json")), mode)
        client = HttpOpenMeteoClient(budget=budget)
        cache = InMemoryCache()
        def check(spot_id: uuid.UUID) -> dict:
            with SessionLocal() as db:
                current = get_live_conditions(spot_id, db=db, client=client, cache=cache)
                forecast = get_forecast_series(spot_id, 10, db=db, client=client, cache=cache)
            days = forecast.get("days") or []
            hours = [hour for day in days for hour in (day.get("hours") or [])]
            invalid = sum(
                1 for hour in hours
                if hour.get("wind_ms") is not None and (
                    hour["wind_ms"] < 0 or hour.get("dir") is None or not 0 <= hour["dir"] < 360
                    or (hour.get("gust_ms") is not None and hour["gust_ms"] < hour["wind_ms"])
                )
            )
            detail_mismatches = [
                i + 1
                for i, day in enumerate(days)
                if day.get("detail") != ("hourly" if i < 5 else "trend")
            ]
            if len(days) != 10 or detail_mismatches or invalid:
                raise RuntimeError(
                    "contract invariant failed for spot "
                    f"{spot_id}: days={len(days)} "
                    f"detail_mismatches={detail_mismatches} invalid_values={invalid}"
                )
            return {
                "spot_id": str(spot_id), "models": len(forecast.get("models") or []),
                "days": len(days), "detail_hours": len(hours),
                "current_resolution": current.get("resolution"), "invalid_values": invalid,
            }
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(spot_ids))) as pool:
            futures = {pool.submit(check, spot_id): spot_id for spot_id in spot_ids}
            for future in as_completed(futures):
                summaries.append(future.result())
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(f"PASS: spots={len(summaries)} requests={budget.run_count} limit={budget.run_limit} duration_s={time.monotonic()-started:.1f}")
    for summary in summaries:
        print("META:", " ".join(f"{key}={value}" for key, value in summary.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
