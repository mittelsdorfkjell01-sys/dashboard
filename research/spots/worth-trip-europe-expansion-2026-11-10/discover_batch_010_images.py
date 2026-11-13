"""Independent Commons/Openverse image discovery for blind batch 010."""
from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SPOTS = [
 ("Durankulak Shabla","Durankulak Shabla Bulgaria kitesurf"),
 ("Krapets Bulgaria","Krapets Bulgaria kitesurf"),
 ("Albena Balchik","Albena Balchik windsurf"),
 ("Varna Asparuhovo","Varna Asparuhovo kitesurf"),
 ("Kamchia Bulgaria","Kamchia Bulgaria kitesurf windsurf"),
 ("Obzor Bulgaria","Obzor Bulgaria windsurf kitesurf"),
 ("Sunny Beach Nessebar","Sunny Beach Nessebar windsurf kitesurf"),
 ("Pomorie Bulgaria","Pomorie Bulgaria windsurf kitesurf"),
 ("Sarafovo Burgas","Sarafovo Burgas kitesurf"),
 ("Lake Atanasovsko Burgas","Lake Atanasovsko Burgas windsurf kitesurf"),
 ("Gradina Chernomorets","Gradina Chernomorets kitesurf"),
 ("Harmanite Sozopol","Harmanite Sozopol windsurf"),
 ("Ahtopol Bulgaria","Ahtopol Bulgaria windsurf"),
 ("Silistar Bulgaria","Silistar Bulgaria kitesurf"),
 ("Mamaia Romania","Mamaia Romania kitesurf windsurf"),
 ("Constanta Modern Beach","Constanta Modern Beach kitesurf"),
 ("Corbu Romania","Corbu Romania kitesurf"),
 ("Vadu Romania","Vadu Romania kitesurf"),
 ("Gura Portitei Razim","Gura Portitei Romania kitesurf"),
 ("Sfantu Gheorghe Danube Delta","Sfantu Gheorghe Romania kitesurf"),
 ("Eforie Nord Romania","Eforie Nord windsurf kitesurf"),
 ("Limanu Mangalia","Limanu Mangalia Romania windsurf"),
 ("Kilyos Istanbul","Kilyos Istanbul kitesurf windsurf"),
 ("Gumusdere Istanbul","Gumusdere Istanbul kitesurf"),
 ("Silivri Istanbul","Silivri Istanbul windsurf kitesurf"),
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
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "independence_statement":"Created before local/database comparison for batch 010.",
        "limitations":["Search relevance is not geographic proof.","Every candidate requires visual, geographic, resolution and licence review."],
        "spots":rows,
    }
    (ROOT / "batch-010-blind-image-candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
