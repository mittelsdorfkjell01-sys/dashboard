"""Build post-freeze comparison results for batch 006."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-006-blind-research.json").read_text(encoding="utf-8"))
images = json.loads((ROOT / "batch-006-blind-image-candidates.json").read_text(encoding="utf-8"))
image_names = {x["spot"] for x in images["spots"] if sum(len(v) for v in x["providers"].values())}

regions = {
"Moledo":"Minho / Caminha", "Cabedelo, Viana do Castelo":"Viana do Castelo", "Ofir":"Esposende / Cávado",
"Matosinhos Beach":"Porto / Matosinhos", "Espinho – Praia da Baía":"Espinho", "Praia da Barra, Aveiro":"Aveiro / Ílhavo",
"Cabedelo, Figueira da Foz":"Figueira da Foz", "Buarcos – Tamargueira":"Figueira da Foz / Buarcos",
"São Pedro de Moel":"Leiria coast", "Foz do Arelho":"Óbidos Lagoon / Caldas da Rainha",
"Santa Cruz, Torres Vedras":"Torres Vedras", "Praia da Areia Branca":"Lourinhã",
"Lagoa de Albufeira":"Sesimbra / Albufeira Lagoon", "Fonte da Telha":"Costa da Caparica / Almada",
"São João da Caparica":"Costa da Caparica / Almada", "Praia do Meco":"Sesimbra",
"Tróia":"Setúbal / Tróia peninsula", "São Torpes":"Sines / Alentejo coast", "Malhão / Milfontes":"Odemira / Costa Vicentina",
"Odeceixe":"Aljezur / Costa Vicentina", "Arrifana":"Aljezur / Costa Vicentina", "Praia do Amado":"Carrapateira / Costa Vicentina",
"Jardim do Mar":"Madeira / Calheta", "Paul do Mar":"Madeira / Calheta", "Santa Bárbara, São Miguel":"Azores / São Miguel"}

special = {
"Moledo":"Pin a legal launch and attach bathing, flag and protected-landscape rules.",
"Cabedelo, Viana do Castelo":"Map north/south discipline sections, dunes and current rescue coverage.",
"Ofir":"Use the southern surf section and retain rocks, river-mouth and protected-area warnings.",
"Matosinhos Beach":"Do not count as worth_trip; retain only as a local training option.",
"Espinho – Praia da Baía":"Pin the Casino wave/peak and add crowd, bank and concession-zone guidance.",
"Praia da Barra, Aveiro":"Keep harbour exclusions, flags and local current guidance explicit.",
"Cabedelo, Figueira da Foz":"Map port, school, swim and dune-access sectors.",
"Buarcos – Tamargueira":"Classify world_class and document exact entry, rock, section, tide and level limits.",
"São Pedro de Moel":"Retain rocky-margin, flag and supervised-water guidance.",
"Foz do Arelho":"Split lagoon wind launch from ocean surf and map inlet/navigation hazards.",
"Santa Cruz, Torres Vedras":"Select one peak and document rocks, current, level and supervised zones.",
"Praia da Areia Branca":"Retain as worth_trip with current school/flag and hazard guidance.",
"Lagoa de Albufeira":"Map legal lagoon launch, inlet current, seasonal opening, dunes and bathers.",
"Fonte da Telha":"Use the verified school/rescue section and attach crowd/cliff restrictions.",
"São João da Caparica":"Pin a current legal wind-sport corridor and separate groynes/bathing water.",
"Praia do Meco":"Separate licensed naturist and sport sections; add rough-sea/flag warnings.",
"Tróia":"Do not count until the exact side, legal launch, navigation and habitat constraints are sourced.",
"São Torpes":"Retain school/flag guidance and current water-quality advisories.",
"Malhão / Milfontes":"Use Malhão as the entry, separate the Mira estuary and map natural-park access.",
"Odeceixe":"Separate river bathing from ocean surf and retain bar/current warnings.",
"Arrifana":"Retain cliff access, crowd, supervision and level guidance.",
"Praia do Amado":"Retain natural-park, current, flag and school-sector rules.",
"Jardim do Mar":"Classify world_class and document reef entry/exit, swell and rescue limits.",
"Paul do Mar":"Pin an exact wave/launch and document reef, level, entry and rescue constraints.",
"Santa Bárbara, São Miguel":"Retain experienced-level, current, flag and seasonal supervision guidance."}

rows=[]
for item in blind["spots"]:
    name=item["name"]
    # Discovery labels omit accents and punctuation, so match on stable first words.
    has_image=any(name.split(",")[0].split(" – ")[0].replace("São", "Sao").replace("á", "a") in x for x in image_names)
    rows.append({"name":name,"verdict":item["blind_verdict"],"blind_verdict":item["blind_verdict"],
      "local_duplicate":False,"public_live_duplicate":False,"duplicate_of":None,
      "region":regions[name],"region_status":"missing","coordinate_status":"identity_or_launch_open" if item["blind_verdict"]=="hold_for_more_research" else "approximate_requires_zone_map",
      "image_status":"unreviewed_candidates_not_approved" if has_image else "no_approved_candidate",
      "priority":"P1" if item["blind_verdict"] not in {"reject_insufficient_trip_value"} else "P2","correction":special[name]})

payload={"batch":"006","completed_at":"2026-11-10","blind_sha256":"4D8E5800DAA56C4BDC66590FFB739C9EDDBFE93E15651E4EAB37D49A78AB2603",
 "comparison_scope":"Public live catalogue (46 published spots), repository seed inventory and public regions checked after blind freeze.",
 "local_duplicate_limit":"Local PostgreSQL remained unavailable; draft-only rows could not be checked.",
 "cloud_duplicate_limit":"No authorized full Cloud/Admin inventory was available.",
 "nearby_note":"Several candidates are near existing Peniche, Ericeira, Cascais or Nazaré regions but are geographically distinct destinations; no exact live/seed duplicate was found.",
 "within_batch_duplicate":None,"spots":rows}
assert len(rows)==25
(ROOT/"batch-006-results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
