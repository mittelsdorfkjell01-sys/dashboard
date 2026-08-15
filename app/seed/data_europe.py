"""Researched seed batch: European wind + wave spots (draft, pending review).

Loaded only by the seed CLI (`python -m app.seed.seed`, via ``include_europe``),
NOT by the core ``seed(db)`` used in tests — so the test catalogue stays small
and deterministic. Slugs are globally unique and do not collide with the core
seed. All spots are ``status="draft"``: they are not public until reviewed and
published (readiness additionally needs a derived climatology + credited image).

Data honesty:
- Coordinates are (lon, lat) public geodata, fine for map pins; verify before
  publishing.
- ``facing`` is intentionally omitted (nullable) where no reliable orientation
  was available — not guessed.
- ``facilities`` are set only where sources support them. A missing key = unknown
  (shown as its own dimmed state on the spot page, not hidden and never
  "not available"). ``available: false`` only on counter-evidence.
- ``editorial.tide`` on wave spots is ``"n/a"`` where no reliable tide info was
  available (readiness accepts the sentinel).
- ``usable_wind_directions`` are authored as 8-point compass letters and
  normalised to 45°, wrap-aware ``{min,max}`` windows below, so the scoring /
  similarity engine consumes them natively (see ``_compass_to_windows``).
"""

from __future__ import annotations


def _box(lon: float, lat: float, d: float = 0.25):
    """Rough, closed bounding box around a centre (lon, lat)."""
    return [
        (lon - d, lat - d),
        (lon + d, lat - d),
        (lon + d, lat + d),
        (lon - d, lat + d),
        (lon - d, lat - d),
    ]


def _img(slug: str, *, kind: str = "region"):
    """Placeholder hero — a real image comes later via the admin picker/upload.

    The unreachable ``*.local`` host is load-bearing: the frontend renders its
    designed no-image state for it, and ``image_ready`` refuses to count it as a
    finished image. Both would break with a plausible-looking URL.
    """
    from app.media.image_object import placeholder_image

    return placeholder_image(slug, kind=kind)


# --- compass → usable-direction windows ------------------------------------

# Canonical bearing (deg, 0 = N) for 16-point compass letters.
_COMPASS_BEARING = {
    "N": 0.0, "NNE": 22.5, "NE": 45.0, "ENE": 67.5,
    "E": 90.0, "ESE": 112.5, "SE": 135.0, "SSE": 157.5,
    "S": 180.0, "SSW": 202.5, "SW": 225.0, "WSW": 247.5,
    "W": 270.0, "WNW": 292.5, "NW": 315.0, "NNW": 337.5,
}


def _compass_to_windows(dirs: list[str]) -> list[dict]:
    """8/16-point compass letters → list of 45°-wide, wrap-aware {min,max} windows.

    Each named direction becomes a 45° arc centred on its bearing (N →
    337.5–22.5). A contiguous list forms overlapping arcs (their union is the
    usable band); a split list (e.g. W/NW + E) yields separate windows — both are
    understood by ``direction_in_windows`` and ``window_to_sectors``.
    """
    windows: list[dict] = []
    for d in dirs:
        b = _COMPASS_BEARING[d]
        windows.append({"min": round((b - 22.5) % 360, 1), "max": round((b + 22.5) % 360, 1)})
    return windows


# ---------------------------------------------------------------------------
# REGIONS (new; tarifa/sardinia already exist in the core seed)
# ---------------------------------------------------------------------------
REGIONS: list[dict] = [
    # --- Wind: Canaries + Mediterranean + North Sea ---
    {"slug": "fuerteventura", "name": "Fuerteventura", "country": "ES",
     "center": (-14.02, 28.36), "bounds": _box(-14.02, 28.36, 0.4),
     "description": "Kanarische Passatinsel mit ganzjährig zuverlässigem "
     "Nordost-Wind und einer der besten Flachwasser-Lagunen Europas.",
     "season": {"best_months": [5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("fuerteventura")},
    {"slug": "lanzarote", "name": "Lanzarote", "country": "ES",
     "center": (-13.55, 29.03), "bounds": _box(-13.55, 29.03, 0.3),
     "description": "Vulkaninsel der Kanaren mit Passatwind, Riffwellen und "
     "einer geschützten Bucht in Costa Teguise.",
     "season": {"best_months": [5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("lanzarote")},
    {"slug": "tenerife", "name": "Teneriffa", "country": "ES",
     "center": (-16.55, 28.20), "bounds": _box(-16.55, 28.20, 0.4),
     "description": "Größte Kanareninsel; El Médano im Südosten zählt zu den "
     "windsichersten Spots Europas.",
     "season": {"best_months": [1, 4, 5, 6, 7, 8, 9, 12]},
     "defaults": {"model_pref": "icon"}, "image": _img("tenerife")},
    {"slug": "gran-canaria", "name": "Gran Canaria", "country": "ES",
     "center": (-15.58, 27.90), "bounds": _box(-15.58, 27.90, 0.35),
     "description": "Kanareninsel mit dem legendären Wellen-Windsurfspot Pozo "
     "Izquierdo an der windexponierten Ostküste.",
     "season": {"best_months": [5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("gran-canaria")},
    {"slug": "rhodes", "name": "Rhodos", "country": "GR",
     "center": (27.95, 36.10), "bounds": _box(27.95, 36.10, 0.35),
     "description": "Dodekanes-Insel mit starkem Meltemi; Prasonisi im Süden "
     "ist einer der bekanntesten Ägäis-Spots.",
     "season": {"best_months": [5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("rhodes")},
    {"slug": "naxos", "name": "Naxos", "country": "GR",
     "center": (25.43, 37.05), "bounds": _box(25.43, 37.05, 0.3),
     "description": "Kykladeninsel mit düsenverstärktem Meltemi; Mikri Vigla "
     "ist der windzuverlässigste Spot der Insel.",
     "season": {"best_months": [5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("naxos")},
    {"slug": "paros", "name": "Paros", "country": "GR",
     "center": (25.15, 37.02), "bounds": _box(25.15, 37.02, 0.3),
     "description": "Kykladen-Windsportinsel; Pounda an der Meerenge zu "
     "Antiparos ist ein internationaler Kitespot.",
     "season": {"best_months": [5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("paros")},
    {"slug": "kos", "name": "Kos", "country": "GR",
     "center": (27.15, 36.85), "bounds": _box(27.15, 36.85, 0.3),
     "description": "Dodekanes-Insel; Psalidi im Osten ist der bekannteste "
     "Kite- und Windsurfstrand von Kos.",
     "season": {"best_months": [5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("kos")},
    {"slug": "lemnos", "name": "Limnos", "country": "GR",
     "center": (25.25, 39.90), "bounds": _box(25.25, 39.90, 0.3),
     "description": "Nordägäische Insel; Keros an der Ostküste bietet einen "
     "langen Sandstrand mit Flach- und Wellenbereich.",
     "season": {"best_months": [5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("lemnos")},
    {"slug": "sicily", "name": "Sizilien", "country": "IT",
     "center": (12.45, 37.87), "bounds": _box(12.45, 37.87, 0.35),
     "description": "Lo Stagnone bei Marsala ist eine der größten "
     "Flachwasser-Kitelagunen Europas.",
     "season": {"best_months": [4, 5, 6, 7, 8, 9]},
     "defaults": {"model_pref": "icon"}, "image": _img("sicily")},
    {"slug": "languedoc", "name": "Languedoc", "country": "FR",
     "center": (3.03, 42.90), "bounds": _box(3.03, 42.90, 0.3),
     "description": "Südfranzösische Mittelmeerküste mit kräftigem Tramontane; "
     "Leucate ist Austragungsort des Mondial du Vent.",
     "season": {"best_months": [4, 5, 6, 7, 8, 9, 10]},
     "defaults": {"model_pref": "icon"}, "image": _img("languedoc")},
    {"slug": "zeeland", "name": "Zeeland", "country": "NL",
     "center": (3.85, 51.75), "bounds": _box(3.85, 51.75, 0.3),
     "description": "Niederländische Küstenprovinz mit dem Brouwersdam — "
     "Süßwasser-Flachwasser und Nordseewellen an einem Ort.",
     "season": {"best_months": [3, 4, 5, 9, 10, 11]},
     "defaults": {"model_pref": "icon_d2"}, "image": _img("zeeland")},

    # --- Wave: Portugal, N Spain, France, Ireland, UK ---
    {"slug": "ericeira", "name": "Ericeira", "country": "PT",
     "center": (-9.42, 38.96), "bounds": _box(-9.42, 38.96, 0.15),
     "description": "Europas einziges World Surfing Reserve mit einer hohen "
     "Dichte an Weltklasse-Wellen auf kurzer Küstenlänge.",
     "season": {"best_months": [9, 10, 11, 3, 4]},
     "defaults": {"model_pref": "icon"}, "image": _img("ericeira")},
    {"slug": "peniche", "name": "Peniche", "country": "PT",
     "center": (-9.38, 39.36), "bounds": _box(-9.38, 39.36, 0.15),
     "description": "Portugals meistbesuchte Surfregion; die Halbinsel fängt "
     "Swell aus fast allen Richtungen, u. a. am Supertubos.",
     "season": {"best_months": [9, 10, 11, 3, 4]},
     "defaults": {"model_pref": "icon"}, "image": _img("peniche")},
    {"slug": "nazare", "name": "Nazaré", "country": "PT",
     "center": (-9.07, 39.60), "bounds": _box(-9.07, 39.60, 0.12),
     "description": "Big-Wave-Mekka: der Nazaré-Canyon bündelt Swell zu den "
     "größten je gesurften Wellen der Welt.",
     "season": {"best_months": [10, 11, 12, 1, 2]},
     "defaults": {"model_pref": "icon"}, "image": _img("nazare")},
    {"slug": "cascais", "name": "Cascais / Lissabon-Küste", "country": "PT",
     "center": (-9.42, 38.70), "bounds": _box(-9.42, 38.70, 0.2),
     "description": "Küste westlich von Lissabon mit Carcavelos (Wiege des "
     "portugiesischen Surfens) und dem windexponierten Guincho.",
     "season": {"best_months": [9, 10, 11, 3, 4]},
     "defaults": {"model_pref": "icon"}, "image": _img("cascais")},
    {"slug": "sintra", "name": "Sintra", "country": "PT",
     "center": (-9.47, 38.80), "bounds": _box(-9.47, 38.80, 0.12),
     "description": "Küste am Cabo da Roca; Praia Grande ist einer der "
     "konstantesten Beachbreaks der Region.",
     "season": {"best_months": [9, 10, 11, 3, 4]},
     "defaults": {"model_pref": "icon"}, "image": _img("sintra")},
    {"slug": "basque-country", "name": "Baskenland", "country": "ES",
     "center": (-2.30, 43.35), "bounds": _box(-2.30, 43.35, 0.4),
     "description": "Nordspanische Atlantikküste mit dem legendären "
     "Linksbrecher Mundaka und dem Beachbreak Zarautz.",
     "season": {"best_months": [10, 11, 12, 1, 2]},
     "defaults": {"model_pref": "icon"}, "image": _img("basque-country")},
    {"slug": "cantabria", "name": "Kantabrien", "country": "ES",
     "center": (-3.75, 43.45), "bounds": _box(-3.75, 43.45, 0.3),
     "description": "Nordspanische Küste um Santander; Somo ist ein "
     "einsteigerfreundlicher Beachbreak mit langer Welle.",
     "season": {"best_months": [10, 11, 12, 1, 2]},
     "defaults": {"model_pref": "icon"}, "image": _img("cantabria")},
    {"slug": "asturias", "name": "Asturien", "country": "ES",
     "center": (-5.38, 43.53), "bounds": _box(-5.38, 43.53, 0.4),
     "description": "Grüne Nordküste Spaniens; Rodiles gilt als das "
     "spanische Mundaka mit Flussmündungs-Setup.",
     "season": {"best_months": [10, 11, 12, 1, 2]},
     "defaults": {"model_pref": "icon"}, "image": _img("asturias")},
    {"slug": "landes", "name": "Landes / Hossegor", "country": "FR",
     "center": (-1.43, 43.66), "bounds": _box(-1.43, 43.66, 0.25),
     "description": "Südwestfrankreichs Epizentrum des Surfens; ein "
     "Unterwassercanyon speist die kraftvollen Beachbreaks von Hossegor.",
     "season": {"best_months": [9, 10, 11, 5, 6]},
     "defaults": {"model_pref": "icon"}, "image": _img("landes")},
    {"slug": "donegal", "name": "Donegal", "country": "IE",
     "center": (-8.28, 54.48), "bounds": _box(-8.28, 54.48, 0.3),
     "description": "Irlands Surf-Hauptstadt Bundoran an der Wild Atlantic "
     "Way mit kraftvollen Riffwellen.",
     "season": {"best_months": [9, 10, 11, 3, 4]},
     "defaults": {"model_pref": "icon"}, "image": _img("donegal")},
    {"slug": "clare", "name": "County Clare", "country": "IE",
     "center": (-9.35, 52.93), "bounds": _box(-9.35, 52.93, 0.3),
     "description": "Westirische Surfregion; Lahinch ist ein Surf-Hub mit "
     "einsteigerfreundlichen Beachbreaks und starker Community.",
     "season": {"best_months": [9, 10, 11, 3, 4]},
     "defaults": {"model_pref": "icon"}, "image": _img("clare")},
    {"slug": "caithness", "name": "Caithness", "country": "GB",
     "center": (-3.52, 58.60), "bounds": _box(-3.52, 58.60, 0.3),
     "description": "Nordschottland; Thurso East ist ein Weltklasse-"
     "Rechtsbrecher über einer flachen Felsplatte vor einer Burg.",
     "season": {"best_months": [9, 10, 11, 2, 3]},
     "defaults": {"model_pref": "icon"}, "image": _img("caithness")},
    {"slug": "cornwall", "name": "Cornwall", "country": "GB",
     "center": (-5.08, 50.42), "bounds": _box(-5.08, 50.42, 0.3),
     "description": "Englands Surf-Kernland; Fistral Beach in Newquay ist der "
     "bekannteste Surfstrand des Landes.",
     "season": {"best_months": [9, 10, 11, 3, 4]},
     "defaults": {"model_pref": "icon"}, "image": _img("cornwall")},
]


# ---------------------------------------------------------------------------
# SPOTS
# ---------------------------------------------------------------------------
SPOTS: list[dict] = [
    # ==================== WIND ====================
    {"slug": "fuerteventura-sotavento", "name": "Sotavento",
     "region_slug": "fuerteventura", "location": (-14.228, 28.045),
     "sports": ["kitesurf", "windsurf", "wing"],
     "water_type": "lagoon", "bottom_type": "sand", "level": "beginner",
     "water_character": "flach", "style": ["freestyle", "big_air"],
     "status": "draft",
     "editorial": {"description": "Rund 9 km lange Lagune an der Costa Calma "
        "und alljährlicher PWA-/GKA-Weltcup-Spot. Bei Ebbe entsteht knie- bis "
        "hüfttiefes Flachwasser — einer der sichersten Lernspots Europas; bei "
        "Flut öffnet sich die Lagune zum offenen Meer mit Chop und kleinen "
        "Wellen. Der Nordost-Passat weht von Mai bis September fast täglich "
        "kräftig. Der Bereich ist in Anfänger- und Fortgeschrittenenzonen "
        "unterteilt.",
        "usable_wind_directions": ["N", "NE", "E"]},
     "facilities": {"parking": {"available": True},
        "shower": {"available": True},
        "food": {"available": True, "note": "Beachbars / Hotels am Strand"},
        "school": {"available": True, "note": "Mehrere Centren, Weltcup-Station"}}},

    {"slug": "fuerteventura-flag-beach", "name": "Flag Beach",
     "region_slug": "fuerteventura", "location": (-13.835, 28.715),
     "sports": ["kitesurf", "windsurf", "wing"],
     "water_type": "ocean", "bottom_type": "mixed", "level": "advanced",
     "water_character": "chop", "style": ["freeride", "wave_riding"],
     "status": "draft",
     "editorial": {"description": "Meistfrequentierter Spot im Norden "
        "Fuerteventuras bei Corralejo, geschützt durch die Insel Lobos. Das "
        "Wasser wird schnell tief, mit Chop und bei stärkerem Wind sauberen "
        "Wellen weiter draußen — gut für Fortgeschrittene und Wave-Freestyle. "
        "Am Einstieg liegen einige Steine. Unterricht findet hier vom Boot "
        "aus statt.",
        "usable_wind_directions": ["N", "NE", "E"]},
     "facilities": {"parking": {"available": True, "note": "Direkt am Strand, kostenlos; im Sommer früh voll"},
        "food": {"available": True, "note": "Beachbars für Sundowner"},
        "school": {"available": True, "note": "Mehrere Schulen/Verleihe, Foil-Rental"}}},

    {"slug": "fuerteventura-el-cotillo", "name": "El Cotillo",
     "region_slug": "fuerteventura", "location": (-14.010, 28.680),
     "sports": ["kitesurf", "windsurf"],
     "water_type": "ocean", "bottom_type": "mixed", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding", "big_air"],
     "status": "draft",
     "editorial": {"description": "Wellenspot im Nordwesten mit teils großen, "
        "kraftvollen Wellen (1–3 m) und seitlich-ablandigem Wind — nur für "
        "erfahrene Rider. Twin-Tip-Fahrer nutzen die Wellen als Kicker für "
        "Sprünge. In der nahen Lagune am Leuchtturm gibt es zusätzlich ein "
        "flaches Anfängerrevier. Auf Steine und ablandigen Wind achten.",
        "usable_wind_directions": ["N", "NW"]},
     "facilities": {"school": {"available": True, "note": "Kiteschule an der Lagune"}}},

    {"slug": "fuerteventura-majanicho", "name": "Majanicho",
     "region_slug": "fuerteventura", "location": (-13.950, 28.740),
     "sports": ["kitesurf"],
     "water_type": "ocean", "bottom_type": "reef", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Abgelegener Wellenspot im Norden mit einer "
        "Bucht, die die Wellen etwas glättet, aber großen, sauberen Swell "
        "zulässt. Felsiger Einstieg und scharfes Riff machen ihn zu einem der "
        "anspruchsvollsten der Insel. Genutzt von Kitern, Windsurfern und "
        "Wellenreitern. Für Einsteiger ungeeignet.",
        "usable_wind_directions": ["N", "NE", "NW"]}},

    {"slug": "fuerteventura-matas-bay", "name": "Matas Bay",
     "region_slug": "fuerteventura", "location": (-14.230, 28.070),
     "sports": ["kitesurf", "wing"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "flach", "style": ["freeride", "big_air"],
     "status": "draft",
     "editorial": {"description": "Kleine Bucht nördlich von Sotavento mit "
        "gezeitenunabhängigem Flachwasser, das gleichmäßig tiefer wird — "
        "ideal zum Foilen. Der Wind steht meist ablandig, weshalb ein "
        "Jetski-Rescue der Center empfohlen ist. Der Spot wird von "
        "Windsurfern, Kitern, Wingfoilern und Foilern geteilt und kann eng "
        "werden. Für erfahrene Rider mit Rescue-Absicherung.",
        "usable_wind_directions": ["N", "NE", "E"]},
     "facilities": {"school": {"available": True, "note": "Center mit Jetski-Rescue"}}},

    {"slug": "tarifa-punta-paloma", "name": "Punta Paloma",
     "region_slug": "tarifa", "location": (-5.730, 36.075),
     "sports": ["kitesurf", "wing"],
     "water_type": "sea", "bottom_type": "sand", "level": "beginner",
     "water_character": "chop", "style": ["freeride"],
     "status": "draft",
     "editorial": {"description": "Nördlich von Valdevaqueros an den großen "
        "Dünen von Tarifa gelegen. Bei Poniente (West) steht der Wind "
        "seitlich-auflandig und damit anfängerfreundlich, mit Blick bis nach "
        "Marokko. Weitläufiger Strand mit viel Platz zum Starten und Landen. "
        "Ruhiger als die Hauptspots weiter südlich.",
        "usable_wind_directions": ["W"]}},

    {"slug": "tarifa-arte-vida", "name": "Arte Vida",
     "region_slug": "tarifa", "location": (-5.655, 36.035),
     "sports": ["kitesurf", "surf"],
     "water_type": "sea", "bottom_type": "mixed", "level": "advanced",
     "water_character": "welle_klein", "style": ["wave_riding", "freeride", "wavekite"],
     "status": "draft",
     "editorial": {"description": "Spot zwischen Los Lances und Valdevaqueros, "
        "der vor allem bei Poniente (West) funktioniert und für "
        "Strapless-Wellenreiten beliebt ist. Bei Levante eher ungeeignet zum "
        "Kiten. Nahe der Küste liegen Steine — Booties empfohlen, beim "
        "Springen Vorsicht. Meist weniger überlaufen als die Nachbarspots.",
        "usable_wind_directions": ["W"]}},

    {"slug": "lanzarote-costa-teguise", "name": "Costa Teguise",
     "region_slug": "lanzarote", "location": (-13.500, 29.000),
     "sports": ["windsurf", "kitesurf", "wing"],
     "water_type": "ocean", "bottom_type": "reef", "level": "beginner",
     "water_character": "flach", "style": ["freeride"],
     "status": "draft",
     "editorial": {"description": "Geschützte Bucht an der Nordostküste "
        "Lanzarotes mit ruhigem Flachwasser für Einsteiger und rollenden "
        "Riffwellen außerhalb der Bucht für Fortgeschrittene. Windsurfen hat "
        "hier lange Tradition, ergänzt um Kite und Wing. Gut ausgebaute "
        "touristische Infrastruktur im Ferienort.",
        "usable_wind_directions": ["N", "NE", "E"]},
     "facilities": {"food": {"available": True, "note": "Breites Angebot im Ferienort"},
        "school": {"available": True, "note": "Windsurf-/Kitecenter vor Ort"}}},

    {"slug": "tenerife-el-medano", "name": "El Médano",
     "region_slug": "tenerife", "location": (-16.535, 28.045),
     "sports": ["windsurf", "kitesurf", "wing"],
     "water_type": "ocean", "bottom_type": "mixed", "level": "advanced",
     "water_character": "chop", "style": ["freeride", "wave_riding", "big_air"],
     "status": "draft",
     "editorial": {"description": "Einer der windsichersten Spots Europas mit "
        "nahezu ganzjährigem, thermisch verstärktem Nordost-Passat. Mehrere "
        "Reviere: eine geschütztere Bucht für Fortgeschrittene und eine "
        "anspruchsvolle Wellenzone für Experten. Sitz mehrerer Schulen, nur "
        "wenige Minuten vom Flughafen. Bei starkem Wind schnell fordernd.",
        "usable_wind_directions": ["N", "NE", "E"]},
     "facilities": {"school": {"available": True, "note": "Mehrere Schulen/Verleihe im Ort"}}},

    {"slug": "gran-canaria-pozo-izquierdo", "name": "Pozo Izquierdo",
     "region_slug": "gran-canaria", "location": (-15.400, 27.810),
     "sports": ["windsurf", "kitesurf"],
     "water_type": "ocean", "bottom_type": "reef", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding", "big_air"],
     "status": "draft",
     "editorial": {"description": "Legendärer Wellen-Windsurfspot an der "
        "windexponierten Ostküste, Austragungsort von PWA-Weltcups. Sehr "
        "starker, beschleunigter Passat und kräftige Wellen machen ihn zu "
        "einem Experten-Revier. Kite ist ebenfalls möglich, aber "
        "anspruchsvoll. Nichts für Einsteiger.",
        "usable_wind_directions": ["N", "NE", "E"]}},

    {"slug": "rhodes-prasonisi", "name": "Prasonisi",
     "region_slug": "rhodes", "location": (27.760, 35.900),
     "sports": ["kitesurf", "windsurf"],
     "water_type": "sea", "bottom_type": "sand", "level": "advanced",
     "water_character": "flach", "style": ["freestyle", "wave_riding"],
     "status": "draft",
     "editorial": {"description": "Bekanntester Meltemi-Spot der Ägäis an der "
        "Südspitze von Rhodos. Eine Sandbank trennt zwei Seiten: flaches "
        "Wasser auf der einen, Wellen auf der anderen — Freestyle und "
        "Wellenreiten am selben Ort. Der Wind wird im Sommer sehr kräftig. "
        "Die Region ist wenig entwickelt; viele übernachten im Zelt oder "
        "Camper.",
        "usable_wind_directions": ["N", "NW"]},
     "facilities": {"food": {"available": True, "note": "Wenige Restaurants/Beachbars"},
        "camping": {"available": True, "note": "Informelles Camping / Camper verbreitet"},
        "school": {"available": True, "note": "Mehrere Kite-/Windsurfstationen"}}},

    {"slug": "rhodes-theologos", "name": "Theologos (Fanes)",
     "region_slug": "rhodes", "location": (28.070, 36.320),
     "sports": ["kitesurf", "windsurf"],
     "water_type": "sea", "bottom_type": "sand", "level": "beginner",
     "water_character": "chop", "style": ["freeride", "big_air"],
     "status": "draft",
     "editorial": {"description": "Spot nahe dem Flughafen von Rhodos mit "
        "kräftigem, seitlichem Meltemi, der große Sprünge erlaubt. Geeignet "
        "für Kiter aller Level dank viel Platz. Verleih- und Materialshops "
        "vor Ort. Weniger überlaufen als Prasonisi im Süden.",
        "usable_wind_directions": ["N", "NW"]},
     "facilities": {"school": {"available": True, "note": "Verleih/Schulen vor Ort"}}},

    {"slug": "naxos-mikri-vigla", "name": "Mikri Vigla",
     "region_slug": "naxos", "location": (25.400, 37.000),
     "sports": ["kitesurf", "windsurf", "wing"],
     "water_type": "sea", "bottom_type": "sand", "level": "advanced",
     "water_character": "chop", "style": ["freeride", "freestyle"],
     "status": "draft",
     "editorial": {"description": "Windzuverlässigster Spot der Kykladen an "
        "der Westküste von Naxos, wo der Meltemi in der Meerenge zu Paros "
        "düsenartig beschleunigt. In der Bucht flach bis choppy, außerhalb "
        "kleine Wellen. Wind meist ab Mittag bis in den späten Nachmittag. "
        "Schule direkt am Spot.",
        "usable_wind_directions": ["N", "NW"]},
     "facilities": {"school": {"available": True, "note": "Kite-/Wingfoilschule am Spot"}}},

    {"slug": "paros-pounda", "name": "Pounda",
     "region_slug": "paros", "location": (25.110, 37.020),
     "sports": ["kitesurf", "windsurf"],
     "water_type": "sea", "bottom_type": "sand", "level": "beginner",
     "water_character": "chop", "style": ["freeride", "freestyle"],
     "status": "draft",
     "editorial": {"description": "Internationaler Kitespot an der Meerenge "
        "zwischen Paros und Antiparos mit zuverlässigem Nordwind. Langer, "
        "hindernisfreier Sandstrand mit viel Platz zum Starten und Landen; "
        "das Wasser wird recht schnell tief. Geeignet für Einsteiger wie "
        "Fortgeschrittene. Schulen mit Beachbereich, Verpflegung und "
        "Rescue-Service.",
        "usable_wind_directions": ["N", "NW"]},
     "facilities": {"food": {"available": True, "note": "Schulen mit Restaurant/BBQ"},
        "school": {"available": True, "note": "Mehrere Schulen, Verleih, Rescue"}}},

    {"slug": "kos-psalidi", "name": "Psalidi",
     "region_slug": "kos", "location": (27.330, 36.870),
     "sports": ["kitesurf", "windsurf"],
     "water_type": "sea", "bottom_type": "sand", "level": "beginner",
     "water_character": "chop", "style": ["freeride"],
     "status": "draft",
     "editorial": {"description": "Bekanntester Kite- und Windsurfstrand von "
        "Kos an der Ostküste mit zuverlässigem Sommerwind. Touristisch gut "
        "erschlossen mit großen Resorts in der Nähe. Oft mild und warm bis "
        "in den Herbst. Solide Einsteiger- und Fortgeschrittenenbedingungen.",
        "usable_wind_directions": ["N", "NW"]}},

    {"slug": "lemnos-keros", "name": "Keros",
     "region_slug": "lemnos", "location": (25.400, 39.870),
     "sports": ["windsurf", "kitesurf"],
     "water_type": "sea", "bottom_type": "sand", "level": "beginner",
     "water_character": "flach", "style": ["freeride"],
     "status": "draft",
     "editorial": {"description": "Langer, weiter Sandstrand an der Ostküste "
        "von Limnos mit einem flachen Bereich zum Lernen und einer "
        "Wellenzone für Fortgeschrittene. Ruhiges, wenig überlaufenes Revier "
        "mit einem etablierten Surfclub. Meltemi-Wind im Sommer.",
        "usable_wind_directions": ["N", "NW"]},
     "facilities": {"school": {"available": True, "note": "Keros Surf Club vor Ort"}}},

    {"slug": "sicily-lo-stagnone", "name": "Lo Stagnone",
     "region_slug": "sicily", "location": (12.470, 37.870),
     "sports": ["kitesurf", "wing"],
     "water_type": "lagoon", "bottom_type": "sand", "level": "beginner",
     "water_character": "flach", "style": ["freestyle", "freeride"],
     "status": "draft",
     "editorial": {"description": "Große, knie- bis hüfttiefe Flachwasser-"
        "Lagune zwischen Marsala und Trapani, geschützt durch die "
        "vorgelagerte Isola Grande. Ideal zum Lernen und für Freestyle mit "
        "nur leichtem Chop in der Mitte. Mehrere internationale Kitecamps "
        "betreiben feste Basen mit eigenen Start-/Landebereichen.",
        "usable_wind_directions": ["W", "NW", "E"]},
     "facilities": {"school": {"available": True, "note": "Mehrere Kitecamps/Schulen mit fester Basis"}}},

    {"slug": "languedoc-leucate", "name": "Leucate",
     "region_slug": "languedoc", "location": (3.030, 42.910),
     "sports": ["windsurf", "kitesurf", "wing"],
     "water_type": "sea", "bottom_type": "sand", "level": "beginner",
     "water_character": "chop", "style": ["freeride", "freestyle"],
     "status": "draft",
     "editorial": {"description": "Einer der bekanntesten Wind-Spots am "
        "französischen Mittelmeer und Austragungsort des Mondial du Vent. Der "
        "offene Meeresstrand ist bei leichtem Wind auch für Einsteiger "
        "geeignet, bei kräftigem Tramontane jedoch fordernd. Der dahinter "
        "liegende Salzsee (Étang) bietet zusätzlich ruhiges Flachwasser für "
        "alle Level.",
        "usable_wind_directions": ["N", "NW"]},
     "facilities": {"school": {"available": True, "note": "Mehrere Kite-/Windsurfschulen"}}},

    {"slug": "zeeland-brouwersdam", "name": "Brouwersdam",
     "region_slug": "zeeland", "location": (3.820, 51.760),
     "sports": ["kitesurf", "windsurf", "wing"],
     "water_type": "sea", "bottom_type": "sand", "level": "advanced",
     "water_character": "chop", "style": ["freestyle", "freeride"],
     "status": "draft",
     "editorial": {"description": "Der Damm trennt die Nordsee vom "
        "Grevelingenmeer und bietet zwei Reviere an einem Ort: flaches "
        "Süßwasser für Freestyle und Einsteiger sowie Nordseewellen. Fahrbar "
        "bei Wind aus Nord, Nordwest, West und Südwest — einer der "
        "meistbesuchten Kitespots der Niederlande. Ein Bereich ist für "
        "Kitefoiler reserviert.",
        "usable_wind_directions": ["N", "NW", "W", "SW"]},
     "facilities": {"food": {"available": True, "note": "Mehrere Restaurants am Strand"},
        "school": {"available": True, "note": "Mehrere Kitesurfschulen"}}},

    # ==================== WAVE ====================
    {"slug": "ericeira-ribeira-dilhas", "name": "Ribeira d'Ilhas",
     "region_slug": "ericeira", "location": (-9.418, 38.983),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "reef", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Bekannteste Welle Ericeiras und WSL-"
        "Wettkampfstätte: ein langer Rechtsbrecher, der schon auf kleinem "
        "NW-Swell anspringt und auch bei kräftigem Winter sauber bleibt. "
        "Blue-Flag-Strand mit einfachem Zugang; bei vollem Peak lassen sich "
        "innen weitere Wellen finden. Beliebt und entsprechend gut besucht.",
        "tide": "mid"},
     "facilities": {"parking": {"available": True, "note": "Reichlich Parkplatz direkt am Spot"},
        "food": {"available": True, "note": "Surfbar am Strand"},
        "school": {"available": True, "note": "Zahlreiche Surfschulen in Ericeira"}}},

    {"slug": "ericeira-coxos", "name": "Coxos",
     "region_slug": "ericeira", "location": (-9.420, 38.995),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "reef", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Von vielen als beste Welle Portugals "
        "gehandelter, kraftvoller Rechts-Pointbreak, der über scharfem Riff "
        "in eine kleine Bucht läuft. Ausschließlich für erfahrene Surfer; bei "
        "Flut brechen die Wellen direkt in die Felsen. Zugang und Einstieg "
        "sind anspruchsvoll. Kenne deine Grenzen.",
        "tide": "low-mid"}},

    {"slug": "ericeira-sao-lourenco", "name": "São Lourenço",
     "region_slug": "ericeira", "location": (-9.415, 39.010),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "reef", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Kraftvoller Rechts-Pointbreak nördlich von "
        "Ericeira bei Ribamar, der über flachen Felsen läuft und Wellen bis "
        "etwa 3 m hält. Wirkt kräftiger, als er aussieht, und ist "
        "unversöhnlich — nur für erfahrene Surfer. Funktioniert am besten bei "
        "Niedrigwasser. Wegen des kniffligen Zugangs meist wenig überlaufen.",
        "tide": "low"}},

    {"slug": "ericeira-foz-do-lizandro", "name": "Foz do Lizandro",
     "region_slug": "ericeira", "location": (-9.420, 38.945),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "beginner",
     "water_character": "welle_klein", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Flussmündungs-Beachbreak südlich von "
        "Ericeira und einer der besten Anfängerspots der Region. Meist "
        "gutmütige Wellen für Einsteiger und Intermediates; an großen Tagen "
        "kann er auch saubere Tubes mit mehreren Peaks liefern. Surfschulen "
        "sind hier aktiv.",
        "tide": "mid"},
     "facilities": {"school": {"available": True, "note": "Surfschulen am Spot"}}},

    {"slug": "peniche-supertubos", "name": "Supertubos",
     "region_slug": "peniche", "location": (-9.365, 39.348),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Portugals Pipeline: ein schneller, "
        "hohler Beachbreak über Sandbänken, der kräftige Barrels liefert und "
        "die WSL (Rip Curl Pro) beherbergt. Der meistfotografierte Wave des "
        "Landes und entsprechend voll, besonders im Sommer. Bei guten "
        "Bedingungen für erfahrene Surfer; berüchtigt für gebrochene Boards.",
        "tide": "mid"},
     "facilities": {"school": {"available": True, "note": "Zahlreiche Surfschulen in Peniche"}}},

    {"slug": "peniche-baleal", "name": "Baleal",
     "region_slug": "peniche", "location": (-9.335, 39.375),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "beginner",
     "water_character": "welle_klein", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Halbinsel nördlich von Peniche mit "
        "mehreren Beachbreaks, die in unterschiedliche Richtungen zeigen — "
        "dadurch fast immer eine surfbare Ecke. Sandiger Boden und "
        "gutmütige Wellen machen die Prainha zum Favoriten der Surfschulen. "
        "Ideal für Einsteiger und Intermediates, ganzjährig.",
        "tide": "mid"},
     "facilities": {"parking": {"available": True, "note": "Im Sommer früh voll"},
        "food": {"available": True, "note": "Cafés/Restaurants am Ort"},
        "school": {"available": True, "note": "Viele Surfcamps/-schulen"}}},

    {"slug": "nazare-praia-do-norte", "name": "Praia do Norte",
     "region_slug": "nazare", "location": (-9.085, 39.605),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "expert",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Das Big-Wave-Mekka der Welt: Der "
        "Nazaré-Canyon bündelt Atlantik-Swell zu gigantischen Wellen, hier "
        "wurden Weltrekorde gesurft. Extrem gefährlich und ausschließlich für "
        "Profis mit Jetski-Support. Für alle anderen ein "
        "Zuschauer-Spektakel von der Klippe. Beste Bedingungen im Winter.",
        "tide": "n/a"},
     "facilities": {"parking": {"available": True, "note": "Klippen-Parkplätze, bei Swell überlaufen"},
        "food": {"available": True, "note": "Cafés/Bars an der Klippe und am Strand"}}},

    {"slug": "cascais-carcavelos", "name": "Carcavelos",
     "region_slug": "cascais", "location": (-9.335, 38.680),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "beginner",
     "water_character": "welle_klein", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Als Wiege des portugiesischen Surfens "
        "gilt dieser 1,5 km lange Beachbreak nur 20 Minuten von Lissabon. Im "
        "Sommer gutmütig und ideal für Einsteiger, im Herbst/Winter kräftiger "
        "für Intermediates. Volle Strandinfrastruktur mit Cafés und "
        "Duschen; entsprechend voll und mit lokalem Line-up an den Riffen.",
        "tide": "mid"},
     "facilities": {"shower": {"available": True, "note": "Volle Strandinfrastruktur"},
        "food": {"available": True, "note": "Cafés/Restaurants am Strand"},
        "school": {"available": True, "note": "Viele Surfschulen"}}},

    {"slug": "cascais-guincho", "name": "Praia do Guincho",
     "region_slug": "cascais", "location": (-9.472, 38.732),
     "sports": ["windsurf", "kitesurf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding", "freeride"],
     "status": "draft",
     "editorial": {"description": "Kraftvoller, westexponierter Strand bei "
        "Cascais mit konstantem Swell und starkem Nordwind — international "
        "bekannt bei Wind- und Kitesurfern und Austragungsort von "
        "Wettbewerben. Der Wind frischt typischerweise über den Tag auf und "
        "wird von Juni bis August besonders kräftig. Strömung und Wind machen "
        "den Spot für Einsteiger tückisch; er ist erfahrenen Ridern "
        "vorbehalten.",
        "usable_wind_directions": ["N", "NW"]},
     "facilities": {"school": {"available": True, "note": "Wind-/Surfschulen in der Umgebung"}}},

    {"slug": "sintra-praia-grande", "name": "Praia Grande",
     "region_slug": "sintra", "location": (-9.485, 38.815),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Einer der konstantesten Beachbreaks der "
        "Region nördlich des Cabo da Roca — der Spot, der läuft, wenn "
        "anderswo Flaute herrscht. Exponiert gegenüber W/NW-Swell, mit "
        "Windschutz durch die Klippen. Austragungsort eines Bodyboard-"
        "Wettbewerbs. UNESCO-Weltkulturerbe-Stadt Sintra in der Nähe.",
        "tide": "mid"}},

    {"slug": "basque-mundaka", "name": "Mundaka",
     "region_slug": "basque-country", "location": (-2.700, 43.407),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Weltberühmter Links-Barrel an der Mündung "
        "des Urdaibai-Ästuars, der über einer Sandbank Ritte von bis zu "
        "mehreren hundert Metern liefert. Ausschließlich für erfahrene "
        "Surfer und stark von exaktem Timing abhängig: läuft nur bei "
        "ablaufender Tide und NW-Swell. Ein Reiseziel für sich; das Line-up "
        "füllt sich schnell mit Locals.",
        "tide": "mid-dropping"},
     "facilities": {"food": {"available": True, "note": "Cafés/Restaurants im Dorf"}}},

    {"slug": "basque-zarautz", "name": "Zarautz",
     "region_slug": "basque-country", "location": (-2.170, 43.285),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "welle_klein", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Zugänglicher High-Performance-Beachbreak "
        "mit langem Strand, der Wellen bis rund 4 m hält und Bedingungen für "
        "mehrere Level bietet. Gute Wahl, wenn Mundaka nicht läuft. Beste "
        "Zeit von Oktober bis Februar mit konstantem NW-Swell. Ganzjährig "
        "kühles Wasser, Surfschulen vor Ort.",
        "tide": "mid"},
     "facilities": {"food": {"available": True, "note": "Promenade mit Cafés/Restaurants"},
        "school": {"available": True, "note": "Surfschulen am Strand"}}},

    {"slug": "cantabria-somo", "name": "Somo",
     "region_slug": "cantabria", "location": (-3.750, 43.470),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "beginner",
     "water_character": "welle_klein", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Entspannter Surfort bei Santander mit "
        "langem Sandstrand und gutmütigen Wellen — ideal zum Lernen. Sehr "
        "konstant und mit lockerer Community und vielen Schulen. Gute Basis "
        "für Anfänger und Longboarder. Kühles Wasser im Winter.",
        "tide": "mid"},
     "facilities": {"school": {"available": True, "note": "Mehrere Surfschulen im Ort"}}},

    {"slug": "asturias-rodiles", "name": "Rodiles",
     "region_slug": "asturias", "location": (-5.385, 43.530),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Als spanisches Mundaka bekannter "
        "Flussmündungs-Linksbrecher in Asturien mit ähnlichem Setup, jedoch "
        "launischer. Bei den richtigen Bedingungen eine lange, "
        "kraftvolle Welle für erfahrene Surfer. Grüne, wenig überlaufene "
        "Küste mit Wald-Kulisse. Braucht den passenden Swell.",
        "tide": "mid"}},

    {"slug": "landes-la-graviere", "name": "La Gravière (Hossegor)",
     "region_slug": "landes", "location": (-1.443, 43.665),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Weltklasse-Beachbreak in Hossegor, gespeist "
        "von einem Unterwassercanyon: schwere, hohle Barrels direkt am Strand, "
        "bis etwa 4 m. Die Welle, die im Herbst Profis aus aller Welt und die "
        "WSL (Quiksilver Pro) anzieht. Der Shorebreak kann an großen Tagen "
        "richtig gefährlich sein — nur für erfahrene Surfer.",
        "tide": "mid"},
     "facilities": {"food": {"available": True, "note": "Beachbars in Strandnähe"}}},

    {"slug": "landes-la-sud", "name": "La Sud (Hossegor)",
     "region_slug": "landes", "location": (-1.440, 43.655),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "beginner",
     "water_character": "welle_klein", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Der geschütztere, einsteigerfreundlichste "
        "Spot am Strand von Hossegor mit kopfhohen Wellen im Frühjahr und "
        "Herbst. Hier operieren im Sommer die meisten Surfschulen. Gute Wahl "
        "zum Lernen, wenn La Gravière zu schwer läuft. Warmes Wasser im "
        "Spätsommer.",
        "tide": "mid"},
     "facilities": {"food": {"available": True, "note": "Beachbars in Strandnähe"},
        "school": {"available": True, "note": "Surfschulen im Sommer aktiv"}}},

    {"slug": "landes-les-estagnots", "name": "Les Estagnots (Seignosse)",
     "region_slug": "landes", "location": (-1.410, 43.700),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Kräftiger, schneller Beachbreak in "
        "Seignosse nördlich von Hossegor mit hohlen Wellen über Sandbänken. "
        "Für erfahrene Surfer; die Sandbänke verschieben sich mit den "
        "kräftigen Gezeiten. Im Herbst mit den besten Swells. Teil des "
        "dichten Landes-Beachbreak-Korridors.",
        "tide": "mid"}},

    {"slug": "donegal-bundoran-peak", "name": "The Peak (Bundoran)",
     "region_slug": "donegal", "location": (-8.283, 54.478),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "reef", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Signaturwelle von Irlands Surf-Hauptstadt "
        "Bundoran: ein kraftvoller, hohler Rechts-Riffbrecher, der zu den "
        "besten Barrels des Landes zählt. Volle Nordatlantik-Energie über "
        "Fels — für erfahrene Surfer, im Winter mit dickem Neopren, Boots und "
        "Haube. In der Umgebung gibt es weitere Wellen für alle Level.",
        "tide": "mid"},
     "facilities": {"food": {"available": True, "note": "Pubs/Restaurants im Surfort"},
        "school": {"available": True, "note": "Surfschulen im Ort (Surf-Hauptstadt)"}}},

    {"slug": "clare-lahinch", "name": "Lahinch",
     "region_slug": "clare", "location": (-9.348, 52.933),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "beginner",
     "water_character": "welle_klein", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Surf-Hub an der Westküste Irlands mit "
        "verlässlichen, einsteigerfreundlichen Beachbreaks und einer starken "
        "Surf-Community. Gute Basis zum Lernen mit mehreren Schulen im Ort. "
        "In der Nähe liegen anspruchsvollere Riffe für Fortgeschrittene. "
        "Kühles Wasser, ganzjährig Neopren.",
        "tide": "mid"},
     "facilities": {"food": {"available": True, "note": "Cafés/Pubs im Surfort"},
        "school": {"available": True, "note": "Surfschulen im Ort"}}},

    {"slug": "caithness-thurso-east", "name": "Thurso East",
     "region_slug": "caithness", "location": (-3.516, 58.598),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "reef", "level": "advanced",
     "water_character": "welle_gross", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Weltklasse-Rechts-Riffbrecher im hohen "
        "Norden Schottlands, der vor einer Burg über einer flachen Felsplatte "
        "läuft — schnell, hohl und kraftvoll bei Nordswell und südlichem "
        "Wind. Kalt (im Winter um 8 °C), abgelegen und fordernd, aber von "
        "herausragender Qualität. Hat WSL-Events beherbergt. Nur für "
        "erfahrene Surfer.",
        "tide": "mid-low"},
     "facilities": {"school": {"available": True, "note": "Verleih/Repair in der Region"}}},

    {"slug": "cornwall-fistral", "name": "Fistral Beach (Newquay)",
     "region_slug": "cornwall", "location": (-5.100, 50.416),
     "sports": ["surf"],
     "water_type": "ocean", "bottom_type": "sand", "level": "beginner",
     "water_character": "welle_klein", "style": ["wave_riding"],
     "status": "draft",
     "editorial": {"description": "Der bekannteste Surfstrand Großbritanniens "
        "und Zentrum der englischen Surfkultur mit lebendiger Szene und "
        "vielen Schulen. Weiche Beachbreak-Wellen für Einsteiger und "
        "punchige Peaks für erfahrenere Surfer. Austragungsort der "
        "Boardmasters. Gut erschlossen mit voller Strandinfrastruktur.",
        "tide": "mid"},
     "facilities": {"food": {"available": True, "note": "Cafés/Restaurants am Strand"},
        "school": {"available": True, "note": "Zahlreiche Surfschulen"}}},
]


# Normalise compass-letter wind directions → 45° {min,max} windows in place, so
# the stored editorial is engine-native (scoring gates + orientation similarity).
for _s in SPOTS:
    _ed = _s.get("editorial")
    if _ed:
        _uwd = _ed.get("usable_wind_directions")
        if isinstance(_uwd, list) and _uwd and isinstance(_uwd[0], str):
            _ed["usable_wind_directions"] = _compass_to_windows(_uwd)

# Every spot gets the same placeholder hero its region gets — derived from the
# slug, so it is one line here instead of 40 copy-pasted dicts. Until Sprint 1
# the seed wrote images for regions only and silently dropped them for spots.
for _s in SPOTS:
    _s.setdefault("image", _img(_s["slug"], kind="spot"))
