"""Independent Commons/Openverse image discovery for blind batch 009."""
from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SPOTS = [
 ("Chalikounas Corfu","Chalikounas Corfu kitesurf"),
 ("Devils Paradise Beach Karpathos","Devils Paradise Beach Karpathos windsurf"),
 ("Fanes Rhodes","Fanes Rhodes kitesurf"),
 ("Kefalos Kos","Kefalos Kos windsurf"),
 ("Loutsa Nissakia","Loutsa Nissakia Greece windsurf"),
 ("Marmari Kos","Marmari Kos windsurf"),
 ("Marmari Megali Ammos Evia","Marmari Megali Ammos Evia kitesurf"),
 ("Mikri Vigla Naxos","Mikri Vigla Naxos kitesurf"),
 ("Ftelia Mykonos","Ftelia Mykonos windsurf"),
 ("Golden Beach Paros","Golden Beach Paros windsurf"),
 ("New Golden Beach Paros","New Golden Beach Paros windsurf"),
 ("Tsoukalia Paros","Tsoukalia Paros windsurf"),
 ("Pounta Paros","Pounta Paros kitesurf"),
 ("Ixia Rhodes","Ixia Rhodes windsurf"),
 ("Kokkari Samos","Kokkari Samos windsurf"),
 ("St George Beach Naxos","St George Beach Naxos windsurf"),
 ("Theologos Rhodes","Theologos Rhodes windsurf kitesurf"),
 ("Plaka Naxos","Plaka Naxos windsurf"),
 ("Laguna Naxos","Laguna Naxos windsurf"),
 ("Schinias Marathon","Schinias Marathon windsurf"),
 ("Anavyssos Attica","Anavyssos Greece windsurf"),
 ("Nea Iraklitsa Kavala","Nea Iraklitsa Kavala windsurf"),
 ("Paliouri Chrousso Halkidiki","Paliouri Chrousso Halkidiki windsurf"),
 ("Lake Volvi","Lake Volvi Greece windsurf"),
 ("Lake Vegoritida","Lake Vegoritida windsurf"),
]

def discover(row):
    name, query = row
    providers, errors = {}, []
    for provider_name, fn in (("wikimedia_commons", commons), ("openverse", openverse)):
        try:
            providers[provider_name] = fn(query)
        except Exception as exc:
            providers[provider_name] = []
            errors.append("{}: {}".format(provider_name, type(exc).__name__))
    return {"spot":name, "query":query, "providers":providers, "errors":errors, "review_status":"unreviewed_candidates_not_approved"}

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=10) as pool:
        rows = list(pool.map(discover, SPOTS))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "independence_statement": "Created before local/database comparison for batch 009.",
        "limitations": ["Search relevance is not geographic proof.", "Every candidate requires visual, geographic, resolution and licence review."],
        "spots": rows,
    }
    (ROOT / "batch-009-blind-image-candidates.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
