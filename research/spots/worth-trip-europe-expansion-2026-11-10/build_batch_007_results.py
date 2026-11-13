"""Build post-freeze comparison results for batch 007."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
blind=json.loads((ROOT/"batch-007-blind-research.json").read_text(encoding="utf-8"))
images=json.loads((ROOT/"batch-007-blind-image-candidates.json").read_text(encoding="utf-8"))
regions={
"Torbole":"Lake Garda / Trentino","Malcesine":"Lake Garda / Veneto","Campione del Garda":"Lake Garda / Lombardy",
"Dervio":"Lake Como / Lecco","Colico":"Lake Como / Lecco","Gera Lario – Acquaforte":"Lake Como / Como","Valmadrera – Baia di Parè":"Lake Como / Lecco","Cannobio Lido":"Lake Maggiore / Piedmont",
"Grado Pineta – Punta Barbacale":"Friuli Venezia Giulia / Grado","Marina Julia":"Friuli Venezia Giulia / Monfalcone","Sottomarina":"Veneto / Chioggia","Porto Corsini":"Emilia-Romagna / Ravenna",
"Senigallia":"Marche / Ancona","Porto Recanati – Scossicci":"Marche / Macerata","Vieste – Scialmarino":"Puglia / Gargano","Torre Guaceto coast":"Puglia / Brindisi",
"Porto Cesareo – Bacino Grande":"Puglia / Salento","Gallipoli – Baia Verde / Lido Pizzo":"Puglia / Salento","Talamone – Fertilia":"Tuscany / Maremma","Castiglione della Pescaia":"Tuscany / Maremma",
"Santa Marinella":"Lazio / Rome coast","Lido di Ostia":"Lazio / Rome coast","Mondello":"Sizilien / Palermo","Puzziteddu":"Sizilien / Trapani","Pozzallo – Secondo Scivolo":"Sizilien / Ragusa"}

rows=[]
for item,img in zip(blind["spots"],images["spots"],strict=True):
 verdict=item["blind_verdict"]
 correction=item["access_rules"]
 if verdict=="reject_as_world_class": correction="Classify world_class; "+correction
 elif verdict=="reject_insufficient_trip_value": correction="Do not count as worth_trip; "+correction
 elif verdict=="reject_insufficient_evidence": correction="Do not count until permission and identity are proven; "+correction
 elif verdict=="hold_for_more_research": correction="Keep blocked pending current authority evidence; "+correction
 items=sum(len(v) for v in img["providers"].values())
 rows.append({"name":item["name"],"verdict":verdict,"blind_verdict":verdict,"local_duplicate":False,"public_live_duplicate":False,"duplicate_of":None,
  "region":regions[item["name"]],"region_status":"available" if item["country"]=="IT" and item["name"] in {"Mondello","Puzziteddu","Pozzallo – Secondo Scivolo"} else "missing",
  "coordinate_status":"identity_or_launch_open" if verdict in {"hold_for_more_research","reject_insufficient_evidence"} else "approximate_requires_zone_map",
  "image_status":"unreviewed_candidates_not_approved" if items else "no_approved_candidate","priority":"P1" if verdict not in {"reject_insufficient_trip_value"} else "P2","correction":correction})

payload={"batch":"007","completed_at":"2026-11-10","blind_sha256":"6C98777F54E9B38BA27AF50AED112F0D966E6BA963F7245C5D00416D1A226200",
 "comparison_scope":"Public live catalogue (46 published spots), repository seed inventory and public regions checked after blind freeze.",
 "local_duplicate_limit":"Local PostgreSQL remained unavailable; draft-only rows could not be checked.","cloud_duplicate_limit":"No authorized full Cloud/Admin inventory was available.",
 "nearby_note":"The Sicily candidates are distinct from published Lo Stagnone; the mainland/lake candidates have no exact public or seed match.","within_batch_duplicate":None,"spots":rows}
assert len(rows)==25
(ROOT/"batch-007-results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
