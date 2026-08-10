import json

import pytest

from app.weather.budget import ProviderBudgetExceeded
from scripts.weather_live_smoke import MAX_DAILY_REQUESTS, SmokeBudget


def test_smoke_budget_counts_attempts_and_caps_run(tmp_path):
    budget = SmokeBudget(2, tmp_path / "budget.json", "manual")
    budget.consume()
    budget.consume()
    with pytest.raises(ProviderBudgetExceeded, match="per-run"):
        budget.consume()


def test_smoke_budget_persists_daily_count_and_run_policy(tmp_path):
    path = tmp_path / "budget.json"
    first = SmokeBudget(10, path, "automated")
    first.consume()
    with pytest.raises(ProviderBudgetExceeded, match="automated"):
        SmokeBudget(10, path, "automated")
    state = json.loads(path.read_text(encoding="utf-8"))
    state["requests"] = MAX_DAILY_REQUESTS
    path.write_text(json.dumps(state), encoding="utf-8")
    manual = SmokeBudget(10, path, "manual")
    with pytest.raises(ProviderBudgetExceeded, match="day"):
        manual.consume()
