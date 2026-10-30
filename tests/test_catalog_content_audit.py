from scripts.catalog_content_audit import description_warnings, runtime_inventory, seed_inventory


def test_seed_inventory_keeps_drafts_and_published_separate():
    result = seed_inventory()
    assert result["spots"]["combined_unique"] == 51
    assert result["spots"]["by_status"] == {"draft": 40, "published": 11}


def test_runtime_inventory_counts_public_coverage_without_claiming_pending():
    spots = [{
        "slug": "sample", "status": "published", "origin": "editorial",
        "region_country": "DE", "sports": ["kitesurf", "wing"],
    }]
    regions = [{
        "slug": "region", "status": "published", "season": None,
        "description": None, "image": {"url": "https://placeholder.local/region.jpg"},
        "spot_count": 1,
    }]
    details = [{
        **spots[0], "level": ["advanced"],
        "editorial": {"description": "Einsteigerfreundlicher Spot."},
        "variant_conditions": {}, "image": {"license": "CC BY"},
    }]
    result = runtime_inventory(spots, regions, details)
    assert result["community_pending"] == "unknown_not_publicly_exposed"
    assert result["spots"]["country_sport_matrix"]["DE"] == {
        "kitesurf": 1, "spots": 1, "wing": 1,
    }
    assert result["regions"]["without_season"] == 1
    assert result["regions"]["placeholder_or_example_image"] == 1
    assert result["spots"]["content_warnings"][0]["warnings"] == [
        "content.level.beginner_mentioned_but_not_structured"
    ]


def test_known_supertubos_copy_conflict_is_detected():
    warnings = description_warnings({
        "slug": "peniche-supertubos",
        "level": ["advanced"],
        "editorial": {"description": "Lagunen der Ria Formosa nahe Tavira."},
    })
    assert "content.description.known_geography_conflict" in warnings
