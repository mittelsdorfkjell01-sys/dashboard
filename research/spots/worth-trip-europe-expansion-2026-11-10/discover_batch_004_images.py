"""Independent Commons/Openverse image discovery for blind batch 004."""

from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SPOTS = [
    ("Apelviken", "Apelviken Varberg surfing"),
    ("Toppilansaari", "Toppilansaari Oulu kitesurf"),
    ("Hiekkasarkat", "Hiekkasarkat Kalajoki kitesurf"),
    ("Svencele", "Svencele Lithuania kitesurf"),
    ("Juodkrante", "Juodkrante Lithuania kitesurf"),
    ("Saulkrasti Koklite", "Saulkrasti Koklite kitesurf"),
    ("Ventspils South Beach", "Ventspils beach kitesurf"),
    ("Leba", "Leba Poland kitesurf"),
    ("Jastarnia", "Jastarnia kitesurf"),
    ("Dabki Lake Bukowo", "Dabki Lake Bukowo windsurf"),
    ("Viganj", "Viganj windsurf"),
    ("Premantura", "Premantura windsurf"),
    ("Velika Plaza", "Velika Plaza Ulcinj kitesurf"),
    ("Ada Bojana", "Ada Bojana kitesurf"),
    ("Velipoja", "Velipoja Albania kitesurf"),
    ("Krapets", "Krapets Bulgaria kitesurf"),
    ("Asparuhovo Beach", "Asparuhovo Beach windsurf"),
    ("Pomorie", "Pomorie Bulgaria kitesurf"),
    ("Mamaia Siutghiol", "Mamaia Siutghiol windsurf"),
    ("Corbu Beach", "Corbu Beach Romania kitesurf"),
    ("Vadu Beach", "Vadu Beach Romania kitesurf"),
    ("Alacati", "Alacati windsurf"),
    ("Akyaka", "Akyaka kitesurf"),
    ("Gokceada Aydincik", "Gokceada Aydincik windsurf"),
    ("Gradina Beach", "Gradina Beach Bulgaria kitesurf"),
]


def discover(row):
    name, query = row
    providers, errors = {}, []
    for provider, search in (("wikimedia_commons", commons), ("openverse", openverse)):
        try:
            providers[provider] = search(query)
        except Exception as exc:
            providers[provider] = []
            errors.append(f"{provider}: {type(exc).__name__}")
    return {"spot": name, "query": query, "providers": providers, "errors": errors,
            "review_status": "unreviewed_candidates_not_approved"}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(discover, SPOTS))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "independence_statement": "Created before local/database comparison for batch 004.",
        "limitations": ["Search relevance is not geographic proof.",
                        "Every candidate requires visual and source-page review.",
                        "Pexels and Unsplash API credentials were unavailable."],
        "spots": results,
    }
    (ROOT / "batch-004-blind-image-candidates.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
