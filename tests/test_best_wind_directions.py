from app.admin.constants import validate_best_wind_directions
from app.seed.best_wind_research import BEST_WIND_RESEARCH
from app.seed.data import SPOTS
from app.seed.data_europe import SPOTS as EUROPE_SPOTS


def test_research_covers_every_seed_spot() -> None:
    seed_slugs = {spot["slug"] for spot in [*SPOTS, *EUROPE_SPOTS]}
    assert set(BEST_WIND_RESEARCH) == seed_slugs
    assert len(seed_slugs) == 51
    assert all(row["directions"] for row in BEST_WIND_RESEARCH.values())
    assert all(row["url"].startswith("https://") for row in BEST_WIND_RESEARCH.values())


def test_best_wind_directions_are_controlled_and_deduplicated() -> None:
    assert validate_best_wind_directions(["NE", "E", "NE"]) == ["NE", "E"]


def test_invalid_best_wind_direction_is_rejected() -> None:
    try:
        validate_best_wind_directions(["north-ish"])
    except ValueError as exc:
        assert "best_wind_directions" in str(exc)
    else:
        raise AssertionError("invalid direction must be rejected")

