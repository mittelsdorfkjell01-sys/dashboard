"""Build post-freeze comparison results for batch 009."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-009-blind-research.json").read_text(encoding="utf-8"))
images = json.loads((ROOT / "batch-009-blind-image-candidates.json").read_text(encoding="utf-8"))

regions = {
 "Chalikounas, Corfu":("Corfu / Lake Korission","missing"),
 "Devil's Bay / Paradise Beach, Karpathos":("Karpathos / Afiartis","missing"),
 "Fanes, Rhodes":("Rhodos","available"), "Kefalos Bay, Kos":("Kos","available"),
 "Nissakia / Agios Nikolaos, Artemida":("Attica / Artemida","missing"),
 "Marmari, Kos":("Kos","available"), "Marmari – Megali Ammos, Evia":("South Evia / Marmari","missing"),
 "Mikri Vigla, Naxos":("Naxos","available"), "Ftelia, Mykonos":("Mykonos","missing"),
 "Golden Beach, Paros":("Paros","available"), "New Golden Beach / Tserdakia, Paros":("Paros","available"),
 "Tsoukalia, Paros":("Paros","available"), "Pounta, Paros":("Paros","available"),
 "Ixia Bay, Rhodes":("Rhodos","available"), "Kokkari, Samos":("Samos","missing"),
 "Agios Georgios, Naxos":("Naxos","available"), "Theologos, Rhodes":("Rhodos","available"),
 "Plaka, Naxos":("Naxos","available"), "Laguna, Naxos":("Naxos","available"),
 "Schinias, Marathon":("Attica / Marathon","missing"), "Anavyssos, Attica":("Attica / Saronikos","missing"),
 "Nea Iraklitsa – Alana":("Kavala / Pangaio","missing"), "Paliouri / Chrouso, Halkidiki":("Halkidiki / Kassandra","missing"),
 "Lake Volvi":("Central Macedonia / Volvi","missing"), "Lake Vegoritida":("West Macedonia / Amyntaio","missing"),
}
duplicates = {
 "Devil's Bay / Paradise Beach, Karpathos":"Karpathos – Afiartis (Charge 005; same Afiartis windsurf complex)",
 "Mikri Vigla, Naxos":"Mikri Vigla (public live catalogue: naxos-mikri-vigla)",
 "Pounta, Paros":"Pounda (public live catalogue: paros-pounda)",
 "Laguna, Naxos":"Agios Georgios, Naxos (same adjoining operational lagoon/Flisvos area in this batch)",
}

rows = []
for item, image in zip(blind["spots"], images["spots"], strict=True):
    name = item["name"]
    verdict = "reject_as_duplicate" if name in duplicates else item["blind_verdict"]
    image_count = sum(len(values) for values in image["providers"].values())
    public_duplicate = name in {"Mikri Vigla, Naxos", "Pounta, Paros"}
    rows.append({
        "name":name, "verdict":verdict, "blind_verdict":item["blind_verdict"],
        "local_duplicate":name in duplicates and not public_duplicate,
        "public_live_duplicate":public_duplicate, "duplicate_of":duplicates.get(name),
        "region":regions[name][0], "region_status":regions[name][1],
        "coordinate_status":"identity_or_launch_open" if item["blind_verdict"] in {"hold_for_more_research","reject_insufficient_evidence"} else "approximate_requires_zone_map",
        "image_status":"unreviewed_candidates_not_approved" if image_count else "no_approved_candidate",
        "priority":"P1" if verdict in {"accept_as_worth_trip","accept_after_correction","hold_for_more_research"} else "P2",
        "correction":"Do not create a separate record; use {}.".format(duplicates[name]) if name in duplicates else item["access_rules"],
    })

payload = {
 "batch":"009", "completed_at":"2026-11-10",
 "blind_sha256":"393E2542E01D3CFB6E90706338E86D7745CD811F6A807F56B3DF6BEAAF1AD20F",
 "comparison_scope":"Public live catalogue (46 published spots), repository seed inventory, public regions and prior completed batches checked after blind freeze.",
 "local_duplicate_limit":"Local PostgreSQL remained unavailable; draft-only rows could not be checked.",
 "cloud_duplicate_limit":"No authorized full Cloud/Admin inventory was available.",
 "nearby_note":"Public Mikri Vigla and Pounda are exact duplicates. Devil's Bay is part of the previously reviewed Afiartis complex. Laguna is consolidated with adjoining Agios Georgios.",
 "within_batch_duplicate":"Laguna, Naxos -> Agios Georgios, Naxos",
 "spots":rows,
}
assert len(rows) == 25
(ROOT / "batch-009-results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
