"""Build post-freeze comparison results for batch 008."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-008-blind-research.json").read_text(encoding="utf-8"))
images = json.loads((ROOT / "batch-008-blind-image-candidates.json").read_text(encoding="utf-8"))

regions = {
 "Seča Cape, Portorož":"Slovenian Littoral / Portorož", "Izola – Petelin Cape":"Slovenian Littoral / Izola",
 "Koper – Žusterna":"Slovenian Littoral / Koper", "Strunjan":"Slovenian Littoral / Strunjan",
 "Lake Bohinj":"Upper Carniola / Bohinj", "Punat Bay, Krk":"Kvarner / Krk", "Baška, Krk":"Kvarner / Krk",
 "Nin – Ždrijac":"Dalmatien / Zadar", "Sabunike":"Dalmatien / Zadar", "Privlaka":"Dalmatien / Zadar",
 "Jadrija":"Dalmatien / Šibenik", "Zaton, Šibenik":"Dalmatien / Šibenik",
 "Omiš – Ribnjak / Lokva Rogoznica":"Dalmatien / Split", "Bačvice, Split":"Dalmatien / Split",
 "Kučište, Pelješac":"Dalmatien / Pelješac", "Neum":"Herzegovina / Neum",
 "Tivat Bay":"Bay of Kotor / Tivat", "Orahovac, Bay of Kotor":"Bay of Kotor / Kotor",
 "Lake Skadar – Vranjina":"Lake Skadar / Podgorica", "Vjosa–Narta / Pishë Poro":"Vlorë / Vjosa–Narta",
 "Golem Beach":"Durrës / Golem", "Lalzit Bay":"Durrës / Lalzit",
 "Lake Shkodra – Shiroka":"Shkodër / Lake Shkodra", "Struga, Lake Ohrid":"Lake Ohrid / Struga",
 "Lake Prespa – Stenje":"Lake Prespa / Resen",
}

rows = []
for item, image in zip(blind["spots"], images["spots"], strict=True):
    name = item["name"]
    verdict = item["blind_verdict"]
    duplicate_of = None
    if name == "Kučište, Pelješac":
        verdict = "reject_as_duplicate"
        duplicate_of = "Viganj (Charge 004; same linked Kučište–Viganj destination corridor)"
    image_count = sum(len(values) for values in image["providers"].values())
    rows.append({
        "name":name, "verdict":verdict, "blind_verdict":item["blind_verdict"],
        "local_duplicate":name == "Kučište, Pelješac", "public_live_duplicate":False,
        "duplicate_of":duplicate_of, "region":regions[name],
        "region_status":"available_broad_region" if item["country"] == "HR" and name not in {"Punat Bay, Krk", "Baška, Krk"} else "missing",
        "coordinate_status":"identity_or_launch_open" if item["blind_verdict"] in {"hold_for_more_research", "reject_insufficient_evidence"} else "approximate_requires_zone_map",
        "image_status":"unreviewed_candidates_not_approved" if image_count else "no_approved_candidate",
        "priority":"P1" if verdict in {"accept_as_worth_trip", "accept_after_correction", "hold_for_more_research"} else "P2",
        "correction":"Do not create a separate spot; retain as a Viganj subspot/service beach." if name == "Kučište, Pelješac" else item["access_rules"],
    })

payload = {
 "batch":"008", "completed_at":"2026-11-10",
 "blind_sha256":"1D81449605E374EDF013E41C115F732C820506441C1E4DBF3B7FE0803480D378",
 "comparison_scope":"Public live catalogue (46 published spots), repository seed inventory, public regions and prior completed batches checked after blind freeze.",
 "local_duplicate_limit":"Local PostgreSQL remained unavailable; draft-only rows could not be checked.",
 "cloud_duplicate_limit":"No authorized full Cloud/Admin inventory was available.",
 "nearby_note":"Nin–Ždrijac and Sabunike remain distinct provisional launches pending exact zone mapping. Kučište is not counted separately from the linked Viganj destination already reviewed in batch 004.",
 "within_batch_duplicate":None, "spots":rows,
}
assert len(rows) == 25
(ROOT / "batch-008-results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
