"""Researched best-wind directions for the canonical spot catalogue.

Directions are meteorological (the direction the wind comes from).  Sources
were checked on 2026-11-08.  ``verified`` is used only where the cited page
states the usable/best direction explicitly; broader guide syntheses remain
``unreviewed`` so the dashboard can distinguish evidence from inference.
"""

from __future__ import annotations


def _row(directions, url, title, publisher, *, verified=True, note=None):
    default_note = (
        "Quelle nennt diese Richtungen als beste bzw. nutzbare Windrichtungen."
        if verified
        else "Aus dem regionalen Spotguide und der Küstenausrichtung abgeleitet; redaktionelle Einzelprüfung ausstehend."
    )
    return {
        "directions": list(directions),
        "url": url,
        "title": title,
        "publisher": publisher,
        "verification_status": "verified" if verified else "unreviewed",
        "note": note or default_note,
    }


BEST_WIND_RESEARCH = {
    # Tarifa — Levante/Poniente; the exact usable side differs by beach.
    "tarifa-los-lances": _row(("E", "W"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", verified=False),
    "tarifa-valdevaqueros": _row(("E", "ENE", "W"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", verified=False),
    "tarifa-balneario": _row(("E", "ENE"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", verified=False),
    "tarifa-punta-paloma": _row(("E", "ENE"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", verified=False),
    "tarifa-arte-vida": _row(("E", "ENE"), "https://www.windmaster.app/blog/kitesurfing-tarifa", "Kitesurfing in Tarifa: spots and winds", "Windmaster", verified=False),

    # Sardinia.
    "sardinia-porto-pollo": _row(("W", "NW"), "https://www.ventosurf.com/spot/porto-pollo-sardinien", "Porto Pollo Sardinia", "VentoSurf"),
    "sardinia-capo-mannu": _row(("NE", "E", "SE"), "https://surfomondo.it/spot/capo-mannu", "Capo Mannu: spot e condizioni surf", "Surfomondo"),
    "sardinia-poetto": _row(("S", "SE"), "https://aurabeach.app/blog/spiagge-kite-windsurf-sardegna", "Migliori spiagge per kite e windsurf in Sardegna", "AURA Beach", verified=False),

    # German Baltic.
    "laboe": _row(("NE", "SW"), "https://kiel.surfers-p.de/spot-laboe", "Spot Laboe", "Wassersport Center Laboe"),
    "stein": _row(("N", "NE", "NW"), "https://www.spotnetz.de/w/deutschland/schleswig-holstein/kieler-bucht/", "Kieler Bucht Spotguide", "Spotnetz", verified=False),
    "schilksee": _row(("NE", "E", "SW"), "https://www.spotnetz.de/w/deutschland/schleswig-holstein/kieler-bucht/", "Kieler Bucht Spotguide", "Spotnetz", verified=False),
    "heidkate": _row(("W", "NW", "N", "NE"), "https://www.kite-buddy.de/kitespot-heidkate", "Kitespot Heidkate", "KITE BUDDY", verified=False),
    "fehmarn-wulfener-hals": _row(("W", "NW", "E", "SE"), "https://surfspot.de/surfspots/europa/deutschland/wulfener-hals-fehmarn/", "Wulfener Hals (Fehmarn)", "surfspot.de"),

    # Canary Islands.
    "fuerteventura-sotavento": _row(("N", "NE"), "https://windmaster.app/blog/kitesurfing-in-fuerteventura", "Kitesurfing in Fuerteventura", "Windmaster"),
    "fuerteventura-flag-beach": _row(("NW", "N", "NE"), "https://kitewithjaja.com/en/guides/kitesurfing-canary-islands/", "Kitesurfing Canary Islands", "Kite with Jaja"),
    "fuerteventura-el-cotillo": _row(("N", "NW"), "https://windmaster.app/blog/kitesurfing-in-fuerteventura", "Kitesurfing in Fuerteventura", "Windmaster"),
    "fuerteventura-majanicho": _row(("E",), "https://kitewithjaja.com/en/guides/kitesurfing-canary-islands/", "Kitesurfing Canary Islands", "Kite with Jaja"),
    "fuerteventura-matas-bay": _row(("N", "NE"), "https://windmaster.app/blog/kitesurfing-in-fuerteventura", "Kitesurfing in Fuerteventura", "Windmaster"),
    "lanzarote-costa-teguise": _row(("N", "NE"), "https://www.casalosalisios.com/blog/windsurfing-costa-teguise/", "Windsurfing in Costa Teguise", "Casa Los Alisios"),
    "tenerife-el-medano": _row(("NE", "ENE"), "https://www.hightech.be/site/assets/files/2621/el_medano_duotone_pro_dpc.pdf", "El Médano Duotone Pro Center spot description", "Duotone Pro Center"),
    "gran-canaria-pozo-izquierdo": _row(("N", "NE"), "https://www.pozowinds.com/spots-windsurf-gran-canaria/", "Windsurf spots Gran Canaria", "Pozowinds", verified=False),

    # Greece — Meltemi sectors; shared regional guides are intentionally pending review.
    "rhodes-prasonisi": _row(("NW",), "https://hanglos.nl/kitereizen/rhodos", "Kitesurfen op Rhodos", "Hanglos", verified=False),
    "rhodes-theologos": _row(("W", "NW"), "https://hanglos.nl/kitereizen/rhodos", "Kitesurfen op Rhodos", "Hanglos", verified=False),
    "naxos-mikri-vigla": _row(("N", "NE"), "https://www.greeka.com/cyclades/naxos/sports/windsurfing/", "Windsurfing in Naxos", "Greeka", verified=False),
    "paros-pounda": _row(("N", "NE"), "https://www.greeka.com/cyclades/paros/sports/windsurfing/", "Windsurfing in Paros", "Greeka", verified=False),
    "kos-psalidi": _row(("W", "NW"), "https://www.greeka.com/dodecanese/kos/sports/windsurfing/", "Windsurfing in Kos", "Greeka", verified=False),
    "lemnos-keros": _row(("N", "NE"), "https://www.surfclubkeros.com/", "Keros Surf Club spot information", "Surf Club Keros", verified=False),

    # Mediterranean / North Sea wind spots.
    "sicily-lo-stagnone": _row(("N",), "https://www.dpc-sicily.com/fileadmin/user_upload/dpcsicily/travel_information/DPC_Sicily_Travel_Information.pdf", "DPC Sicily travel information", "Duotone Pro Center Sicily"),
    "languedoc-leucate": _row(("NW", "SE"), "https://spots.mywatersessions.com/spots/leucate-la-franqui", "Leucate / La Franqui spot guide", "MyWaterSessions"),
    "zeeland-brouwersdam": _row(("SW", "W", "NW"), "https://www.hangloose.nl/brouwersdam/", "Brouwersdam spot information", "Hangloose", verified=False),

    # Portugal — surf winds are the clean/offshore sectors for each break.
    "ericeira-ribeira-dilhas": _row(("NE", "E", "SE"), "https://makaisurf.app/spots/ribeira-dilhas", "Ribeira d'Ilhas surf guide", "Makai"),
    "ericeira-coxos": _row(("E", "SE"), "https://www.cm-mafra.pt/cmmafra/uploads/writer_file/document/2999/guiasurf2020_digital_leve_v.pdf", "Ericeira surf guide", "Município de Mafra", verified=False),
    "ericeira-sao-lourenco": _row(("E", "SE"), "https://www.cm-mafra.pt/cmmafra/uploads/writer_file/document/2999/guiasurf2020_digital_leve_v.pdf", "Ericeira surf guide", "Município de Mafra", verified=False),
    "ericeira-foz-do-lizandro": _row(("E", "SE"), "https://www.cm-mafra.pt/cmmafra/uploads/writer_file/document/2999/guiasurf2020_digital_leve_v.pdf", "Ericeira surf guide", "Município de Mafra"),
    "peniche-supertubos": _row(("N", "NE", "E"), "https://www.visitportugal.com/en/content/surfing-and-bodyboarding", "Surfing and bodyboarding", "Turismo de Portugal", verified=False),
    "peniche-baleal": _row(("S", "SW"), "https://www.cm-peniche.pt/visitar/surf", "Surf in Peniche", "Município de Peniche", verified=False),
    "nazare-praia-do-norte": _row(("E", "SE"), "https://www.visitportugal.com/en/content/nazare-waves", "Nazaré waves", "Turismo de Portugal", verified=False),
    "cascais-carcavelos": _row(("N", "NE", "NW"), "https://www.cascais.pt/sites/default/files/anexos/gerais/impacte_da_urbanizacao_de_carcavelos-sul_sobre_o_regime_de_ventos_na_praia.pdf", "Wind regime at Carcavelos beach", "Município de Cascais", verified=False),
    "cascais-guincho": _row(("E", "SE"), "https://www.visitcascais.com/en/locais/guincho-beach", "Guincho Beach", "Visit Cascais", verified=False),
    "sintra-praia-grande": _row(("E", "SE"), "https://visitsintra.travel/en/visit/beaches/praia-grande", "Praia Grande", "Visit Sintra", verified=False),

    # Bay of Biscay / Landes.
    "basque-mundaka": _row(("S", "SW"), "https://kirolur.bizkaia.eus/documents/d/kirolur/a-2025-03-05-bizkaia-region-europea_en", "Bizkaia European Region of Sport", "Bizkaia", verified=True),
    "basque-zarautz": _row(("S", "SE"), "https://turismo.euskadi.eus/en/surf-spots/zarautz/webtur00-content/en/", "Zarautz surf spot", "Basque Country Tourism", verified=False),
    "cantabria-somo": _row(("S", "SE", "E", "NE"), "https://turismodecantabria.com/wp-content/uploads/2023/06/aeaa3219-aa7b-ab9b-8651-3d1384980b0c.pdf", "Cantabria surf guide", "Cantabria Tourism"),
    "asturias-rodiles": _row(("S", "SW"), "https://www.turismoasturias.es/en/descubre/costa/playas/playa-de-rodiles", "Rodiles beach", "Turismo Asturias", verified=False),
    "landes-la-graviere": _row(("E", "NE"), "https://conditionssurf.fr/spots/hossegor", "Surf report Hossegor", "Conditions Surf"),
    "landes-la-sud": _row(("E", "NE"), "https://hossegorfrance.com/breaks/", "Hossegor breaks", "Hossegor France", verified=False),
    "landes-les-estagnots": _row(("E", "NE"), "https://conditionssurf.fr/spots/hossegor", "Surf report Hossegor", "Conditions Surf"),

    # Atlantic islands / UK.
    "donegal-bundoran-peak": _row(("ESE", "SE", "SSE"), "https://shoreforecast.com/en/ireland/bundoran-the-peak/", "Bundoran – The Peak surf forecast", "Shore Forecast"),
    "clare-lahinch": _row(("E", "SE"), "https://www.discoverireland.ie/clare/lahinch-beach", "Lahinch Beach", "Discover Ireland", verified=False),
    "caithness-thurso-east": _row(("S", "SW"), "https://www.surf-forecast.com/breaks/Thurso-East", "Thurso East surf forecast", "Surf-Forecast", verified=False),
    "cornwall-fistral": _row(("E", "SE"), "https://www.visitnewquay.org/things-to-do/beaches/fistral-beach", "Fistral Beach", "Visit Newquay", verified=False),
}

