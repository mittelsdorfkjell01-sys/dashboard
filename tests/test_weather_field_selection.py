from app.spatial_fields.selection import bounds_in_coverage, point_in_coverage, rank_model_candidates


MODELS = [
    {
        "key": "icon-d2",
        "priority": 5,
        "freshness": "fresh",
        "coverage": {"west": -3.5, "south": 43.0, "east": 20.5, "north": 58.0},
    },
    {
        "key": "icon-eu",
        "priority": 10,
        "freshness": "fresh",
        "coverage": {"west": -23.5, "south": 29.5, "east": 45.0, "north": 70.5},
    },
    {
        "key": "gfs-0p25",
        "priority": 20,
        "freshness": "fresh",
        "coverage": {"west": -180.0, "south": -85.0, "east": 180.0, "north": 85.0},
    },
]


def _rank(latitude: float, longitude: float, requested_model: str | None = None):
    return rank_model_candidates(
        [dict(item) for item in MODELS],
        latitude=latitude,
        longitude=longitude,
        requested_model=requested_model,
        primary_model="icon-eu",
    )


def test_geographic_priority_is_d2_then_icon_eu_then_global_gfs() -> None:
    assert _rank(50.0, 8.0)[0]["key"] == "icon-d2"
    assert _rank(38.0, -9.0)[0]["key"] == "icon-eu"
    assert _rank(-34.0, 18.0)[0]["key"] == "gfs-0p25"


def test_stale_regional_model_falls_behind_healthy_covering_model() -> None:
    models = [dict(item) for item in MODELS]
    models[0]["freshness"] = "stale"

    ranked = rank_model_candidates(
        models,
        latitude=50.0,
        longitude=8.0,
        requested_model=None,
        primary_model="icon-eu",
    )

    assert ranked[0]["key"] == "icon-eu"
    assert ranked[-1]["key"] == "icon-d2"


def test_manual_model_stays_first_even_outside_its_coverage() -> None:
    ranked = _rank(-34.0, 18.0, requested_model="icon-d2")

    assert ranked[0]["key"] == "icon-d2"
    assert ranked[0]["covers_point"] is False
    assert ranked[1]["key"] == "gfs-0p25"


def test_coverage_edges_are_inclusive() -> None:
    assert point_in_coverage(MODELS[0]["coverage"], latitude=43.0, longitude=-3.5)
    assert point_in_coverage(MODELS[0]["coverage"], latitude=58.0, longitude=20.5)


def test_viewport_selection_uses_smallest_model_covering_the_whole_map() -> None:
    ranked = rank_model_candidates(
        [dict(item) for item in MODELS],
        latitude=48.0,
        longitude=4.0,
        requested_model=None,
        primary_model="icon-eu",
        bounds={"west": -8.0, "south": 36.0, "east": 16.0, "north": 60.0},
    )

    assert ranked[0]["key"] == "icon-eu"
    assert ranked[0]["covers_viewport"] is True
    assert ranked[1]["key"] == "gfs-0p25"
    assert ranked[-1]["key"] == "icon-d2"


def test_viewport_coverage_edges_are_inclusive() -> None:
    assert bounds_in_coverage(MODELS[1]["coverage"], MODELS[0]["coverage"])


def test_viewport_selection_tolerates_small_camera_overscan() -> None:
    coverage = {"west": -10.5, "south": 30.0, "east": 42.0, "north": 66.0}

    assert bounds_in_coverage(
        coverage,
        {"west": -10.65, "south": 48.0, "east": 20.0, "north": 60.0},
    )
    assert not bounds_in_coverage(
        coverage,
        {"west": -11.0, "south": 48.0, "east": 20.0, "north": 60.0},
    )
