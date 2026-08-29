import pytest

from app.weather.budget import ProviderBudgetExceeded, RequestBudget


def test_daily_budget_warns_at_70_percent_and_soft_stops_at_80(caplog):
    budget = RequestBudget(per_minute=100, per_hour=100, per_day=10, clock=lambda: 1.0)
    for _ in range(7):
        budget.consume()
    assert "70%" in caplog.text
    budget.consume()
    with pytest.raises(ProviderBudgetExceeded):
        budget.consume()
