"""Build post-freeze comparison results for batch 004."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-004-blind-research.json").read_text(encoding="utf-8"))

regions = {
"Apelviken":"Halland / Varberg", "Toppilansaari kitesurf beach":"Oulu / Bothnian Bay",
"Hiekkasärkät, Kalajoki":"Northern Ostrobothnia", "Svencelė":"Curonian Lagoon / Klaipėda",
"Juodkrantė Beach":"Curonian Spit", "Saulkrasti – Koklīte":"Vidzeme / Gulf of Riga",
"Ventspils South Beach":"Kurzeme", "Łeba / Sarbsko Lake":"Pomerania / Łeba",
"Jastarnia – Puck Bay":"Hel Peninsula / Puck Bay", "Dąbki – Lake Bukowo":"West Pomerania",
"Viganj – Ponta Liberan":"Pelješac / Dalmatia", "Premantura":"Istria",
"Velika Plaža, Ulcinj":"Ulcinj coast", "Ada Bojana":"Ulcinj / Bojana Delta",
"Velipoja":"Shkodër / Buna Delta", "Krapets Beach":"Northern Bulgarian Black Sea",
"Asparuhovo Beach":"Varna", "Pomorie Lake / coast":"Burgas / Pomorie",
"Mamaia – Lake Siutghiol":"Constanța / Mamaia", "Corbu Beach":"Romanian Black Sea / Danube Delta",
"Vadu Beach":"Romanian Black Sea / Danube Delta", "Alaçatı":"Çeşme / İzmir",
"Akyaka kite beach":"Gökova Bay / Muğla", "Gökçeada – Aydıncık / Kefalos":"Gökçeada / Çanakkale",
"Gradina Beach":"Sozopol / Burgas"}

correction = {
"Apelviken":"Confirm current summer swim zoning and preserve separation from bathers.",
"Toppilansaari kitesurf beach":"Pin the northern Toppilansaari launch; do not label Nallikari as the open-water kite entry.",
"Hiekkasärkät, Kalajoki":"Use the Surf Center entry and retain sudden-depth, current and no-lifeguard warnings.",
"Svencelė":"Attach depth, launch geometry and current adjacent-reserve rules.",
"Juodkrantė Beach":"Resolve lagoon versus sea side and obtain the exact legal national-park launch.",
"Saulkrasti – Koklīte":"Pin the Koklīte section outside Centre bathing and protected nature-park areas.",
"Ventspils South Beach":"Do not count until a current municipal corridor, conditions and hazards are documented.",
"Łeba / Sarbsko Lake":"Create only a specific Sarbsko school launch, separate from open Baltic and port waters.",
"Jastarnia – Puck Bay":"Map the bay-side entry around pier, harbours, schools and bathing areas; retain foil-depth risk.",
"Dąbki – Lake Bukowo":"Use the municipal centre or verified southeast-shore base; separate lake from Baltic beach.",
"Viganj – Ponta Liberan":"Classify world_class and keep Ponta Liberan launch/rescue constraints explicit.",
"Premantura":"Do not count without an authoritative exact launch, permission and conditions source.",
"Velika Plaža, Ulcinj":"Classify world_class; represent individual school sections only as subspots if independently justified.",
"Ada Bojana":"Do not count separately from the Ulcinj/Velika Plaža destination without an independent launch identity.",
"Velipoja":"Do not count until wind-sport use, zone, rules and trip value are independently established.",
"Krapets Beach":"Map conservation and legal access zones; retain unguarded/current warnings.",
"Asparuhovo Beach":"Treat as a local/worth-checking-out urban beach, not a dedicated-trip destination.",
"Pomorie Lake / coast":"Resolve the official ban and permitted coast/lake polygons before any classification.",
"Mamaia – Lake Siutghiol":"Attach the current ANR-approved lake sector and keep it separate from Black Sea swim zones.",
"Corbu Beach":"Obtain written non-motor wind-sport permission and a legal reserve launch before counting.",
"Vadu Beach":"Do not count; activity authorization, rescue and habitat protection are insufficient.",
"Alaçatı":"Classify world_class and use annually designated sport courses.",
"Akyaka kite beach":"Classify world_class; pin paid operator entries and separate the wild lagoon.",
"Gökçeada – Aydıncık / Kefalos":"Split flat and wave sections, levels and habitat/operator rules.",
"Gradina Beach":"Do not count until a current exact corridor, conditions, hazards and trip case are proven."}

image_exact = {"Apelviken", "Viganj – Ponta Liberan", "Premantura", "Alaçatı", "Akyaka kite beach"}
rows=[]
for item in blind["spots"]:
    name=item["name"]
    rows.append({"name":name,"verdict":item["blind_verdict"],"local_duplicate":False,
                 "public_live_duplicate":False,"region":regions[name],"region_status":"missing",
                 "coordinate_status":"identity_or_launch_open" if item["blind_verdict"] in {"hold_for_more_research","reject_insufficient_evidence","reject_as_duplicate"} else "approximate_requires_zone_map",
                 "image_status":"exact_candidates_open" if name in image_exact else "no_approved_candidate",
                 "priority":"P1" if item["blind_verdict"] not in {"reject_insufficient_evidence","reject_insufficient_trip_value"} else "P2",
                 "correction":correction[name]})

payload={"batch":"004","completed_at":"2026-11-10",
 "blind_sha256":"54A99A4E837825482600F070663D3ACBDB6F7F3F3517D83D9B6ADE0D3BDDCED8",
 "comparison_scope":"Public live catalogue (46 published spots), repository seed inventory and public regions checked after blind freeze.",
 "local_duplicate_limit":"Local PostgreSQL remained unavailable; draft-only rows could not be checked.",
 "cloud_duplicate_limit":"No authorized full Cloud/Admin inventory was available.",
 "nearby_note":"Viganj is 29.1 km from published Neretva Delta and is a distinct Pelješac Channel venue.",
 "within_batch_duplicate":"Ada Bojana was not counted separately because the available sources describe it as part of the same Ulcinj/Velika Plaža kite destination.",
 "spots":rows}
assert len(rows)==25
(ROOT/"batch-004-results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
