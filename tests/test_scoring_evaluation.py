from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest

from app.scoring.params import get_params
from app.scoring.personal.backtest import (
    HistoricalHour,
    SeasonPrediction,
    SURFACES,
    TruthHour,
    evaluate_backtest,
    evaluate_season_backtest,
    profile_archetypes,
)
from app.scoring.personal.calibration import band_factor_proposal
from app.scoring.personal.metrics import recommendation_quality
from app.scoring.personal.social import bayesian_positive_share


def _hours() -> list[HistoricalHour]:
    start = datetime(2026, 7, 1, 10, tzinfo=timezone.utc)
    return [
        HistoricalHour(
            spot_id="spot-a",
            valid_at=start + timedelta(hours=offset),
            surface=surface,
            forecast_wind_kt=17,
            truth_wind_kt=17,
            confidence=0.8,
        )
        for surface in SURFACES
        for offset in range(3)
    ]


def test_backtest_calculates_every_surface_and_archetype() -> None:
    params = get_params("kitesurf")
    profiles = profile_archetypes(params)
    rows = evaluate_backtest(_hours(), profiles=profiles, params=params, k=5)

    assert len(rows) == len(SURFACES) * len(profiles)
    average = next(row for row in rows if row.surface == "now" and row.archetype == "average")
    assert average.available is True
    assert average.precision_at_k == 1.0
    assert average.confidence_brier == pytest.approx(0.04)
    assert average.confidence_calibration_error == pytest.approx(0.2)
    assert average.coverage == 1.0
    assert average.recommendation_count == 1


def test_backtest_fixture_cli_runs_without_database(tmp_path: Path) -> None:
    fixture = tmp_path / "hours.json"
    fixture.write_text(json.dumps([
        {
            **asdict(row),
            "valid_at": row.valid_at.isoformat(),
        }
        for row in _hours()
    ], default=str), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/scoring_backtest.py", "--fixture", str(fixture), "--k", "3"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["metrics"]) == 25
    assert any(row["surface"] == "season" and row["available"] for row in payload["metrics"])


def test_season_backtest_uses_v3_probability_without_archive_lookahead() -> None:
    params = get_params("kitesurf")
    profiles = {"average": profile_archetypes(params)["average"]}
    start = datetime(2026, 7, 6, 10, tzinfo=timezone.utc)
    predictions = {
        "average": [
            SeasonPrediction("spot-a", start.isocalendar().week, 0.8, 2025),
            SeasonPrediction("spot-leaky", start.isocalendar().week, 0.95, 2026),
        ]
    }
    truth = [
        TruthHour("spot-a", start + timedelta(hours=offset), 17)
        for offset in range(3)
    ] + [
        TruthHour("spot-leaky", start + timedelta(hours=offset), 17)
        for offset in range(3)
    ]

    metric = evaluate_season_backtest(
        predictions,
        truth,
        profiles=profiles,
        params=params,
        k=1,
    )[0]

    assert metric.available is True
    assert metric.precision_at_k == 1.0
    assert metric.recommendation_count == 1
    assert metric.confidence_brier == pytest.approx(0.04)


def test_social_signal_shrinks_and_enforces_minimum_group() -> None:
    hidden = bayesian_positive_share(
        [("a", True), ("b", False)], min_group_size=3,
    )
    assert hidden.available is False
    assert hidden.score == 0.5

    visible = bayesian_positive_share(
        [("a", False), ("a", True), ("b", True), ("c", False)],
        min_group_size=3,
    )
    assert visible.available is True
    assert visible.group_size == 3
    assert visible.positive_count == 2
    assert visible.score == pytest.approx(4.5 / 8)


def test_band_calibration_requires_sample_floor_and_uses_worthwhile_rows() -> None:
    current = {
        "k_board": {"twintip": 2.2, "foil": 1.4},
        "f_lo": 0.8,
        "f_hi": 1.35,
    }
    sample = {
        "outcome": "worthwhile",
        "weight_kg": 80,
        "kite_size": 10,
        "board_type": "twintip",
        "wind_kt": 18,
    }
    assert band_factor_proposal([sample], current, minimum_checkins=2)["eligible"] is False
    result = band_factor_proposal(
        [sample, {**sample, "wind_kt": 20}, {**sample, "outcome": "not_worthwhile"}],
        current,
        minimum_checkins=2,
    )
    assert result["eligible"] is True
    assert result["sample_count"] == 2
    assert result["proposal"]["k_board"]["twintip"] == pytest.approx(2.375)


class _FakeMetricsDb:
    def __init__(self, logs: list, events: list) -> None:
        self.values = iter((logs, events))

    def scalars(self, _statement):
        return next(self.values)


def test_online_metrics_are_segmented_by_surface_and_params_version() -> None:
    now = datetime.now(timezone.utc)
    log_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    spot_id = uuid.uuid4()
    log = SimpleNamespace(
        id=log_id,
        spot_id=spot_id,
        surface="now",
        audience_segment="logged_profile",
        params_version=4,
        app_user_id=actor_id,
        created_at=now - timedelta(minutes=10),
    )
    events = [
        SimpleNamespace(
            recommendation_log_id=log_id,
            app_user_id=actor_id,
            anon_id=None,
            spot_id=spot_id,
            surface="now",
            type=event_type,
            context={"outcome": "worthwhile"} if event_type == "session_checkin" else {},
            created_at=now - timedelta(minutes=5),
        )
        for event_type in ("impression", "click", "favorite_add", "session_checkin")
    ]
    result = recommendation_quality(_FakeMetricsDb([log], events), days=30)
    assert result["rows"] == [{
        "surface": "now",
        "audience": "logged_profile",
        "params_version": 4,
        "impressions": 1,
        "ctr": 1.0,
        "favorite_rate": 1.0,
        "checkin_rate": 1.0,
        "worthwhile_share": 1.0,
        "checkins_with_outcome": 1,
    }]
