"""Build the Europe worth-trip discovery register from public catalogues.

Catalogue presence is discovery evidence only. It must never be treated as a
confirmed sport, condition, rule, coordinate, image, or worth_trip verdict.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CHECKED_AT = "2026-11-10"
USER_AGENT = "Surfwinddata independent Europe spot research/1.0"

SPOTARA_URL = "https://spotara.de/spots"
WIND_SOCIETY_URL = "https://sociedaddelviento.com/en/spots/"
WIKIDATA_URL = "https://query.wikidata.org/sparql"

PILOT_NAMES = {
    "domburg noordduine",
    "vrouwenpolder",
    "agios georgios lagoon naxos",
    "theologos rhodes",
    "chia su giudeu",
    "perranporth",
    "neeltje jans",
    "gwithian towans",
    "sennen cove",
    "rossnowlagh",
    "salinas asturias",
    "valdearenas liencres",
    "bakio beach",
    "xago",
    "vega berbes",
    "los locos",
    "plentzia",
    "karraspio",
    "praia da arrifana",
    "saunton sands",
    "carrowniskey strand",
    "chalupy puck bay",
    "agios ioannis myloi",
    "apelviken",
    "marmari fun2fun",
}

COUNTRY_NAMES = {
    "AT": "Austria",
    "BE": "Belgium",
    "CH": "Switzerland",
    "DE": "Germany",
    "DK": "Denmark",
    "ES": "Spain",
    "FR": "France",
    "GR": "Greece",
    "HR": "Croatia",
    "IT": "Italy",
    "MT": "Malta",
    "NL": "Netherlands",
    "PL": "Poland",
    "PT": "Portugal",
    "GB": "United Kingdom",
    "IE": "Ireland",
    "IS": "Iceland",
    "NO": "Norway",
    "SE": "Sweden",
    "FI": "Finland",
}

WIND_SOCIETY_COUNTRY = {
    "es": "ES",
    "pt": "PT",
    "fr": "FR",
    "it": "IT",
}

WIKIDATA_COUNTRY = {
    "Austria": "AT",
    "Belgium": "BE",
    "Croatia": "HR",
    "Denmark": "DK",
    "Finland": "FI",
    "France": "FR",
    "Germany": "DE",
    "Greece": "GR",
    "Iceland": "IS",
    "Ireland": "IE",
    "Italy": "IT",
    "Malta": "MT",
    "Netherlands": "NL",
    "Norway": "NO",
    "Poland": "PL",
    "Portugal": "PT",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "United Kingdom": "GB",
}


def fetch(url: str, *, accept: str = "text/html") -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def environment_hint(name: str) -> str:
    key = normalize(name)
    if any(token in key for token in ("fjord", "fjorden")):
        return "fjord"
    if any(token in key for token in ("lagoon", "laguna", "lagune", "stagnone")):
        return "lagoon"
    if any(token in key for token in ("estuary", "estuari", "mundung", "foce", "desembocadura")):
        return "river_estuary"
    if any(token in key for token in ("insel", "island", "ile ", "isola ", "noirmoutier")):
        return "island"
    if any(token in key for token in (" lake", "lake ", "lac ", "lago ", "see ", "alfsee", "meer")):
        return "lake_or_inland_water"
    return "coast_or_unknown"


def extract_balanced_array(page: str, marker: str) -> str:
    marker_index = page.find(marker)
    if marker_index < 0:
        raise RuntimeError(f"catalogue marker not found: {marker}")
    start = marker_index + len(marker) - 1
    depth = 0
    for index in range(start, len(page)):
        if page[index] == "[":
            depth += 1
        elif page[index] == "]":
            depth -= 1
            if depth == 0:
                return page[start : index + 1]
    raise RuntimeError("unterminated catalogue array")


def spotara_candidates() -> list[dict]:
    page = fetch(SPOTARA_URL)
    escaped = extract_balanced_array(page, r'{\"spots\":[')
    payload = escaped.replace(r'\"', '"')
    rows = json.loads(payload)
    candidates = []
    for row in rows:
        code = row.get("countryCode")
        if code not in COUNTRY_NAMES:
            continue
        candidates.append(
            {
                "name": row["title"].strip(),
                "country_code": code,
                "country": COUNTRY_NAMES[code],
                "locality_hint": row.get("city"),
                "environment_hint": environment_hint(row["title"]),
                "discovery_sports": row.get("sportTypes", []),
                "discovery_wind_directions": row.get("windDirection", []),
                "coordinates": None,
                "catalogue_sources": [
                    {
                        "catalogue": "Spotara",
                        "url": urllib.parse.urljoin(SPOTARA_URL, row["detailHref"]),
                        "checked_at": CHECKED_AT,
                    }
                ],
            }
        )
    return candidates


def wind_society_candidates() -> list[dict]:
    page = fetch(WIND_SOCIETY_URL)
    link_pattern = re.compile(
        r'<a\s+href="\.\./spots/([^"/]+)/">(.*?)</a>', re.IGNORECASE | re.DOTALL
    )
    candidates = []
    for slug, raw_name in link_pattern.findall(page):
        suffix = slug.rsplit("-", 1)[-1].lower()
        code = WIND_SOCIETY_COUNTRY.get(suffix)
        if not code:
            continue
        name = html.unescape(re.sub(r"<[^>]+>", "", raw_name)).strip()
        candidates.append(
            {
                "name": name,
                "country_code": code,
                "country": COUNTRY_NAMES[code],
                "locality_hint": None,
                "environment_hint": environment_hint(name),
                "discovery_sports": ["windsport_unspecified"],
                "discovery_wind_directions": [],
                "coordinates": None,
                "catalogue_sources": [
                    {
                        "catalogue": "Wind Society",
                        "url": urllib.parse.urljoin(WIND_SOCIETY_URL, f"../spots/{slug}/"),
                        "checked_at": CHECKED_AT,
                    }
                ],
            }
        )
    return candidates


def wikidata_candidates() -> list[dict]:
    query = """
SELECT ?item ?itemLabel ?coord ?countryLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2368508.
  OPTIONAL { ?item wdt:P625 ?coord. }
  OPTIONAL { ?item wdt:P17 ?country. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
""".strip()
    url = WIKIDATA_URL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    payload = json.loads(fetch(url, accept="application/sparql-results+json"))
    candidates = []
    for binding in payload["results"]["bindings"]:
        country_name = binding.get("countryLabel", {}).get("value")
        code = WIKIDATA_COUNTRY.get(country_name)
        name = binding.get("itemLabel", {}).get("value", "")
        if not code or not name or name.startswith("Q"):
            continue
        coord = binding.get("coord", {}).get("value")
        parsed_coord = None
        match = re.fullmatch(r"Point\(([-0-9.]+) ([-0-9.]+)\)", coord or "")
        if match:
            parsed_coord = {
                "lon": float(match.group(1)),
                "lat": float(match.group(2)),
                "status": "catalogue_only_unverified",
            }
        candidates.append(
            {
                "name": name,
                "country_code": code,
                "country": COUNTRY_NAMES[code],
                "locality_hint": None,
                "environment_hint": environment_hint(name),
                "discovery_sports": ["surf"],
                "discovery_wind_directions": [],
                "coordinates": parsed_coord,
                "catalogue_sources": [
                    {
                        "catalogue": "Wikidata surf spot query",
                        "url": binding["item"]["value"],
                        "checked_at": CHECKED_AT,
                    }
                ],
            }
        )
    return candidates


def merge_candidates(rows: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["country_code"], normalize(row["name"]))
        if key not in merged:
            merged[key] = row
            continue
        current = merged[key]
        current["catalogue_sources"].extend(row["catalogue_sources"])
        current["discovery_sports"] = sorted(
            set(current["discovery_sports"]) | set(row["discovery_sports"])
        )
        current["discovery_wind_directions"] = sorted(
            set(current["discovery_wind_directions"])
            | set(row["discovery_wind_directions"])
        )
        if not current["coordinates"] and row["coordinates"]:
            current["coordinates"] = row["coordinates"]
        if not current["locality_hint"] and row["locality_hint"]:
            current["locality_hint"] = row["locality_hint"]

    result = []
    for index, row in enumerate(
        sorted(merged.values(), key=lambda item: (item["country_code"], normalize(item["name"]))),
        start=1,
    ):
        row["candidate_id"] = f"raw-{index:04d}"
        row["research_status"] = "raw_unreviewed"
        row["catalogue_is_not_confirmation"] = True
        row["pilot_overlap"] = normalize(row["name"]) in PILOT_NAMES
        result.append(row)
    return result


def main() -> None:
    try:
        wikidata_rows = wikidata_candidates()
        wikidata_note = None
    except (HTTPError, URLError, TimeoutError) as exc:
        wikidata_rows = []
        wikidata_note = f"Wikidata query unavailable during generation: {type(exc).__name__}"

    source_rows = {
        "spotara": spotara_candidates(),
        "wind_society": wind_society_candidates(),
        "wikidata": wikidata_rows,
    }
    candidates = merge_candidates([row for rows in source_rows.values() for row in rows])
    country_counts = Counter(row["country_code"] for row in candidates)
    environment_counts = Counter(row["environment_hint"] for row in candidates)
    pilot_overlap = sum(1 for row in candidates if row["pilot_overlap"])

    register = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checked_at": CHECKED_AT,
        "purpose": "Discovery register only; every candidate requires independent verification.",
        "source_counts_before_merge": {key: len(value) for key, value in source_rows.items()},
        "statistics": {
            "unique_raw_candidates": len(candidates),
            "new_raw_candidates_excluding_pilot_name_overlap": len(candidates) - pilot_overlap,
            "pilot_name_overlaps": pilot_overlap,
            "countries": dict(sorted(country_counts.items())),
            "environment_hints": dict(sorted(environment_counts.items())),
        },
        "limitations": [
            "Catalogue inclusion proves neither current access nor worth_trip quality.",
            "Country and environment coverage is uneven and requires targeted gap searches.",
            "Names may still collapse neighbouring launches or contain duplicates with different spelling.",
            "Coordinates, sports, winds, rules, levels, facilities and images remain unverified.",
            *([wikidata_note] if wikidata_note else []),
        ],
        "candidates": candidates,
    }
    output = ROOT / "raw-candidates.json"
    output.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    coverage = [
        "# Europaweite Kandidatenabdeckung",
        "",
        f"Stand: {CHECKED_AT}. Rohkandidaten sind keine bestätigten Spots.",
        "",
        "## Discovery-Quellen",
        "",
        f"- Spotara: {len(source_rows['spotara'])} Einträge",
        f"- Wind Society: {len(source_rows['wind_society'])} Einträge",
        f"- Wikidata-Surfspotabfrage: {len(source_rows['wikidata'])} europäische Einträge",
        f"- nach Normalisierung: {len(candidates)} eindeutige Rohkandidaten",
        f"- davon ohne Namensüberschneidung mit Pilotcharge 001: {len(candidates) - pilot_overlap}",
        "",
        "## Länderabdeckung",
        "",
        "| Land | Rohkandidaten |",
        "|---|---:|",
    ]
    for code, count in sorted(country_counts.items()):
        coverage.append(f"| {COUNTRY_NAMES[code]} (`{code}`) | {count} |")
    coverage.extend(
        [
            "",
            "## Gewässer-Hinweise",
            "",
            "Die Typen sind lediglich aus Namen abgeleitete Discovery-Hinweise.",
            "",
            "| Hinweis | Anzahl |",
            "|---|---:|",
        ]
    )
    for kind, count in sorted(environment_counts.items()):
        coverage.append(f"| `{kind}` | {count} |")
    coverage.extend(
        [
            "",
            "## Aktive Abdeckungslücken",
            "",
            "- Großbritannien, Irland, Island und Norwegen fehlen in der aktuellen Registerausgabe, weil die punktuelle Wikidata-Ergänzung nicht verfügbar war.",
            "- Schweden und Finnland fehlen ebenfalls in den drei Discovery-Quellen.",
            "- Ostsee-Baltikum, Südosteuropa, Schwarzes Meer und Atlantikinseln benötigen eigene Suchwellen.",
            "- Surf-only-Reviere sind gegenüber Wind-/Kite-/Wing-Katalogen unterrepräsentiert.",
            "- Fjorde und geeignete Flussmündungen müssen gezielt ergänzt werden.",
            *([f"- Technischer Hinweis: {wikidata_note}." ] if wikidata_note else []),
            "",
            "Keine Länderquote rechtfertigt die Aufnahme schwacher Spots. Die Lücken steuern nur die weitere Suche.",
            "",
        ]
    )
    (ROOT / "coverage-ledger.md").write_text("\n".join(coverage), encoding="utf-8")


if __name__ == "__main__":
    main()
