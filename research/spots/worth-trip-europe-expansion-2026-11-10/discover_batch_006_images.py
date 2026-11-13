"""Independent Commons/Openverse image discovery for blind batch 006."""
from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SPOTS = [
    ("Moledo", "Praia de Moledo Portugal surf"),
    ("Cabedelo Viana", "Cabedelo Viana do Castelo kitesurf"),
    ("Ofir", "Praia de Ofir surf"),
    ("Matosinhos", "Matosinhos surf Portugal"),
    ("Espinho Praia da Baia", "Espinho Praia da Baia surf"),
    ("Praia da Barra Aveiro", "Praia da Barra Aveiro surf"),
    ("Cabedelo Figueira da Foz", "Cabedelo Figueira da Foz surf"),
    ("Buarcos", "Buarcos surf Portugal"),
    ("Sao Pedro de Moel", "Sao Pedro de Moel surf"),
    ("Foz do Arelho", "Foz do Arelho windsurf surf"),
    ("Santa Cruz Torres Vedras", "Santa Cruz Torres Vedras surf"),
    ("Areia Branca", "Praia da Areia Branca surf"),
    ("Lagoa de Albufeira", "Lagoa de Albufeira kitesurf"),
    ("Fonte da Telha", "Fonte da Telha kitesurf surf"),
    ("Sao Joao da Caparica", "Sao Joao da Caparica surf kitesurf"),
    ("Praia do Meco", "Praia do Meco surf"),
    ("Troia", "Troia Portugal kitesurf windsurf"),
    ("Sao Torpes", "Sao Torpes surf"),
    ("Milfontes Malhao", "Vila Nova Milfontes Malhao surf"),
    ("Odeceixe", "Odeceixe surf"),
    ("Arrifana", "Arrifana surf"),
    ("Praia do Amado", "Praia do Amado surf"),
    ("Jardim do Mar", "Jardim do Mar Madeira surf"),
    ("Paul do Mar", "Paul do Mar Madeira surf"),
    ("Santa Barbara Sao Miguel", "Santa Barbara Sao Miguel Azores surf"),
]


def discover(row):
    name, query = row; providers = {}; errors = []
    for provider, fn in (("wikimedia_commons", commons), ("openverse", openverse)):
        try: providers[provider] = fn(query)
        except Exception as exc: providers[provider] = []; errors.append(f"{provider}: {type(exc).__name__}")
    return {"spot": name, "query": query, "providers": providers, "errors": errors,
            "review_status": "unreviewed_candidates_not_approved"}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=10) as pool: rows = list(pool.map(discover, SPOTS))
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "independence_statement": "Created before local/database comparison for batch 006.",
               "limitations": ["Search relevance is not geographic proof.", "Every candidate requires visual, geographic, resolution and licence review."],
               "spots": rows}
    (ROOT / "batch-006-blind-image-candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
