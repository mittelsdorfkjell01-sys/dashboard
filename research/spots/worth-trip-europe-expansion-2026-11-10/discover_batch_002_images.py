"""Independent Commons/Openverse image discovery for blind batch 002.

Results are candidates only. No image is approved without visual, geographic,
resolution and licence review.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
USER_AGENT = "Surfwinddata independent image research/1.0"

SPOTS = [
    ("Podersdorf Nordstrand", "Podersdorf am See kitesurf windsurf"),
    ("Lake Silvaplana", "Silvaplana lake kitesurf windsurf"),
    ("Ahrenshoop", "Ahrenshoop beach surf"),
    ("Amrum Norddorf", "Norddorf Amrum beach kitesurf"),
    ("Bork Havn", "Bork Havn surf"),
    ("Agger", "Agger Denmark surf"),
    ("Bredene", "Bredene beach surf"),
    ("Hindeloopen", "Hindeloopen kitesurf"),
    ("Cadzand-Bad", "Cadzand beach kitesurf"),
    ("Razo", "Praia de Razo surf"),
    ("Pals", "Platja de Pals windsurf"),
    ("Baie de Pont-Mahé", "Pont-Mahé kitesurf"),
    ("Algajola", "Algajola Aregno beach surf"),
    ("Beauduc", "Beauduc kitesurf"),
    ("Keros", "Keros Beach Lemnos kitesurf"),
    ("Sigri", "Sigri Lesvos windsurf"),
    ("Neretva Estuary", "Neretva estuary kitesurf Croatia"),
    ("Bol / Zlatni Rat", "Zlatni Rat windsurf"),
    ("Badesi / Li Junchi", "Li Junchi Badesi kitesurf"),
    ("Talamone", "Talamone kitesurf windsurf"),
    ("Mellieha Bay", "Mellieha Bay windsurf"),
    ("Rewa", "Rewa Poland kitesurf"),
    ("Esposende", "Esposende kitesurf"),
    ("Figueira da Foz / Cabedelo", "Praia Cabedelo Figueira surf"),
    ("Lagoa de Óbidos", "Obidos Lagoon kitesurf"),
]


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def commons(query: str) -> list[dict]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": "6",
        "gsrlimit": "5",
        "prop": "imageinfo|coordinates",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": "640",
        "origin": "*",
    }
    data = get_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params))
    rows = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        coords = (page.get("coordinates") or [None])[0]
        rows.append(
            {
                "title": page.get("title"),
                "source_page": info.get("descriptionurl"),
                "thumbnail_url": info.get("thumburl"),
                "width": info.get("width"),
                "height": info.get("height"),
                "license": (meta.get("LicenseShortName") or {}).get("value"),
                "artist": (meta.get("Artist") or {}).get("value"),
                "description": (meta.get("ImageDescription") or {}).get("value"),
                "coordinates": (
                    {"lat": coords.get("lat"), "lon": coords.get("lon")} if coords else None
                ),
            }
        )
    return rows


def openverse(query: str) -> list[dict]:
    params = {"q": query, "page_size": "5", "mature": "false"}
    data = get_json("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params))
    return [
        {
            "title": row.get("title"),
            "source_page": row.get("foreign_landing_url"),
            "thumbnail_url": row.get("thumbnail"),
            "width": row.get("width"),
            "height": row.get("height"),
            "license": row.get("license"),
            "license_version": row.get("license_version"),
            "creator": row.get("creator"),
            "provider": row.get("provider"),
            "source": row.get("source"),
        }
        for row in data.get("results", [])
    ]


def main() -> None:
    def discover(spot: tuple[str, str]) -> dict:
        name, query = spot
        providers = {}
        errors = []
        for provider, search in (("wikimedia_commons", commons), ("openverse", openverse)):
            try:
                providers[provider] = search(query)
            except Exception as exc:  # discovery must preserve per-provider failure
                providers[provider] = []
                errors.append(f"{provider}: {type(exc).__name__}")
        return {
            "spot": name,
            "query": query,
            "providers": providers,
            "errors": errors,
            "review_status": "unreviewed_candidates_not_approved",
        }

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(discover, SPOTS))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "independence_statement": "Created before local/database comparison for batch 002.",
        "limitations": [
            "Search relevance is not geographic proof.",
            "Every candidate requires visual and source-page review.",
            "Pexels and Unsplash API credentials were unavailable.",
        ],
        "spots": results,
    }
    (ROOT / "batch-002-blind-image-candidates.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
