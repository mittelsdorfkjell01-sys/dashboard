"""Independent Commons/Openverse image discovery for blind batch 003."""

from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SPOTS = [
    ("Gott Bay, Tiree", "Gott Bay Tiree windsurf"),
    ("West Wittering", "West Wittering kitesurf windsurf"),
    ("Llangennith", "Llangennith surfing Wales"),
    ("Daymer Bay", "Daymer Bay kitesurf"),
    ("Brandon Bay", "Brandon Bay windsurf Ireland"),
    ("Keel / Trawmore, Achill", "Keel Beach Achill surf"),
    ("Inch Strand", "Inch Strand Kerry surf"),
    ("Strandhill", "Strandhill surfing Ireland"),
    ("Hoddevik", "Hoddevik surfing Norway"),
    ("Borestranda", "Borestranda kitesurf Norway"),
    ("Sola Beach", "Solastranden kitesurf"),
    ("Lomsesanden, Lista", "Lomsesanden kitesurf Lista"),
    ("Thorlakshofn", "Thorlakshofn surfing Iceland"),
    ("Sandvik, Reykjanes", "Sandvik Reykjanes surfing"),
    ("Toro Stenstrand", "Toro Stenstrand surfing Sweden"),
    ("Lomma Beach", "Lomma Beach kitesurf"),
    ("Yyteri", "Yyteri surfing Finland"),
    ("Tulliniemi Beach", "Tulliniemi Beach Hanko windsurf"),
    ("Ristna Beach", "Ristna Beach surfing Estonia"),
    ("Parnu Beach", "Parnu Beach kitesurf"),
    ("Pavilosta", "Pavilosta surfing Latvia"),
    ("Karosta Beach, Liepaja", "Karosta Beach Liepaja kitesurf"),
    ("Nida", "Nida Lithuania windsurf Curonian Lagoon"),
    ("Kintai", "Kintai kitesurf Lithuania"),
    ("Sventoji", "Sventoji Lithuania kitesurf"),
]


def discover(spot):
    name, query = spot
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
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(discover, SPOTS))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "independence_statement": "Created before local/database comparison for batch 003.",
        "limitations": ["Search relevance is not geographic proof.",
                        "Every candidate requires visual and source-page review.",
                        "Pexels and Unsplash API credentials were unavailable."],
        "spots": results,
    }
    (ROOT / "batch-003-blind-image-candidates.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
