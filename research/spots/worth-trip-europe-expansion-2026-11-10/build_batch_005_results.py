"""Build post-freeze comparison results for batch 005."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-005-blind-research.json").read_text(encoding="utf-8"))

regions = {
"Lancieux": ("Brittany / Côte d'Émeraude", "missing"), "Saint-Brevin – Les Rochelets": ("Loire-Atlantique", "missing"),
"La Baule – K13": ("Loire-Atlantique / La Baule", "missing"), "Les Sables-d'Olonne – Tanchet": ("Vendée", "missing"),
"Pontaillac": ("Charente-Maritime / Royan", "missing"), "Hourtin Lake": ("Gironde / Médoc", "missing"),
"Biscarrosse Plage": ("Landes / Hossegor", "available"), "Gruissan – Plage des Chalets": ("Languedoc", "available"),
"Almanarre": ("Var / Hyères", "missing"), "Leucate – La Franqui": ("Languedoc", "available"),
"Pantín": ("Galicia / A Coruña", "missing"), "Patos": ("Galicia / Vigo", "missing"),
"Somo": ("Kantabrien", "available"), "Salinas": ("Asturien", "available"),
"Trabucador": ("Ebro Delta / Tarragona", "missing"), "Castelldefels – La Pineda": ("Barcelona coast", "missing"),
"El Palmar": ("Cádiz / Costa de la Luz", "missing"), "Mar Menor – La Mota": ("Murcia / Mar Menor", "missing"),
"Cape Drepano": ("Achaea / Gulf of Patras", "missing"), "Raches Lighthouse": ("Phthiotis / Maliakos Gulf", "missing"),
"Vassiliki": ("Lefkada", "missing"), "Nea Kios": ("Argolis / Nafplio", "missing"),
"Ai Giannis, Lefkada": ("Lefkada", "missing"), "Prasonisi": ("Rhodos", "available"),
"Karpathos – Afiartis": ("Karpathos", "missing")}

correction = {
"Lancieux":"Pin a tide-specific launch and retain rock, tidal-range and offshore-drift warnings.",
"Saint-Brevin – Les Rochelets":"Use the official Rochelets summer sector and current school/bathing priorities.",
"La Baule – K13":"Attach the current ordinance, K13 corridor, tide/coefficient limits and experienced-rider requirement.",
"Les Sables-d'Olonne – Tanchet":"Use Tanchet as the named entry and add live rip/bathing-zone guidance.",
"Pontaillac":"Do not count as worth_trip; retain only as a local urban surf option if another workflow needs it.",
"Hourtin Lake":"Select one legal launch from the municipal map and exclude reserve/swimming water.",
"Biscarrosse Plage":"Keep the central beach identity and explicit rip, shorebreak, flag and level warnings.",
"Gruissan – Plage des Chalets":"Classify world_class; map the discipline-specific and event corridors.",
"Almanarre":"Classify world_class and use only official launch channels/current seasonal rules.",
"Leucate – La Franqui":"Do not create a second record; improve existing Leucate with the La Franqui/Coussoules zone split and world_class review.",
"Pantín":"Classify world_class and retain competition/strong-swell context.",
"Patos":"Separate beach and Pico de Patos reef identities and attach current level/access guidance.",
"Somo":"Do not create a second record; apply the verified occupancy, school and bathing-zone evidence to the existing spot.",
"Salinas":"Retain as worth_trip with current bank, swell, lifeguard and rip guidance.",
"Trabucador":"Map sea/bay sides, legal vehicle access and habitat/nesting restrictions.",
"Castelldefels – La Pineda":"Attach the current licence/bib, zone and seasonal-hour rules.",
"El Palmar":"Retain as worth_trip with current/shorebreak and bathing-zone warnings.",
"Mar Menor – La Mota":"Do not count until an authority confirms the exact wind-sport zone and conservation rules.",
"Cape Drepano":"Pin the lighthouse-side launch and document reef, level and rescue boundaries.",
"Raches Lighthouse":"Confirm the public launch, rescue coverage and seasonal operating rules.",
"Vassiliki":"Classify world_class and preserve morning/afternoon level and zone differences.",
"Nea Kios":"Obtain a municipal launch, rules, rescue and bathing separation before publication.",
"Ai Giannis, Lefkada":"Separate kite and windsurf sections and attach current training-centre/swimmer rules.",
"Prasonisi":"Do not create a second record; review the existing spot as world_class and update its two-sided zone/level details.",
"Karpathos – Afiartis":"Classify world_class; separate Afiartis bay sections and skill levels."}

duplicates = {"Leucate – La Franqui": "Leucate (languedoc-leucate)", "Somo": "Somo (cantabria-somo)", "Prasonisi": "Prasonisi (rhodes-prasonisi)"}
rows = []
for item in blind["spots"]:
    name = item["name"]
    duplicate = name in duplicates
    verdict = "reject_as_duplicate" if duplicate else item["blind_verdict"]
    rows.append({"name": name, "verdict": verdict, "blind_verdict": item["blind_verdict"],
                 "local_duplicate": duplicate, "public_live_duplicate": duplicate,
                 "duplicate_of": duplicates.get(name), "region": regions[name][0], "region_status": regions[name][1],
                 "coordinate_status": "existing_point_needs_review" if duplicate else ("identity_or_launch_open" if item["blind_verdict"] == "hold_for_more_research" else "approximate_requires_zone_map"),
                 "image_status": "existing_media_not_reused" if duplicate else "no_approved_candidate_provider_failure",
                 "priority": "P0" if duplicate else ("P1" if verdict not in {"reject_insufficient_trip_value"} else "P2"),
                 "correction": correction[name]})

payload = {"batch": "005", "completed_at": "2026-11-10",
 "blind_sha256": "9AB5F6A31158BD05E231097C931DD01FF87A7188C2D899B6E3F1A55D5D41B020",
 "comparison_scope": "Public live catalogue (46 published spots), repository seed inventory and public regions checked after blind freeze.",
 "local_duplicate_limit": "Local PostgreSQL remained unavailable; draft-only rows could not be checked.",
 "cloud_duplicate_limit": "No authorized full Cloud/Admin inventory was available.",
 "nearby_note": "Biscarrosse is in the existing Landes region but distinct from La Gravière; other nearby candidates represent separate launches or disciplines.",
 "within_batch_duplicate": None, "spots": rows}
assert len(rows) == 25
(ROOT / "batch-005-results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
