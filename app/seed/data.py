"""Static seed fixtures: 2 European regions and ~6 spots.

No climatology / score yet (out of scope for Sprint 1) — just identity,
coordinates and sport metadata. Coordinates are (lon, lat) WGS84.
"""


def _img(slug: str, *, kind: str = "region"):
    """Placeholder hero for a fixture — see ``data_europe._img``.

    The unreachable ``*.local`` host is deliberate: the frontend shows its
    no-image state for it and ``image_ready`` does not count it as done. These
    used to be ``example.com`` URLs, which are not recognised as placeholders
    and therefore rendered as broken images.
    """
    from app.media.image_object import placeholder_image

    return placeholder_image(slug, kind=kind)


REGIONS: list[dict] = [
    {
        "slug": "tarifa",
        "name": "Tarifa",
        "country": "ES",
        "center": (-5.6035, 36.0128),  # lon, lat
        # Rough bounding box around the Strait of Gibraltar coast.
        "bounds": [
            (-5.80, 35.95),
            (-5.40, 35.95),
            (-5.40, 36.10),
            (-5.80, 36.10),
            (-5.80, 35.95),  # closing point
        ],
        "description": "Wind capital of Europe on the Strait of Gibraltar, "
        "famous for reliable Levante and Poniente winds.",
        "season": {"best_months": [4, 5, 6, 7, 8, 9]},
        "defaults": {"model_pref": "icon"},
        "image": _img("tarifa"),
    },
    {
        "slug": "sardinia",
        "name": "Sardinia",
        "country": "IT",
        "center": (8.9000, 39.2000),
        "bounds": [
            (8.10, 38.85),
            (9.70, 38.85),
            (9.70, 41.30),
            (8.10, 41.30),
            (8.10, 38.85),
        ],
        "description": "Mediterranean island with varied coastlines and the "
        "strong Mistral wind on the west coast.",
        "season": {"best_months": [5, 6, 7, 8, 9]},
        "defaults": {"model_pref": "icon", "aliases": ["Sardegna"]},
        "image": _img("sardinia"),
    },
    {
        "slug": "kieler-bucht",
        "name": "Kieler Bucht",
        "country": "DE",
        "center": (10.2000, 54.4000),
        # Box around the Kiel bight on the German Baltic coast.
        "bounds": [
            (10.00, 54.20),
            (11.30, 54.20),
            (11.30, 54.60),
            (10.00, 54.60),
            (10.00, 54.20),
        ],
        "description": "Baltic bight around Kiel — a cluster of flatwater and "
        "wave spots that fire on north-easterly winds.",
        "season": {"best_months": [4, 5, 6, 9, 10]},
        "defaults": {"model_pref": "icon_d2", "aliases": ["Kiel", "Kiel Bay"]},
        "image": _img("kieler-bucht"),
    },
]

# region_slug links each spot to its region.
SPOTS: list[dict] = [
    {
        "slug": "tarifa-los-lances",
        "name": "Los Lances",
        "region_slug": "tarifa",
        "location": (-5.6280, 36.0250),
        "sports": ["kitesurf", "windsurf"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "beginner",
        "water_character": "chop",
        "style": ["freeride"],
        "status": "published",
        "facing": 225,
    },
    {
        "slug": "tarifa-valdevaqueros",
        "name": "Valdevaqueros",
        "region_slug": "tarifa",
        "location": (-5.7000, 36.0640),
        "sports": ["kitesurf", "windsurf"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "advanced",
        "water_character": "chop",
        "style": ["freeride", "freestyle", "big_air"],
        "status": "published",
        "facing": 250,
    },
    {
        "slug": "tarifa-balneario",
        "name": "Balneario",
        "region_slug": "tarifa",
        "location": (-5.6060, 36.0080),
        "sports": ["windsurf"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "advanced",
        "water_character": "chop",
        "style": ["freeride"],
        "status": "published",
        "facing": 135,
    },
    {
        "slug": "sardinia-porto-pollo",
        "name": "Porto Pollo",
        "region_slug": "sardinia",
        "location": (9.1670, 41.1880),
        "sports": ["kitesurf", "windsurf"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "beginner",
        "water_character": "flach",
        "style": ["freeride", "freestyle"],
        "facilities": {
            "parking": {"available": True},
            "school": {"available": True, "note": "Verleih und Kurse direkt am Spot."},
            "food": {"available": True},
        },
        "status": "published",
        "facing": 315,
    },
    {
        "slug": "sardinia-capo-mannu",
        "name": "Capo Mannu",
        "region_slug": "sardinia",
        "location": (8.3690, 40.0480),
        "sports": ["surf", "windsurf"],
        "water_type": "ocean",
        "bottom_type": "reef",
        "level": "advanced",
        "water_character": "welle_gross",
        "style": ["wave_riding"],
        "status": "published",
        "facing": 290,
    },
    {
        "slug": "sardinia-poetto",
        "name": "Poetto",
        "region_slug": "sardinia",
        "location": (9.1620, 39.2050),
        "sports": ["kitesurf", "windsurf", "wing"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "beginner",
        "water_character": "chop",
        "style": ["freeride", "freestyle"],
        "status": "published",
        "facing": 135,
    },
    # --- Kieler Bucht (Baltic) — clustered spots for nearby/ranking/toggle ---
    {
        "slug": "laboe",
        "name": "Laboe",
        "region_slug": "kieler-bucht",
        "location": (10.2206, 54.4097),
        "sports": ["kitesurf", "windsurf"],  # flatwater — no wave sport
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "beginner",
        "water_character": "chop",
        "style": ["freeride"],
        "facilities": {
            "parking": {"available": True, "note": "Kostenpflichtig, an Sommerwochenenden früh voll."},
            "school": {"available": True, "note": "Kite- & Surfschule mit Verleih vor Ort."},
            "shower": {"available": True},
            "food": {"available": True, "note": "Strandbar & Imbiss an der Promenade."},
        },
        "status": "published",
        "facing": 45,
        "confidence": 0.5,
        "editorial": {
            "aliases": ["Laboe Beach"],
            "usable_wind_directions": {"min": 180, "max": 260},
            "wind_range": [14, 26],
        },
    },
    {
        "slug": "stein",
        "name": "Stein",
        "region_slug": "kieler-bucht",
        "location": (10.2667, 54.4500),  # ~5 km NE of Laboe
        "sports": ["kitesurf", "windsurf", "surf"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "advanced",
        "water_character": "welle_klein",
        "style": ["freeride", "wave_riding"],
        "status": "published",
        "facing": 50,
        "confidence": 0.55,
        "editorial": {
            "aliases": ["Steiner Strand"],
            "usable_wind_directions": {"min": 180, "max": 260},
            "wind_range": [14, 28],
        },
    },
    {
        "slug": "schilksee",
        "name": "Schilksee",
        "region_slug": "kieler-bucht",
        "location": (10.1747, 54.4244),  # ~4 km W of Laboe
        "sports": ["windsurf", "kitesurf"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "beginner",
        "water_character": "flach",
        "style": ["freeride"],
        "status": "published",
        "facing": 70,
        "confidence": 0.45,
        "editorial": {
            "usable_wind_directions": {"min": 200, "max": 290},
            "wind_range": [12, 24],
        },
    },
    {
        "slug": "heidkate",
        "name": "Heidkate",
        "region_slug": "kieler-bucht",
        "location": (10.3486, 54.4561),  # ~8 km E of Laboe
        "sports": ["surf", "windsurf"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "advanced",
        "water_character": "welle_klein",
        "style": ["wave_riding", "freeride"],
        "status": "published",
        "facing": 30,
        "confidence": 0.5,
        "editorial": {
            "usable_wind_directions": {"min": 0, "max": 80},
            "wind_range": [16, 30],
        },
    },
    {
        "slug": "fehmarn-wulfener-hals",
        "name": "Fehmarn Wulfener Hals",
        "region_slug": "kieler-bucht",
        "location": (11.1500, 54.4300),  # ~58 km E — stronger but farther
        "sports": ["kitesurf", "windsurf", "wing", "surf"],
        "water_type": "sea",
        "bottom_type": "sand",
        "level": "advanced",
        "water_character": "flach",
        "style": ["freeride", "freestyle", "big_air"],
        "facilities": {
            "parking": {"available": True},
            "school": {"available": True, "note": "Surfcenter mit Verleih und Kursen."},
            "shower": {"available": True},
            "food": {"available": True},
            "camping": {"available": True, "note": "Campingplatz Wulfener Hals direkt am Spot."},
        },
        "status": "published",
        "facing": 200,
        "confidence": 0.9,
        "editorial": {
            "aliases": ["Fehmarn", "Wulfener Hals"],
            "usable_wind_directions": {"min": 120, "max": 260},
            "wind_range": [14, 30],
        },
    },
]

# Spots get the same placeholder hero their regions get — derived from the slug.
# Until Sprint 1 the seed wrote images for regions only and dropped them for
# spots (the Spot(...) constructor had no image= at all), so a freshly seeded
# spot always came up without one.
for _s in SPOTS:
    _s.setdefault("image", _img(_s["slug"], kind="spot"))
