"""Write independent blind research for expansion batch 010."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def s(url, publisher, supports):
    return {"url": url, "publisher": publisher, "supports": supports}


def r(name, country, lat, lon, identity, sports, conditions, rules, value, sources, verdict):
    return {
        "name": name,
        "country": country,
        "identity": identity,
        "entry": {"lat": lat, "lon": lon, "status": "approximate_discovery_point_exact_launch_open"},
        "sports": sports,
        "conditions": conditions,
        "access_rules": rules,
        "trip_value": value,
        "image_review": "searched_open_not_approved",
        "sources": sources,
        "blind_verdict": verdict,
    }


MINISTRY_SPORT = "https://www.tourism.government.bg/sites/tourism.government.bg/files/uploads/info_materials/eng/sport.pdf"
MINISTRY_COAST = "https://www.tourism.government.bg/sites/tourism.government.bg/files/uploads/info_materials/eng/black_sea_coast.pdf"

S = {
    "durankulak": [
        s("https://www.ventosurf.com/spot/durankulak-suedstrand-kartaliy", "VentoSurf", ["spot_identity", "season", "wind", "level", "no_lifeguard"]),
        s("https://bulgariatravel.org/wp-content/uploads/2021/03/Slow-tourism-eng-MT-2-3.pdf", "Bulgaria Travel", ["wild_beach", "lake", "nature_value"]),
    ],
    "krapets": [
        s("https://www.ikointl.com/destinations/kitesurfing-bulgaria/spots/krapets", "International Kiteboarding Organization", ["season", "wind", "waves", "level"]),
        s("https://bulgariatravel.org/wp-content/uploads/2021/03/Slow-tourism-eng-MT-2-3.pdf", "Bulgaria Travel", ["wide_shallow_beach", "wild_nature", "destination"]),
        s(MINISTRY_SPORT, "Bulgarian Ministry of Tourism", ["popular_surf_destination"]),
    ],
    "albena": [
        s(MINISTRY_SPORT, "Bulgarian Ministry of Tourism", ["popular_surf_destination"]),
        s("https://albena.bg/sports/water-sports", "Albena resort", ["windsurf", "water_sports", "services"]),
    ],
    "asparuhovo": [
        s("https://visit.varna.bg/en/beach-asparuhovo.html", "Visit Varna", ["beach_dimensions", "shallows", "services", "canal_boundary"]),
        s("https://visit.varna.bg/bg/water-sports-1.html", "Visit Varna", ["windsurf", "kitesurf", "clubs", "bay_breeze"]),
    ],
    "kamchia": [
        s("https://pdbase.government.bg/zpo/bg/area.jsp?NEM_Partition=1&areaID=11&categoryID=1", "Bulgarian protected-area register", ["strict_reserve", "access_limits"]),
        s("https://www.moew.government.bg/en/the-ministry-of-environment-and-water-declared-protected-zone-kamchiya/", "Bulgarian environment ministry", ["protected_zone", "marine_and_dune_habitats"]),
    ],
    "obzor": [
        s("https://windsurfbulgaria.adbtc.info/spots/obzor", "Windsurf Bulgaria", ["windsurf_claim", "levels", "amenities"]),
        s(MINISTRY_COAST, "Bulgarian Ministry of Tourism", ["coast_destination", "regional_wind_context"]),
    ],
    "sunny": [
        s("https://www.visitnessebar.bg/dataen/77", "Nessebar municipality tourism", ["long_beach", "generic_water_sports"]),
        s("https://surfschoolbg.com/en/", "Extreme Surf School", ["lessons", "Sunny_Beach_North", "Nessebar_South"]),
    ],
    "pomorie": [
        s(MINISTRY_SPORT, "Bulgarian Ministry of Tourism", ["popular_surf_destination"]),
        s("https://rsis.ramsar.org/RISapp/files/RISrep/BG1229RIS.pdf", "Ramsar Sites Information Service", ["wetland_status", "recreation_context", "management_constraints"]),
    ],
    "sarafovo": [
        s("https://www.unplug-kitesurf.com/spots/sarafovo-bulgaria", "Unplug Kitesurf", ["wind_directions", "flat_chop_waves", "levels", "hazards"]),
        s("https://eyca.org/discounts/5b2a84ca3145ce59aebf1dd9", "European Youth Card Association", ["IKO_school", "Burgas_bay", "lessons"]),
        s(MINISTRY_SPORT, "Bulgarian Ministry of Tourism", ["Burgas_surf_destination"]),
    ],
    "atanasovsko": [
        s("https://natura2000.egov.bg/PublicDownloads/Auto/PS_SCI/BG0000270/BG0000270_PS_16.pdf", "Bulgarian Natura 2000 portal", ["protected_habitats", "management"]),
        s("https://rsis.ramsar.org/RISapp/files/RISrep/BG292RIS_2001_en.pdf", "Ramsar Sites Information Service", ["wetland_status", "bird_value"]),
    ],
    "gradina": [
        s(MINISTRY_COAST, "Bulgarian Ministry of Tourism", ["best_windsurf_conditions", "Gradina"]),
        s("https://surfhouse.bg/windsurf-school-gradina/", "Surf House Gradina", ["school", "equipment", "beginner_advanced", "operating_history"]),
    ],
    "harmanite": [
        s("https://plajovete.bg/en/beaches/xarmanite", "Bulgarian beaches portal", ["windsurf_available", "shallows", "lifeguard", "urban_beach"]),
        s("https://www.sozopolis.bg/en/activities/water-sports-sozopol", "Sozopolis destination portal", ["centres", "schools", "windsurf_on_windy_days"]),
    ],
    "ahtopol": [
        s("https://windsurfbulgaria.adbtc.info/spots/ahotopol", "Windsurf Bulgaria", ["windsurf_claim", "strong_wind", "waves", "rock_hazard"]),
        s(MINISTRY_COAST, "Bulgarian Ministry of Tourism", ["south_coast_destination", "regional_context"]),
    ],
    "silistar": [
        s(MINISTRY_SPORT, "Bulgarian Ministry of Tourism", ["popular_surf_destination"]),
        s("https://pdbase.government.bg/zpo/en/area.jsp?NEM_Partition=1&areaID=192&categoryID=6", "Bulgarian protected-area register", ["protected_area", "identity", "management_need"]),
    ],
    "mamaia": [
        s("https://ctseaus.ro/en/turism-activ/", "Constanta active-tourism portal", ["kite", "windsurf", "Lake_Siutghiol", "WEGO"]),
        s("https://www.xtremespots.com/board-sports/kiteboarding-kitesurfing/h2o-beach-constanta-romania/", "Xtreme Spots", ["H2O_identity", "season", "thermal", "launch", "crowding"]),
    ],
    "constanta": [
        s("https://ctseaus.ro/en/turism-activ/", "Constanta active-tourism portal", ["WEGO_kite_spot", "location_context"]),
        s("https://www.spots4kite.com/spots/wego-kite-spot/", "Spots4Kite", ["city_spot", "pier_hazard", "water_state"]),
    ],
    "corbu": [
        s("https://www.cjc.ro/dyn_doc/turism/1.5-Ruta_multi-culturala_ecoturistica.pdf", "Constanta County Council", ["biosphere_reserve", "natural_beach", "tourism_value"]),
        s("https://consilierturism.ro/destinatii/asemanari-si-diferente-intre-plajele-corbu-si-vadu/", "Consilier Turism", ["permit", "vehicle_restrictions", "no_lifeguard"]),
        s("https://cdpqb6wwgd.infopensiuni.ro/cazare-corbu/obiective-turistice-corbu/plaja-corbu_7132", "InfoPensiuni", ["kitesurf_claim", "windsurf_claim"]),
    ],
    "vadu": [
        s("https://www.cjc.ro/dyn_doc/turism/1.5-Ruta_multi-culturala_ecoturistica.pdf", "Constanta County Council", ["biosphere_reserve", "natural_beach"]),
        s("https://www.info-delta.ro/ce-ai-voie-sa-faci-pe-plajele-neamenajate-vadu-corbu-si-midia-din-delta-dunarii-2022/", "Info Delta", ["reserve_rules", "tourist_zones", "access_limits"]),
    ],
    "portitei": [
        s("https://visitjurilovca.ro/en/descopera/gura-portitei/", "Visit Jurilovca", ["destination", "lagoon_sea_identity", "boat_access"]),
        s("https://guraportitei.ro/en/", "Gura Portitei resort", ["accommodation", "activities", "access"]),
    ],
    "sfantu": [
        s("https://visit-delta.ro/en/natural-attractions/beaches/", "Visit Delta", ["wild_beach", "shallow_water", "protected_plant", "mouth_hazard"]),
        s("https://www.info-delta.ro/ce-ai-voie-sa-faci-pe-plajele-neamenajate-vadu-corbu-si-midia-din-delta-dunarii-2022/", "Info Delta", ["reserve_rules", "permitted_activities", "access_limits"]),
    ],
    "eforie": [
        s("https://www.robgjobs.eu/wp-content/uploads/2019/02/Brosura-100pg-editia-a-patra.pdf", "RO-BG Jobs project", ["historic_windsurf_school_claim", "regional_sport"]),
        s("https://romania.travel/eforie-nord", "Romania Travel", ["resort_identity", "beach_services"]),
    ],
    "limanu": [
        s("https://portal.rna.ro/SiteAssets/servicii/personal-navigant/Lista%20furnizori%20aprobati%20ptr%20cursuriCAA.pdf", "Romanian Naval Authority", ["approved_sailing_provider", "Limanu_Mangalia"]),
        s("https://www.mmediu.gov.ro/app/webroot/uploads/files/PASM.pdf", "Romanian environment ministry", ["Limanu_marina", "lake_context"]),
    ],
    "kilyos": [
        s("https://dev.goturkiye.com/istanbul/kilyos", "GoTurkiye", ["windsurf", "kiteboard", "Burc_Beach", "destination"]),
        s("https://www.bumed.org.tr/pdf/calisma_raporlari/2011_faaliyet_raporu.pdf", "Bogazici University Alumni Association", ["kite_world_championship", "windsurf", "kiteboard", "facilities"]),
    ],
    "gumusdere": [
        s("https://www.bilgeozturkkiteclub.com/subelerimiz/kilyos-istanbul", "Bilge Ozturk Kite Club", ["Kilyos_branch", "lessons", "rental", "strong_wind_and_waves"]),
        s("https://lets-kite.com/en/spots/9869/kitesurf/gumusdere-beach-kilyos", "Let's Kite", ["same_coastal_spot", "kitesurf", "wingfoil", "windsurf"]),
        s("https://sariyer.bel.tr/ckuploads/ckfiles/Sariyer%20Yasam%20Rehberi%202021%2817.12.2021%29.pdf", "Sariyer municipality", ["Gumusdere_beaches", "clean_water", "identity"]),
    ],
    "silivri": [
        s("https://advenway.com/en/tools/windsurf-conditions/silivri-semizkum/", "Advenway", ["spot_identity", "flat_water", "experienced", "club", "modelled_wind"]),
        s("https://www.istanbulwindsurfcenter.com/istanbulda-ruzgar-sorfu/", "Istanbul Windsurf Center", ["Silivri_area", "Poyraz", "wide_uncrowded_area"]),
    ],
}

spots = [
    r("Durankulak – Kartaliy South Beach", "BG", 43.666, 28.572, "The exposed beach south of Durankulak, outside the lake itself.", ["kitesurf", "windsurf"], "Seasonal NE–SE wind, waves and an unguarded long beach suit self-sufficient intermediate or expert riders.", "Confirm the exact launch against the protected lake and dune zones; no lifeguard or verified rescue.", "Wild coast and credible conditions are attractive, but legal launch and current sport-use evidence remain incomplete.", S["durankulak"], "hold_for_more_research"),
    r("Krapets", "BG", 43.624, 28.574, "The long open beach south of Krapets village.", ["kitesurf", "windsurf"], "May–September winds, waves and broad shallow water are documented for intermediate and advanced kiters.", "Map swimmer and dune corridors and confirm current rescue/operator coverage.", "A wild, spacious coast with international sport documentation supports worth_trip after operational correction.", S["krapets"], "accept_after_correction"),
    r("Albena", "BG", 43.369, 28.082, "The organised Albena resort beach north of Varna, not the whole Balchik coast.", ["windsurf"], "Official national material names Albena as a popular surf destination and the resort advertises windsurf services.", "Pin the current watersports launch and swimmer separation; the evidence lacks a detailed wind profile.", "Services and destination infrastructure support consideration, but specialist travel value and recurring conditions are not sufficiently demonstrated.", S["albena"], "reject_insufficient_trip_value"),
    r("Asparuhovo, Varna", "BG", 43.175, 27.904, "The long shallow beach south of Varna's canal entrance.", ["windsurf", "kitesurf"], "Varna Bay has regular breeze and active clubs; the beach is long, wide and shallow.", "Keep clear of the canal, fishing port, navigation and swimmer sectors; identify the club launch.", "An accessible urban training venue is useful, but the sources do not establish a dedicated-trip proposition.", S["asparuhovo"], "reject_insufficient_trip_value"),
    r("Kamchia coast", "BG", 43.027, 27.897, "The beach and river-mouth coast adjoining the strict Kamchia reserve.", ["kitesurf", "windsurf"], "No reliable source establishes recurring wind-sport use at a legal launch.", "Strict-reserve, marine and dune protection require explicit authority permission and a launch outside prohibited habitat.", "Natural value alone cannot substitute for evidence of legal watersports use.", S["kamchia"], "reject_insufficient_evidence"),
    r("Obzor", "BG", 42.819, 27.884, "The main Obzor beach, not an identified specialist launch.", ["windsurf", "kitesurf"], "A specialist directory claims windsurf use, while official material only supplies broad regional context.", "Confirm a current launch, operator, rescue and recurring wind window.", "The available evidence does not establish either robust specialist use or distinctive trip value.", S["obzor"], "reject_insufficient_evidence"),
    r("Sunny Beach / Nessebar", "BG", 42.687, 27.714, "The school-operated sectors at Sunny Beach North and Nessebar South, not the entire resort strip.", ["windsurf", "kitesurf"], "A current school proves lessons and use on a very long serviced resort beach.", "Split the two launch sectors and retain swimmers, seasonal crowding and harbour boundaries.", "Strong resort utility does not by itself show distinctive wind, water or specialist travel value.", S["sunny"], "reject_insufficient_trip_value"),
    r("Pomorie", "BG", 42.560, 27.646, "The sea-side sport beach near Pomorie, not protected Lake Pomorie.", ["windsurf", "kitesurf"], "National tourism identifies Pomorie as a surf destination, but exact active launch and conditions are unresolved.", "Separate sea launch from Ramsar wetland, and confirm current permission, operator and rescue.", "Potential destination value exists, but wetland boundaries and operational evidence block confirmation.", S["pomorie"], "hold_for_more_research"),
    r("Sarafovo, Burgas", "BG", 42.562, 27.521, "The Sarafovo beach launch on Burgas Bay.", ["kitesurf", "windsurf"], "E–SW winds produce flat water, chop or small waves; a documented IKO school serves multiple levels.", "Map the launch around swimmers, groynes and airport/urban constraints and verify current rescue.", "Established instruction, usable condition range and Burgas access support worth_trip after launch correction.", S["sarafovo"], "accept_after_correction"),
    r("Lake Atanasovsko", "BG", 42.544, 27.473, "The protected saline lake north of Burgas, not adjacent Sarafovo sea beach.", ["windsurf", "kitesurf"], "No reliable source establishes legal wind-sport use.", "Ramsar and Natura 2000 habitat protection is central; do not infer access from adjacent roads or beaches.", "The candidate lacks discipline-specific and legal-use evidence.", S["atanasovsko"], "reject_insufficient_evidence"),
    r("Gradina, Chernomorets", "BG", 42.431, 27.649, "The Gradina/Zlatna Ribka windsurf beach between Chernomorets and Sozopol.", ["windsurf", "wing"], "The tourism ministry identifies some of Bulgaria's best windsurf conditions here; a long-running school serves beginner through advanced levels.", "Pin the school/launch and swimmer/campsite separation and retain seasonal rescue information.", "National recognition, mature instruction and a broad sandy bay support worth_trip.", S["gradina"], "accept_as_worth_trip"),
    r("Harmanite, Sozopol", "BG", 42.412, 27.696, "The guarded urban Harmanite beach south of Sozopol old town.", ["windsurf"], "Windsurf is available on windy days, with shallow water and nearby centres.", "Seasonal swimmer density and guarded bathing zones constrain launch use.", "This is a convenient activity beach, but sources do not show a recurring specialist condition or dedicated-trip value.", S["harmanite"], "reject_insufficient_trip_value"),
    r("Ahtopol", "BG", 42.098, 27.939, "The rocky/open coast around Ahtopol; an exact legal launch is not verified.", ["windsurf"], "One low-authority directory claims strong summer/autumn wind, waves and advanced use.", "Confirm the launch, rock hazards, protected-coast rules, rescue and a current operator/community source.", "A single specialist claim plus general tourism context is insufficient.", S["ahtopol"], "reject_insufficient_evidence"),
    r("Silistar", "BG", 42.022, 28.007, "The small protected bay south of Sinemorets.", ["windsurf", "kitesurf"], "National tourism names Silistar among surf destinations, but no precise conditions or active launch are established.", "Explicit protected-area permission, beach zoning and access must be confirmed before recommending rigging or launch.", "The setting and national mention are promising, but conservation rules and weak operational detail require more research.", S["silistar"], "hold_for_more_research"),
    r("Mamaia – H2O Beach / Lake Siutghiol", "RO", 44.273, 28.618, "Two nearby but materially different sectors: H2O sea beach for kite and Lake Siutghiol clubs for windsurf.", ["kitesurf", "windsurf"], "H2O has a May–September thermal window, designated launch and services; the lake supports organised windsurf activity.", "Split sea and lake sectors before publication and retain crowding, swimmer and shore-infrastructure constraints.", "A mature activity scene and resort access support worth_trip once the mixed identity is corrected.", S["mamaia"], "accept_after_correction"),
    r("Constanța – Zoom / WEGO sector", "RO", 44.193, 28.655, "The documented WEGO/Zoom urban kite sector, replacing the unverified generic Modern Beach label.", ["kitesurf"], "An official active-tourism portal lists the spot; secondary detail describes flat-to-small-wave water beside an urban pier.", "Pin the current launch and document pier/rock, swimmers and any seasonal municipal restrictions.", "Verified use is useful locally, but sources do not establish a distinctive travel proposition.", S["constanta"], "reject_insufficient_trip_value"),
    r("Corbu beach", "RO", 44.378, 28.707, "The natural Corbu beach within the Danube Delta Biosphere Reserve tourism perimeter.", ["kitesurf", "windsurf"], "Low-authority local material reports windsurf/kitesurf use, but no supervised launch or robust conditions source is available.", "Reserve permit, vehicle rules, approved tourist zone and absence of lifeguard must be resolved with the authority.", "Wild-coast travel value is strong, but legal operation and sport evidence remain too uncertain.", S["corbu"], "hold_for_more_research"),
    r("Vadu beach", "RO", 44.450, 28.769, "The limited tourism-access part of Vadu's natural biosphere-reserve beach.", ["kitesurf", "windsurf"], "No reliable discipline-specific use or condition evidence was found.", "Reserve access, tourist-zone and vehicle restrictions apply; no launch should be inferred outside authorised areas.", "Scenery and wind exposure do not establish a legal wind-sport destination.", S["vadu"], "reject_insufficient_evidence"),
    r("Gura Portiței", "RO", 44.691, 28.942, "The boat-access settlement on the narrow Razim–Black Sea barrier.", ["kitesurf", "windsurf"], "Official destination and resort sources establish unusual lagoon/sea geography but not recurring wind-sport use.", "Confirm reserve rules, a legal launch, operator/rescue and transport of equipment.", "Exceptional scenery is not enough without discipline-specific evidence.", S["portitei"], "reject_insufficient_evidence"),
    r("Sfântu Gheorghe, Danube Delta", "RO", 44.896, 29.596, "The wild beach near the Sfântu Gheorghe arm mouth, outside the dangerous outlet itself.", ["kitesurf", "windsurf"], "The broad shallow wild beach has high landscape value, but no reliable wind-sport scene or launch is documented.", "Reserve rules, protected plants, no-lifeguard conditions and the river-mouth hazard require authority confirmation.", "Remote trip value is clear, yet legal and discipline-specific evidence is insufficient.", S["sfantu"], "reject_insufficient_evidence"),
    r("Eforie Nord", "RO", 44.067, 28.641, "The resort beach at Eforie Nord, with no currently verified specialist launch.", ["windsurf", "kitesurf"], "An older cross-border brochure mentions regional windsurf activity; current exact use and conditions are unverified.", "Confirm a current operator, launch, wind window and swimmer separation.", "Historic/general activity claims do not meet the evidence threshold.", S["eforie"], "reject_insufficient_evidence"),
    r("Limanu / Mangalia marina", "RO", 43.804, 28.531, "The Limanu lake marina and sailing-school area, not an evidenced windsurf spot.", ["sailing", "windsurf"], "Official records establish sailing instruction and marina use, but not windsurf/kite use or notable conditions.", "Do not generalise sailing permission to boards or kites; confirm any public launch separately.", "The candidate does not meet discipline-specific evidence requirements.", S["limanu"], "reject_insufficient_evidence"),
    r("Kilyos – Burç Beach", "TR", 41.251, 29.032, "The Burç Beach wind/kite sector on Istanbul's Black Sea coast.", ["windsurf", "kitesurf", "wavesurf"], "Strong Black Sea wind and waves support multiple disciplines; the beach has hosted a kiteboard world championship and provides sport facilities.", "Check current membership/guest access, operating season, rescue and swimmer separation before travel.", "Competition history, official destination recognition and proximity to Istanbul support worth_trip.", S["kilyos"], "accept_as_worth_trip"),
    r("Gümüşdere Beach, Kilyos", "TR", 41.254, 28.986, "The Gümüşdere/Goga school sector on the same wider Kilyos wind coast as Burç Beach.", ["kitesurf", "wing", "windsurf"], "A current kite club offers lessons and equipment on a strong-wind, wave-exposed Black Sea beach.", "Determine whether this should be a sector of one Kilyos record; confirm exact public access and rescue.", "It has credible sport value but should not become a second destination-level count without a defensible boundary.", S["gumusdere"], "accept_after_correction"),
    r("Silivri – Semizkum", "TR", 41.072, 28.161, "The Semizkum windsurf area west of Istanbul, not the whole Silivri shoreline.", ["windsurf"], "Secondary sources identify flat water, a club and Poyraz sessions, but modelled wind is relatively light and often offshore.", "Confirm the active club/launch and retain offshore-wind, experience and rescue warnings.", "Regional windsurf use is credible, but distinctive dedicated-trip value is not established.", S["silivri"], "reject_insufficient_trip_value"),
]

payload = {
    "schema_version": 1,
    "batch": "010",
    "research_mode": "independent_blind_before_local_comparison",
    "created_at": "2026-11-10",
    "independence_statement": "Saved before opening local spot, source, media or prior candidate records for these 25 names. Candidate selection used external discovery only.",
    "method_limits": [
        "Coordinates are approximate discovery points and do not prove a launch.",
        "Protected-area permission is unresolved unless explicitly sourced.",
        "Image candidates remain unapproved.",
        "Full draft/cloud duplication access remained unavailable.",
    ],
    "spots": spots,
}

assert len(spots) == 25 and all(len(item["sources"]) >= 2 for item in spots)
(ROOT / "batch-010-blind-research.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
