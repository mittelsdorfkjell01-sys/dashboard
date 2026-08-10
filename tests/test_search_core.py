"""Pure-function search tests: text index, geocode classification, ranking,
clustering, colouring, sport filtering. No database, no network."""

from __future__ import annotations

from app.search.geocode import GeocodeResult, classify_geocode
from app.search.pins import build_pins, cluster_pins, value_to_color
from app.search.ranking import rank_nearby
from app.search.spatial import filter_spots_by_sport
from app.search.text import match_entities, normalize
from tests.search_helpers import FakeGeocoder, FakeScorer, make_region, make_spot


# --- text index ------------------------------------------------------------

def test_normalize_folds_accents_and_case():
    assert normalize("Kieler Bùcht") == "kieler bucht"


def test_match_entities_groups_and_matches_alias():
    laboe = make_spot("Laboe", 54.41, 10.22, ["kitesurf"], aliases=["Laboe Beach"])
    stein = make_spot("Stein", 54.45, 10.27, ["surf"])
    kiel = make_region("Kieler Bucht", country="DE", aliases=["Kiel"])

    by_name = match_entities("Laboe", [laboe, stein], [kiel])
    assert [s.slug for s in by_name["spots"]] == ["laboe"]
    assert by_name["regionen"] == []

    by_alias = match_entities("Laboe Beach", [laboe, stein], [kiel])
    assert [s.slug for s in by_alias["spots"]] == ["laboe"]

    region_hit = match_entities("kiel", [laboe, stein], [kiel])
    assert [r.slug for r in region_hit["regionen"]] == ["kieler-bucht"]


def test_match_entities_empty_query():
    laboe = make_spot("Laboe", 54.41, 10.22, ["kitesurf"])
    assert match_entities("", [laboe], []) == {"regionen": [], "spots": []}


# --- geocode classification ------------------------------------------------

def test_classify_geocode_point_for_town():
    geo = FakeGeocoder(
        {"laboe": [GeocodeResult("Laboe", 54.41, 10.22, feature_code="PPL")]}
    )
    out = classify_geocode("Laboe", geocoder=geo)
    assert out["type"] == "point"
    assert out["bounds"] is None
    assert out["point"] == {"lat": 54.41, "lon": 10.22}


def test_classify_geocode_area_for_island_uses_bounds():
    geo = FakeGeocoder(
        {"sardinia": [GeocodeResult("Sardinia", 40.0, 9.0, feature_code="ISL")]}
    )
    out = classify_geocode("Sardinia", geocoder=geo)
    assert out["type"] == "area"
    b = out["bounds"]
    assert b["min_lat"] < 40.0 < b["max_lat"]
    assert b["min_lon"] < 9.0 < b["max_lon"]


def test_classify_geocode_island_box_covers_spread_out_spots():
    # Regression: a large island's fallback bbox must actually contain its spots.
    # Sardinia's spots span lat ~39.2–41.2 around the geocoded centre (40, 9);
    # a too-small island box returned zero spots for "Sardinien".
    geo = FakeGeocoder(
        {"sardinia": [GeocodeResult("Sardinia", 40.0, 9.0, feature_code="ISL")]}
    )
    b = classify_geocode("Sardinia", geocoder=geo)["bounds"]
    for lat, lon in [(40.05, 8.37), (39.21, 9.16), (41.19, 9.17)]:  # the 3 spots
        assert b["min_lat"] <= lat <= b["max_lat"], (lat, b)
        assert b["min_lon"] <= lon <= b["max_lon"], (lon, b)


def test_classify_geocode_explicit_bbox_wins():
    geo = FakeGeocoder(
        {
            "sardinia": [
                GeocodeResult(
                    "Sardinia", 40.0, 9.0, feature_code="ISL",
                    bbox=[8.1, 38.85, 9.7, 41.3],
                )
            ]
        }
    )
    out = classify_geocode("Sardinia", geocoder=geo)
    assert out["bounds"] == {
        "min_lon": 8.1, "min_lat": 38.85, "max_lon": 9.7, "max_lat": 41.3
    }


def test_classify_geocode_no_results():
    assert classify_geocode("nowhere", geocoder=FakeGeocoder()) is None


def test_classify_geocode_country_prefers_area_for_region_creation():
    geo = FakeGeocoder({
        "fehmarn": [
            GeocodeResult("Fehmarn", 54.44, 11.19, feature_code="PPL", country="DE"),
            GeocodeResult("Fehmarn", 54.47, 11.14, feature_code="ISL", country="DE"),
        ]
    })
    out = classify_geocode("Fehmarn", geocoder=geo, country="de")
    assert out["type"] == "area"
    assert out["point"] == {"lat": 54.47, "lon": 11.14}


# --- ranking: score x distance damping -------------------------------------

def test_rank_nearby_orders_by_score_times_decay():
    near = make_spot("Near", 54.41, 10.22, ["kitesurf"], slug="near")
    far = make_spot("Far", 54.50, 10.40, ["kitesurf"], slug="far")
    scorer = FakeScorer({"near": 0.4, "far": 0.9})

    # near = 5 km / mediocre, far = 15 km / excellent; d0 = 40 km
    ranked = rank_nearby(
        [(near, 5_000), (far, 15_000)], None, None, scorer=scorer, d0_km=40.0
    )
    # the clearly better, somewhat farther spot moves ahead
    assert [r["spot"].slug for r in ranked] == ["far", "near"]
    assert ranked[0]["rank_score"] > ranked[1]["rank_score"]


def test_rank_nearby_distance_damping_breaks_ties():
    a = make_spot("A", 54.41, 10.22, ["kitesurf"], slug="a")
    b = make_spot("B", 54.42, 10.23, ["kitesurf"], slug="b")
    scorer = FakeScorer({"a": 0.7, "b": 0.7})  # equal score
    ranked = rank_nearby(
        [(a, 20_000), (b, 2_000)], None, None, scorer=scorer, d0_km=30.0
    )
    assert [r["spot"].slug for r in ranked] == ["b", "a"]  # nearer wins the tie


# --- pins: colouring + clustering ------------------------------------------

def test_value_to_color_tiers():
    assert value_to_color(0.9) == "green"
    assert value_to_color(0.6) == "lime"
    assert value_to_color(0.3) == "amber"
    assert value_to_color(0.1) == "grey"
    assert value_to_color(None) == "grey"


def test_build_pins_uses_scorer_value():
    spots = [
        make_spot("Hot", 54.41, 10.22, ["kitesurf"], slug="hot"),
        make_spot("Cold", 54.45, 10.27, ["kitesurf"], slug="cold"),
    ]
    scorer = FakeScorer({"hot": 0.9, "cold": 0.1})
    pins = build_pins(spots, None, None, scorer=scorer)
    colors = {p["slug"]: p["color"] for p in pins}
    assert colors == {"hot": "green", "cold": "grey"}


def test_cluster_pins_low_vs_high_zoom():
    spots = [
        make_spot("A", 54.41, 10.22, ["kitesurf"], slug="a"),
        make_spot("B", 54.42, 10.23, ["kitesurf"], slug="b"),
        make_spot("C", 54.90, 11.50, ["kitesurf"], slug="c"),
    ]
    pins = build_pins(spots, None, None, scorer=FakeScorer({}))

    high = cluster_pins(pins, zoom=12)
    assert len(high) == 3 and all(c["count"] == 1 for c in high)

    low = cluster_pins(pins, zoom=4)
    assert len(low) < 3  # nearby A/B merge into one cluster
    assert any(c["cluster"] and c["count"] >= 2 for c in low)


# --- sport toggle mechanism ------------------------------------------------

def test_filter_spots_by_sport_drops_flatwater_in_wave_mode():
    laboe = make_spot("Laboe", 54.41, 10.22, ["kitesurf", "windsurf"], slug="laboe")
    stein = make_spot("Stein", 54.45, 10.27, ["kitesurf", "surf"], slug="stein")

    all_spots = [laboe, stein]
    assert {s.slug for s in filter_spots_by_sport(all_spots, None)} == {"laboe", "stein"}
    # wave mode: flatwater-only Laboe falls out
    assert {s.slug for s in filter_spots_by_sport(all_spots, "surf")} == {"stein"}
