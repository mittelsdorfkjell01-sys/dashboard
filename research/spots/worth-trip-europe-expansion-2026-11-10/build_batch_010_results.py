"""Build post-freeze comparison results for batch 010."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-010-blind-research.json").read_text(encoding="utf-8"))
images = json.loads((ROOT / "batch-010-blind-image-candidates.json").read_text(encoding="utf-8"))

regions = {
    "Durankulak – Kartaliy South Beach": "Dobrich / Shabla",
    "Krapets": "Dobrich / Shabla",
    "Albena": "Dobrich / Balchik",
    "Asparuhovo, Varna": "Varna",
    "Kamchia coast": "Varna / Avren",
    "Obzor": "Burgas / Nessebar",
    "Sunny Beach / Nessebar": "Burgas / Nessebar",
    "Pomorie": "Burgas / Pomorie",
    "Sarafovo, Burgas": "Burgas",
    "Lake Atanasovsko": "Burgas",
    "Gradina, Chernomorets": "Burgas / Sozopol",
    "Harmanite, Sozopol": "Burgas / Sozopol",
    "Ahtopol": "Burgas / Tsarevo",
    "Silistar": "Burgas / Tsarevo",
    "Mamaia – H2O Beach / Lake Siutghiol": "Constanța / Mamaia",
    "Constanța – Zoom / WEGO sector": "Constanța",
    "Corbu beach": "Constanța / Corbu",
    "Vadu beach": "Constanța / Corbu",
    "Gura Portiței": "Tulcea / Jurilovca",
    "Sfântu Gheorghe, Danube Delta": "Tulcea / Danube Delta",
    "Eforie Nord": "Constanța / Eforie",
    "Limanu / Mangalia marina": "Constanța / Mangalia",
    "Kilyos – Burç Beach": "Istanbul / Sarıyer",
    "Gümüşdere Beach, Kilyos": "Istanbul / Sarıyer",
    "Silivri – Semizkum": "Istanbul / Silivri",
}

duplicates = {
    "Gümüşdere Beach, Kilyos": "Kilyos – Burç Beach (same wider Kilyos wind-sport coast; retain as an operational sector, not a second destination count)",
}

rows = []
for item, image in zip(blind["spots"], images["spots"], strict=True):
    name = item["name"]
    verdict = "reject_as_duplicate" if name in duplicates else item["blind_verdict"]
    image_count = sum(len(values) for values in image["providers"].values())
    rows.append({
        "name": name,
        "verdict": verdict,
        "blind_verdict": item["blind_verdict"],
        "local_duplicate": name in duplicates,
        "public_live_duplicate": False,
        "duplicate_of": duplicates.get(name),
        "region": regions[name],
        "region_status": "missing",
        "coordinate_status": "identity_or_launch_open" if item["blind_verdict"] in {"hold_for_more_research", "reject_insufficient_evidence"} else "approximate_requires_zone_map",
        "image_status": "unreviewed_candidates_not_approved" if image_count else "no_approved_candidate",
        "image_candidate_count": image_count,
        "priority": "P1" if verdict in {"accept_as_worth_trip", "accept_after_correction", "hold_for_more_research"} else "P2",
        "correction": ("Do not create a separate destination record; use " + duplicates[name] + ".") if name in duplicates else item["access_rules"],
    })

payload = {
    "batch": "010",
    "completed_at": "2026-11-10",
    "blind_sha256": "96EB74EC19894663494EAB7DA49D6ECA7549E1F805744C64CEB1BAD907FE50E3",
    "comparison_scope": "Public live catalogue (46 published spots), repository seed inventory, public regions and prior completed batches checked after blind freeze.",
    "local_duplicate_limit": "Local PostgreSQL remained unavailable; draft-only rows could not be checked.",
    "cloud_duplicate_limit": "No authorized full Cloud/Admin inventory was available.",
    "nearby_note": "No exact public-live or seed duplicate was found. Gümüşdere is consolidated as an operational sector of the same wider Kilyos destination rather than counted independently.",
    "within_batch_duplicate": "Gümüşdere Beach, Kilyos -> Kilyos – Burç Beach",
    "spots": rows,
}
assert len(rows) == 25
(ROOT / "batch-010-results.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
