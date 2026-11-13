"""Write independent blind research for expansion batch 009."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def s(url, publisher, supports):
    return {"url":url, "publisher":publisher, "supports":supports}

def r(name, lat, lon, identity, sports, conditions, rules, value, sources, verdict):
    return {
        "name":name, "country":"GR", "identity":identity,
        "entry":{"lat":lat, "lon":lon, "status":"approximate_discovery_point_exact_launch_open"},
        "sports":sports, "conditions":conditions, "access_rules":rules,
        "trip_value":value, "image_review":"searched_open_not_approved",
        "sources":sources, "blind_verdict":verdict,
    }

S = {
 "chalikounas":[
  s("https://visit.corfu.gr/el/drasthriothtes/surf-center-corfu/","Visit Corfu",["daily_use","wind","school","reserve"]),
  s("https://www.visitgreece.gr/en/experiences/architecture/picturesque-villages/beaches-of-corfu","Visit Greece",["beach","shallow_water","wetland"])],
 "devils":[
  s("https://www.internationalwindsurfing.com/userfiles/documents/press_kit_karpathos_2008.pdf","International Windsurfing Association",["competition","wind_statistics","spot_identity"]),
  s("https://www.visitgreece.gr/islands/dodecanese/karpathos/","Visit Greece",["island_destination","access"])],
 "fanes":[
  s("https://site.rhodes.gr/tourist-guide/?lang=en","Municipality of Rhodes",["windsurf","kitesurf","centres"]),
  s("https://www.visitrhodes.com/what-to-see/beaches/fanes-beach","Visit Rhodes",["constant_wind","space","services"])],
 "kefalos":[
  s("https://www.kefaloswindsurfing.com/spot/","Kefalos Windsurfing",["thermal","Meltemi","flat_water","records"]),
  s("https://kos.gr/activities/wind-and-kite-surfing","Kos municipality tourism",["season","clubs","Kefalos"])],
 "nissakia":[
  s("https://www.thisisathens.org/activities/sports-outdoors/windsurfing-kitesurfing","Official Athens Guide",["conditions","levels","clubs","hazards"]),
  s("https://www.athensnauticalclub.gr/","Athens Nautical Club",["sports","closed_bay","events","access"])],
 "marmari_kos":[
  s("https://kos.gr/settlements/marmari","Kos municipality tourism",["wind_probability","clubs","beach"]),
  s("https://kos.gr/activities/wind-and-kite-surfing","Kos municipality tourism",["season","side_shore","levels"]),
  s("https://www.marmari-windsurfing.com/","Marmari Windsurfing",["current_season","rental","instruction"])],
 "marmari_evia":[
  s("https://www.greekmap.eu/index.php/api/pdf_export/287/en","Greek Map destination guide",["sport_use","wind","beach"]),
  s("https://www.amore.rs/wp-content/uploads/2014/12/Island-of-Evia-Tourist-Guide_2010_ENGLISH_.pdf","Evia tourism guide",["northerly_wind","currents","windsurf"])],
 "mikri":[
  s("https://www.naxos.gr/mikri-vigla-parthena-limanaki/?lang=en","Naxos municipality tourism",["sports","wind","beach_sections"]),
  s("https://www.naxos.gr/flisvos-sportclub-mikri-vigla-beach/?lang=en","Naxos municipality tourism",["Meltemi","season","school","rescue"])],
 "ftelia":[
  s("https://www.visitgreece.gr/en/experiences/nature/beaches/the-beaches-of-mykonos","Visit Greece",["windsurf_paradise","identity"]),
  s("https://www.visitgreece.gr/en/experiences/leisure/nightlife/mykonos-nightlife","Visit Greece",["strong_winds","surf_beaches"])],
 "paros":[
  s("https://www.visitgreece.gr/en/experiences/activities/eco-tourism-activities/sea-activities-on-paros","Visit Greece",["world_class_context","spot_split","conditions","levels"])],
 "golden":[
  s("https://sunwind.gr/","SunWind Surf Club",["Meltemi","school","rental","levels"])],
 "new_golden":[
  s("https://paroswindsurfcenter.com/","Paros Windsurf Center",["PWA","wind_reliability","school"])],
 "tsoukalia":[
  s("https://parola-paros-freepress.gr/en/playing-with-the-waves-surfing/","Parola Paros",["waves","reef","levels","facilities"]),
  s("https://lets-kite.com/en/spots/11718/tsoukalia-paros","Let's Kite",["Meltemi","season","hazards"])],
 "pounta":[
  s("https://www.paroskite.com/","Paros Kite",["steady_side_shore","school","international_draw"])],
 "ixia":[
  s("https://site.rhodes.gr/tourist-guide/?lang=en","Municipality of Rhodes",["ideal_conditions","centres","windsurf"]),
  s("https://www.aegeanislands.gr/pois/rhodes-water-sports-en/","Aegean Islands tourism",["Meltemi","season","popular_centres"])],
 "kokkari":[
  s("https://samosgreece.gr/en/beaches_e/","Samos municipality tourism",["constant_wind","windsurf","beach"]),
  s("https://tourism.samoscci.gr/minipage/index/en/activity/44811/s","Samos Chamber tourism",["school","cross_onshore","levels"])],
 "naxos_general":[
  s("https://www.naxos.gr/swim-sail-smooth-ride-the-wave/?lang=en","Naxos municipality tourism",["clubs","lagoon","kite_ban","conditions"]),
  s("https://www.naxos.gr/wp-content/uploads/2018/04/Naxos-Guide-EN.pdf","Naxos municipality tourism",["Meltemi","sports","clubs"])],
 "theologos":[
  s("https://www.visitrhodes.com/what-to-see/beaches/theologos-beach","Visit Rhodes",["strong_wind","windsurf","services"]),
  s("https://www.surftheologos.com/en/location/spot/","Surf and Kite Theologos",["20kt","side_onshore","season","rescue"])],
 "plaka":[
  s("https://www.ventosurf.com/school/plaka-watersports","VentoSurf",["school","Meltemi","launch","levels"])],
 "schinias":[
  s("https://www.visitgreece.gr/en/experiences/nature/gorges/schinias-marathon-national-park","Visit Greece",["national_park","Natura","shallow_water"]),
  s("https://www.welovemarathon.gr/beaches?lang=en","Marathon destination portal",["winter_kitesurf","access","fire_closure"])],
 "anavyssos":[
  s("https://www.thisisathens.org/activities/sports-outdoors/windsurfing-kitesurfing","Official Athens Guide",["south_wind_kite","gusts","club"]),
  s("https://thisisyourgreece.com/beaches/anavyssos-beach","This Is Your Greece",["windsurf_base","access","shallows"])],
 "iraklitsa":[
  s("https://www.visitkavala.gr/en/sightseeing/water-sports-2/","Visit Kavala",["windsurf","operator","beach"]),
  s("https://katatopisi.gr/en/beach/nea-iraklitsa/","Katatopisi",["bathing_water","wind_climatology","access"])],
 "paliouri":[
  s("https://visit-centralmacedonia.gr/en/what-to-do/73/sun-sea/103/paliouri-beach","Visit Central Macedonia",["beach_identity","destination"]),
  s("https://www.discovergreece.com/experiences/explore-timeless-villages-halkidiki","Discover Greece / Halkidiki Tourism",["general_water_sports","shallow_water"])],
 "volvi":[
  s("https://www.visitgreece.gr/routes/waterways-discovering-the-lakes","Visit Greece",["windsurf_destination","Rentina_wind","national_draw","protected_area"]),
  s("https://www.foreaskv.gr/wp-content/uploads/2021/03/xenoglwssos_podhlatikos_xartis.pdf","Koronia-Volvi National Park",["windsurf","protected_area","map"])],
 "vegoritida":[
  s("https://visit-centralmacedonia.gr/en/where-to-go/58/1-pella/36/lake-vegoritida-","Visit Central Macedonia",["sailing","canoe","environment"]),
  s("https://visitwestmacedonia.gr/places-box/limni-vegoritida/","Visit West Macedonia",["ecosystem","visitor_activities"]),
  s("https://katatopisi.gr/en/beach/vegoritida/","Katatopisi",["bathing_water","light_mean_wind"])],
}

spots = [
 r("Chalikounas, Corfu",39.448,19.875,"The long sand strip beside Lake Korission, not the whole southwest Corfu coast.",["windsurf","kitesurf"],
   "Regular afternoon northwesterly and shallow nearshore learning water; a school and rescue are documented.",
   "Map the legal sport section against the lake/dune nature reserve and current bathing zones.",
   "A distinctive sea-wetland setting with established daily use supports worth_trip after conservation correction.",S["chalikounas"],"accept_after_correction"),
 r("Devil's Bay / Paradise Beach, Karpathos",35.423,27.145,"A strong-wind Afiartis bay used for international windsurf competition.",["windsurf"],
   "Exceptionally reliable strong Meltemi and recorded competition conditions.",
   "Retain strong-wind level, rescue and exact bay boundaries.",
   "International competition history and exceptional wind place it above worth_trip.",S["devils"],"reject_as_world_class"),
 r("Fanes, Rhodes",36.356,27.986,"Fanes' open west-coast beach outside its fishing harbour.",["windsurf","kitesurf"],
   "Constant breeze, open rigging space and strong-wind exposure with rentals/services.",
   "Keep clear of the fishing harbour and mark swim, launch and strong-wind sectors.",
   "Defined dual-discipline beach, services and island setting support worth_trip.",S["fanes"],"accept_as_worth_trip"),
 r("Kefalos Bay, Kos",36.736,26.966,"The windsurf/wing bay stations, separate from nearby Kohilari kite and wave beaches.",["windsurf","wing"],
   "Accelerated Meltemi and local thermal produce very flat cross-offshore water, lighter mornings and strong afternoons.",
   "Pin the rescue-covered station area and retain offshore-wind and level/time guidance.",
   "Long records, high reliability, schools and condition variety support worth_trip.",S["kefalos"],"accept_as_worth_trip"),
 r("Nissakia / Agios Nikolaos, Artemida",37.983,24.015,"The Nissakia club and adjacent Agios Nikolaos sport sectors east of Athens.",["windsurf","kitesurf","wing"],
   "Strong exposed northerlies, flat water downwind and bump-and-jump waves upwind; water becomes crowded.",
   "Split ability sectors, confirm kite permission and attach rescue, swimmer and airport/harbour constraints.",
   "Long-running clubs, competition use and easy access support worth_trip after exact-zone correction.",S["nissakia"],"accept_after_correction"),
 r("Marmari, Kos",36.880,27.145,"Marmari's long north-coast sand beach and its wind/kite club sectors.",["windsurf","kitesurf","wing"],
   "High wind probability, steady side-shore summer Meltemi and channel acceleration.",
   "Pin the club/launch section and protect dunes, swimmers and nearby Alykes habitat.",
   "Officially recognised hotspot, multiple clubs and family services support worth_trip.",S["marmari_kos"],"accept_as_worth_trip"),
 r("Marmari – Megali Ammos, Evia",38.046,24.318,"Megali Ammos wind-sport beach in South Evia, not Marmari harbour.",["windsurf","kitesurf"],
   "Regular northerlies, waves, sheltered Petalioi-side waters and strong channel currents.",
   "Map the launch, currents, harbour/navigation separation and current operator/rescue coverage.",
   "Distinct sand-spit landscape and established sport use support worth_trip after safety correction.",S["marmari_evia"],"accept_after_correction"),
 r("Mikri Vigla, Naxos",37.027,25.370,"Mikri Vigla's divided Parthena/Limanaki bay with discipline-specific sections.",["windsurf","kitesurf"],
   "Side to side-onshore Meltemi May–October, sandy water, schools and rescue.",
   "Preserve the north/south section split and current swimmer/launch corridors.",
   "International meeting point, reliable wind and full services support worth_trip.",S["mikri"],"accept_as_worth_trip"),
 r("Ftelia, Mykonos",37.462,25.376,"The north-facing Ftelia bay, distinct from Kalafatis and other Mykonos wind beaches.",["windsurf"],
   "Exposed northerly Meltemi creates a recognised windsurf setting; detailed hazards and active services remain open.",
   "Pin the launch and document onshore strong-wind, wave, archaeological and bathing constraints.",
   "National tourism identifies a windsurf paradise, supporting worth_trip after operational correction.",S["ftelia"],"accept_after_correction"),
 r("Golden Beach, Paros",37.012,25.240,"Chrysi Akti's long shallow windsurf beach, separate from Tserdakia/New Golden.",["windsurf","wing"],
   "Northerly Meltemi dominates summer; shallow water and schools serve all levels.",
   "Keep the operational boundary with New Golden explicit and map schools/swimmers.",
   "Paros travel value, reliable wind and mature services support worth_trip.",S["paros"]+S["golden"],"accept_as_worth_trip"),
 r("New Golden Beach / Tserdakia, Paros",37.020,25.253,"The stronger-wind Tserdakia competition beach, not generic Golden Beach.",["windsurf","wing"],
   "The island's strongest winds, speed/jump conditions and an official former PWA World Cup venue.",
   "Retain expert wind, competition, rescue and beach-sector guidance.",
   "PWA history, global athlete draw and exceptional reliability exceed worth_trip.",S["paros"]+S["new_golden"],"reject_as_world_class"),
 r("Tsoukalia, Paros",37.078,25.261,"Northeast Paros wave-oriented windsurf beach.",["windsurf","wing","kitesurf"],
   "N/NNE Meltemi is slightly weaker than southern Paros; open waves and a rocky reef zone require experience.",
   "Mark reef/sandy entries, no-centre self-sufficiency, swimmers and strong-wind level.",
   "A quieter, wave-focused alternative supports worth_trip after hazard and launch correction.",S["tsoukalia"],"accept_after_correction"),
 r("Pounta, Paros",37.038,25.100,"Pounta's kite beach on the narrow Paros–Antiparos channel.",["kitesurf","windsurf","wing"],
   "Constant steady side-shore Meltemi accelerated by the channel, with established schools.",
   "Map launch/swim sectors and channel/boat traffic; do not confuse with Pounda Beach Club elsewhere.",
   "World-renowned kite beach, services and inter-island setting support worth_trip.",S["paros"]+S["pounta"],"accept_as_worth_trip"),
 r("Ixia Bay, Rhodes",36.422,28.187,"The Ixia windsurf centre strip on Rhodes' west coast.",["windsurf","wing"],
   "Strong April–October northwesterly Meltemi and wavy/choppy water; multiple centres operate.",
   "Select a centre/launch and retain pebbly shorebreak, gust, swimmer and rescue guidance.",
   "One of Rhodes' officially preferred windsurf areas with mature infrastructure supports worth_trip.",S["ixia"],"accept_as_worth_trip"),
 r("Kokkari, Samos",37.779,26.891,"Kokkari's north-facing pebbly beach and seasonal windsurf centre.",["windsurf"],
   "Terrain-enhanced constant cross-onshore northerlies, with wave/chop and quickly deepening water.",
   "Mark the supervised school section, pebble entry, swimmers, shorebreak and strong-wind limits.",
   "Distinct terrain wind, school and Samos destination support worth_trip.",S["kokkari"],"accept_as_worth_trip"),
 r("Agios Georgios, Naxos",37.096,25.371,"The southern windsurf end of Agios Georgios bay and its shallow lagoon area.",["windsurf","wing"],
   "Shallow calm lagoon enables beginner, speed, slalom and freestyle use under summer Meltemi.",
   "Kites are prohibited near the airport; pin the windsurf corridor and reef/swimmer boundary.",
   "Long-running clubs, friendly water and town access support worth_trip after exact-zone correction.",S["naxos_general"],"accept_after_correction"),
 r("Theologos, Rhodes",36.449,28.035,"Theologos' separated windsurf and kite stations on Rhodes' west coast.",["windsurf","kitesurf","wing"],
   "About 20 kt side-onshore southwest wind from midday, April–November, with rescue.",
   "Retain separated discipline zones, airport proximity, swimmer and stronger-gust guidance.",
   "Reliable conditions, full services and broad-level suitability support worth_trip.",S["theologos"],"accept_as_worth_trip"),
 r("Plaka, Naxos",37.054,25.368,"The organised windsurf school section on long Plaka/Maragkas beach.",["windsurf"],
   "Summer north Meltemi crosses a flat bay with wide sandy shallows and teaching for all levels.",
   "Pin the school section and distinguish it from Agios Georgios and Mikri Vigla; map swimmers.",
   "A long-running school and broad beach support worth_trip after identity correction.",S["naxos_general"]+S["plaka"],"accept_after_correction"),
 r("Laguna, Naxos",37.087,25.371,"The shallow Laguna/Flisvos windsurf water immediately adjoining Agios Georgios.",["windsurf","wing"],
   "An internationally used shallow lagoon suited to beginner, slalom and freestyle sessions.",
   "Kites are forbidden near the airport; determine whether this is one entry with Agios Georgios.",
   "Strong travel value exists, but the candidate identity requires consolidation.",S["naxos_general"],"accept_after_correction"),
 r("Schinias, Marathon",38.149,24.036,"The southern Schinias Bay wind-sport area inside a Natura 2000 national park.",["windsurf","kitesurf"],
   "Established wind use and winter southerly kitesurfing on a long shallow sandy bay.",
   "Current park permission, fire closures, vehicle access and exact launch sector require authority confirmation.",
   "Nature and sport value are strong, but protected-area rules block confirmation.",S["schinias"],"hold_for_more_research"),
 r("Anavyssos, Attica",37.728,23.944,"Athens Riviera windsurf base with conditional south-wind kitesurfing.",["windsurf","kitesurf"],
   "Flat/gusty local conditions; kitesurfing is specifically associated with southerly winds.",
   "Pin the club launch and retain gust, wind-direction and bathing restrictions.",
   "Useful regional access and training, but evidence does not show distinctive dedicated-trip value.",S["anavyssos"],"reject_insufficient_trip_value"),
 r("Nea Iraklitsa – Alana",40.877,24.318,"Alana beach windsurf candidate west of Kavala.",["windsurf"],
   "Official tourism calls the large beach suitable because of local winds, but coarse climatology is light and general water sports dominate.",
   "Confirm the exact wind window, operator status, launch and bathing corridor.",
   "Insufficient evidence of reliability or specialist travel value beyond a regional activity beach.",S["iraklitsa"],"reject_insufficient_trip_value"),
 r("Paliouri / Chrouso, Halkidiki",39.928,23.681,"Popular shallow resort beach with generic water-sports marketing.",["windsurf"],
   "Official sources establish beach services but not recurring windsurf use or a specialist launch.",
   "Do not infer windsurf suitability from generic motorised water sports.",
   "Insufficient discipline-specific evidence.",S["paliouri"],"reject_insufficient_evidence"),
 r("Lake Volvi",40.680,23.500,"Protected lake windsurf destination whose exact southern-shore launch remains open.",["windsurf"],
   "Rentina-strait winds create waves and draw windsurfers nationally.",
   "Pin a legal launch and confirm Ramsar/Natura permission, wildlife seasons and rescue.",
   "Rare inland wave/wind character and national draw support worth_trip after protected-area correction.",S["volvi"],"accept_after_correction"),
 r("Lake Vegoritida",40.725,21.754,"Large alpine lake with sailing/canoe use but no verified windsurf scene.",["windsurf","sailing"],
   "Official tourism supports sailing and general activity; available coarse wind means are light.",
   "A current windsurf operator, usable wind window, legal launch and rescue are unproven.",
   "Scenic and sailing value do not establish a windsurf trip destination.",S["vegoritida"],"reject_insufficient_evidence"),
]

payload = {
 "schema_version":1, "batch":"009",
 "research_mode":"independent_blind_before_local_comparison", "created_at":"2026-11-10",
 "independence_statement":"Saved before opening local spot, source, media or prior candidate records for these 25 names. Candidate selection used external discovery only.",
 "method_limits":[
  "Coordinates are approximate discovery points and do not prove a launch.",
  "Protected-area permission is unresolved unless explicitly sourced.",
  "Image candidates remain unapproved.",
  "Full draft/cloud duplication access remained unavailable.",
 ],
 "spots":spots,
}
assert len(spots) == 25 and all(len(item["sources"]) >= 2 for item in spots)
(ROOT / "batch-009-blind-research.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
