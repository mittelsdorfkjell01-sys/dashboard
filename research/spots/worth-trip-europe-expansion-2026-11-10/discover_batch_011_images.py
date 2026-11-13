"""Independent Commons/Openverse image discovery for blind batch 011."""
from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SPOTS = [
    ("Odesa Chornomorka", "Odesa Chornomorka Ukraine kitesurf windsurf"),
    ("Odesa Arcadia", "Odesa Arcadia Ukraine windsurf kitesurf"),
    ("Chornomorsk Ukraine", "Chornomorsk Ukraine kitesurf windsurf"),
    ("Kobleve Ukraine", "Kobleve Ukraine kitesurf windsurf"),
    ("Kinburn Spit Ukraine", "Kinburn Spit Ukraine kitesurf"),
    ("Skadovsk Ukraine", "Skadovsk Ukraine windsurf kitesurf"),
    ("Arabat Spit Henichesk", "Arabat Spit Henichesk Ukraine kitesurf windsurf"),
    ("Kyrylivka Fedotova Spit", "Kyrylivka Fedotova Spit Ukraine windsurf kitesurf"),
    ("Berdyansk Ukraine", "Berdyansk Ukraine windsurf kitesurf"),
    ("Lake Svitiaz Ukraine", "Lake Svitiaz Ukraine windsurf kitesurf"),
    ("Kyiv Sea Vyshhorod", "Kyiv Sea Vyshhorod Ukraine windsurf kitesurf"),
    ("Zatoka Dniester Liman", "Zatoka Dniester Liman Ukraine kitesurf windsurf"),
    ("Ghidighici Reservoir Moldova", "Ghidighici Reservoir Moldova windsurf kitesurf"),
    ("Costesti Stanca Reservoir Moldova", "Costesti Stanca Reservoir Moldova windsurf"),
    ("Batumi Georgia", "Batumi Georgia kitesurf windsurf"),
    ("Gonio Georgia", "Gonio Georgia kitesurf windsurf"),
    ("Kvariati Georgia", "Kvariati Georgia windsurf kitesurf"),
    ("Kobuleti Georgia", "Kobuleti Georgia kitesurf windsurf"),
    ("Ureki Georgia", "Ureki Georgia kitesurf windsurf"),
    ("Maltakva Poti Georgia", "Maltakva Poti Georgia kitesurf windsurf"),
    ("Anaklia Georgia", "Anaklia Georgia kitesurf windsurf"),
    ("Tbilisi Sea Georgia", "Tbilisi Sea Georgia windsurf kitesurf"),
    ("Bazaleti Lake Georgia", "Bazaleti Lake Georgia windsurf"),
    ("Paravani Lake Georgia", "Paravani Lake Georgia windsurf kitesurf"),
    ("Lisi Lake Georgia", "Lisi Lake Georgia windsurf"),
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
    return {"spot": name, "query": query, "providers": providers, "errors": errors, "review_status": "unreviewed_candidates_not_approved"}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=10) as pool:
        rows = list(pool.map(discover, SPOTS))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "independence_statement": "Created before local/database comparison for batch 011.",
        "limitations": ["Search relevance is not geographic proof.", "Every candidate requires visual, geographic, resolution and licence review."],
        "spots": rows,
    }
    (ROOT / "batch-011-blind-image-candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
