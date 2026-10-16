from scripts.weather_field_load_test import percentile


def test_load_test_percentile_is_nearest_rank() -> None:
    assert percentile([5, 1, 4, 2, 3], 0.5) == 3
    assert percentile(list(range(1, 101)), 0.95) == 95
