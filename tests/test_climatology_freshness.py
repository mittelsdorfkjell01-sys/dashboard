from datetime import date
from types import SimpleNamespace

from app.era5.freshness import (
    CLIMATOLOGY_ALGORITHM_VERSION,
    CLIMATOLOGY_SCHEMA_VERSION,
    expected_window,
    finalize_record,
    mark_stale,
    stale_reasons,
    state,
)


CELL = {"wind": [54.5, 10.25], "wave": [54.5, 10.0]}


def _spot(record=None, cell=None):
    return SimpleNamespace(climatology=record, era5_cell=cell or CELL)


def test_expected_window_uses_the_last_20_complete_years():
    assert expected_window(date(2026, 1, 31)) == "2005-2024"
    assert expected_window(date(2026, 2, 1)) == "2006-2025"
    assert expected_window(date(2027, 6, 1)) == "2007-2026"


def test_finalized_snapshot_is_current_for_matching_inputs():
    record = finalize_record(
        {
            "window": "2006-2025",
            "weeks": [{"week": 1}],
            "smoothing": {"window_weeks": 3},
        },
        CELL,
    )
    spot = _spot(record)

    assert record["schema_version"] == CLIMATOLOGY_SCHEMA_VERSION
    assert record["algorithm_version"] == CLIMATOLOGY_ALGORITHM_VERSION
    assert state(spot, today=date(2026, 8, 6)) == "current"
    assert stale_reasons(spot, today=date(2026, 8, 6)) == []


def test_new_year_and_grid_cell_changes_make_snapshot_stale():
    record = finalize_record(
        {
            "window": "2006-2025",
            "weeks": [{"week": 1}],
            "smoothing": {"window_weeks": 3},
        },
        CELL,
    )
    spot = _spot(record, {"wind": [55.0, 11.0], "wave": [55.0, 11.0]})

    assert stale_reasons(spot, today=date(2027, 2, 1)) == [
        "data_window",
        "grid_cell",
    ]
    assert state(spot, today=date(2027, 2, 1)) == "stale"


def test_mark_stale_keeps_existing_weekly_values():
    original = {"weeks": [{"week": 1, "wind": {"p50": 12}}]}
    marked = mark_stale(original, "grid_cell")

    assert marked is not original
    assert marked["weeks"] == original["weeks"]
    assert marked["freshness"]["status"] == "stale"
    assert marked["freshness"]["reasons"] == ["grid_cell"]
