"""Render comparison, image QA and progress reports from frozen batch data."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def compact(value: object) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={item}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def esc(value: object) -> str:
    return compact(value).replace("|", "\\|").replace("\n", " ")


def trip_evaluation(verdict: str) -> str:
    return {
        "accept_as_worth_trip": "confirmed",
        "accept_after_correction": "confirmed_with_caveat",
        "hold_for_more_research": "open",
        "reject_as_duplicate": "duplicate_risk",
        "reject_as_world_class": "contradicted",
        "reject_insufficient_trip_value": "unsupported",
        "reject_insufficient_evidence": "unsupported",
    }[verdict]


def coordinate_evaluation(status: str) -> str:
    risky = ("open", "estimated", "multiple", "conflict", "bay_not", "landmark_not", "requires")
    return "coordinate_risk" if any(token in status for token in risky) else "confirmed_with_caveat"


def render_comparison(blind: dict, results: dict) -> None:
    by_name = {row["name"]: row for row in results["spots"]}
    lines = [
        "# Charge 002: feldweiser Vergleich",
        "",
        "Stand: 2026-11-10. Die Bestandsseite wurde erst nach dem Einfrieren der Blindrecherche geöffnet. `Kein lokaler Datensatz` bedeutet nicht, dass kein Cloud-Entwurf existiert.",
        "",
    ]
    for spot in blind["spots"]:
        result = by_name[spot["name"]]
        verdict = result["verdict"]
        local = (
            f"Vorhandener Entwurf `{result['duplicate_of']}`"
            if result.get("local_duplicate")
            else "Kein lokaler Datensatz"
        )
        sources = "; ".join(source["publisher"] for source in spot["sources"][:3])
        sport_eval = "unsupported" if verdict == "reject_insufficient_evidence" else "confirmed_with_caveat"
        if verdict in {"accept_as_worth_trip", "reject_as_world_class", "reject_insufficient_trip_value"}:
            sport_eval = "confirmed"
        if result.get("local_duplicate"):
            sport_eval = "duplicate_risk"
        image_eval = "image_mismatch" if result["image_status"] == "existing_placeholder_p0" else "open"
        region_eval = "confirmed" if result["region_status"] == "available" else "open"
        lines.extend(
            [
                f"## {spot['name']}",
                "",
                "| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |",
                "|---|---|---|---|---|---|",
                f"| Identität | {esc(spot['identity'])} | {esc(local)} | {'duplicate_risk' if result.get('local_duplicate') else 'confirmed_with_caveat'} | {esc(sources)} | {esc(result['correction'])} |",
                f"| Einstieg | {esc(spot['entry'])} | {esc(local)} | {coordinate_evaluation(result['coordinate_status'])} | Blindrecherche und Nominatim | {esc(result['correction'])} |",
                f"| Sportarten | {esc(spot['sports'])} | {esc(local)} | {sport_eval} | {esc(sources)} | Nur feldweise belegte Sportarten übernehmen |",
                f"| Bedingungen | {esc(spot['conditions'])} | {esc(local)} | {'open' if verdict.startswith('hold_') else 'confirmed_with_caveat'} | {esc(sources)} | Unsicherheit, Saison und Niveau konditional erhalten |",
                f"| Zugang / Regeln | {esc(spot['access_rules'])} | {esc(local)} | {'open' if verdict in {'hold_for_more_research', 'reject_insufficient_evidence'} else 'confirmed_with_caveat'} | {esc(sources)} | Aktuelle Primärregel am konkreten Einstieg speichern |",
                f"| Region | {esc(result['region'])} | {esc(result['region_status'])} | {region_eval} | Lokale Regionsprüfung | Fehlende Region vor Spotanlage redaktionell prüfen |",
                f"| Bild | Unabhängig gesucht; kein Treffer automatisch freigegeben | {esc(result['image_status'])} | {image_eval} | Commons / Openverse | Siehe `batch-002-image-review.md` |",
                f"| Reisewert | {esc(spot['trip_value'])} | Keine lokale Einstufung{' am vorhandenen Entwurf' if result.get('local_duplicate') else ''} | {trip_evaluation(verdict)} | {esc(sources)} | {esc(result['correction'])} |",
                "",
                f"Abschlussurteil: `{verdict}`",
                "",
            ]
        )
    (ROOT / "batch-002-comparison.md").write_text("\n".join(lines), encoding="utf-8")


def render_images(images: dict, results: dict) -> None:
    result_by_image_name = {
        "Podersdorf Nordstrand": "Podersdorf Nordstrand",
        "Lake Silvaplana": "Lake Silvaplana",
        "Ahrenshoop": "Ahrenshoop",
        "Amrum Norddorf": "Amrum Norddorf",
        "Bork Havn": "Bork Havn",
        "Agger": "Agger",
        "Bredene": "Bredene – Twins Club",
        "Hindeloopen": "Hindeloopen",
        "Cadzand-Bad": "Cadzand-Bad – kite zone",
        "Razo": "Razo",
        "Pals": "Platja del Grau, Pals",
        "Baie de Pont-Mahé": "Baie de Pont-Mahé",
        "Algajola": "Algajola / Aregno Plage",
        "Beauduc": "Beauduc – Plage de la Comtesse",
        "Keros": "Keros Beach, Lemnos",
        "Sigri": "Sigri",
        "Neretva Estuary": "Neretva Estuary kite beach",
        "Bol / Zlatni Rat": "Bol / Zlatni Rat",
        "Badesi / Li Junchi": "Badesi – Li Junchi",
        "Talamone": "Talamone – Fertilia Bay",
        "Mellieha Bay": "Mellieħa Bay / Għadira Bay",
        "Rewa": "Rewa",
        "Esposende": "Esposende – Cávado estuary",
        "Figueira da Foz / Cabedelo": "Praia do Cabedelo, Figueira da Foz",
        "Lagoa de Óbidos": "Lagoa de Óbidos",
    }
    by_name = {row["name"]: row for row in results["spots"]}
    lines = [
        "# Charge 002: unabhängige Bildprüfung",
        "",
        "Stand: 2026-11-10. Suchtreffer sind keine Bildfreigaben. Nicht-kommerzielle Lizenzen, geringe Auflösung, fehlender Ortsbezug und Nachbarstrandmotive werden ausgeschlossen.",
        "",
        "| Spot | Treffer | Ergebnis | Priorität / nächster Schritt |",
        "|---|---:|---|---|",
    ]
    for row in images["spots"]:
        result = by_name[result_by_image_name[row["spot"]]]
        items = row["providers"].get("wikimedia_commons", []) + row["providers"].get("openverse", [])
        viable = [
            item
            for item in items
            if item.get("license") not in {"by-nc", "by-nc-sa", "by-nc-nd", "by-nd"}
            and (item.get("width") or 0) >= 1600
        ]
        next_step = {
            "existing_placeholder_p0": "P0: vorhandenen Keros-Platzhalter vor jeder Veröffentlichung entfernen; erst dann exakten Ersatz prüfen.",
            "exact_commons_candidates": "P1: zwei exakte Commons-Dateien visuell und anhand ihrer Geokoordinaten prüfen; nur eine erreicht Hero-Breite.",
            "gallery_candidate_only": "P1: Podersdorf-Datei örtlich prüfen; 2048 px reicht nur für Galerie.",
        }.get(result["image_status"], "P1/P2: bildlos lassen und nach geklärter Einstiegslage erneut suchen.")
        error_note = f"; Providerfehler: {', '.join(row['errors'])}" if row["errors"] else ""
        lines.append(
            f"| {result_by_image_name[row['spot']]} | {len(items)} ({len(viable)} technisch/lizenzseitig vorprüfbar) | `{result['image_status']}`{error_note} | {next_step} |"
        )
    lines.extend(
        [
            "",
            "## Ergebnis",
            "",
            "- Kein Bild wurde Produktdaten zugeordnet oder freigegeben.",
            "- Belastbare exakte Kandidaten bestehen derzeit nur für Bol/Zlatni Rat; Podersdorf und Silvaplana haben mögliche Galerieansätze.",
            "- Openverse-Treffer mit `NC` oder `ND` sowie Treffer unter 1600 px sind für die geplante kommerzielle, bearbeitbare Nutzung ungeeignet.",
            "- Zwölf Commons-Abfragen waren während der Discovery temporär rate-limitiert; diese Spots bleiben ausdrücklich offen.",
            "",
        ]
    )
    (ROOT / "batch-002-image-review.md").write_text("\n".join(lines), encoding="utf-8")


def render_progress(register: dict, results: dict) -> None:
    verdicts = Counter(row["verdict"] for row in results["spots"])
    batch_accepted = verdicts["accept_as_worth_trip"] + verdicts["accept_after_correction"]
    batch_excluded = sum(
        verdicts[key]
        for key in (
            "reject_as_duplicate",
            "reject_as_world_class",
            "reject_insufficient_trip_value",
            "reject_insufficient_evidence",
        )
    )
    cumulative_checked = 25 + len(results["spots"])
    cumulative_accepted = 16 + batch_accepted
    cumulative_direct = 4 + verdicts["accept_as_worth_trip"]
    lines = [
        "# Europaweite `worth_trip`-Recherche: Fortschritt",
        "",
        "Stand: 2026-11-10. Pilotcharge 001 und Erweiterungscharge 002 sind abgeschlossen. Es wurden keine Produktdaten geschrieben.",
        "",
        "## Register und Abdeckung",
        "",
        f"- Rohkandidaten im aktuellen Discovery-Register: {register['statistics']['unique_raw_candidates']}",
        f"- neue Rohkandidaten ohne direkte Namensüberschneidung mit Pilotcharge 001: {register['statistics']['new_raw_candidates_excluding_pilot_name_overlap']}",
        "- Länder im aktuellen Register: 14",
        "- aktive Lücken: UK, Irland, Island, Norwegen, Schweden, Finnland, Baltikum, weite Teile Südosteuropas und Schwarzes Meer",
        "",
        "## Charge 002",
        "",
        f"- vollständig geprüft: {len(results['spots'])}",
        f"- direkt `accept_as_worth_trip`: {verdicts['accept_as_worth_trip']}",
        f"- `accept_after_correction`: {verdicts['accept_after_correction']}",
        f"- blockiert / Hold: {verdicts['hold_for_more_research']}",
        f"- ausgeschlossen oder anders einzustufen: {batch_excluded}",
        f"- lokale Duplikate: {verdicts['reject_as_duplicate']}",
        "",
        "## Kumuliert",
        "",
        f"- vollständig geprüft: {cumulative_checked}",
        f"- direkt akzeptiert: {cumulative_direct}",
        f"- potenziell akzeptabel einschließlich dokumentierter Korrekturfälle: {cumulative_accepted}",
        f"- noch bis 400 vollständig geprüften Kandidaten: {400 - cumulative_checked}",
        f"- noch bis 400 potenziell akzeptablen `worth_trip`-Spots: {400 - cumulative_accepted}",
        f"- noch bis 400 ohne Korrektur direkt akzeptierten Spots: {400 - cumulative_direct}",
        "",
        "## Nächste Charge",
        "",
        "Charge 003 soll zuerst die Registerlücken in Großbritannien, Irland, Island/Norwegen, Schweden/Finnland und dem Baltikum ergänzen und daraus höchstens 25 Kandidaten prüfen. Die hohe Konzentration des aktuellen Registers auf Deutschland, Frankreich und Italien darf die Auswahl nicht dominieren.",
        "",
    ]
    (ROOT / "progress.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    blind = load("batch-002-blind-research.json")
    results = load("batch-002-results.json")
    images = load("batch-002-blind-image-candidates.json")
    register = load("raw-candidates.json")
    render_comparison(blind, results)
    render_images(images, results)
    render_progress(register, results)


if __name__ == "__main__":
    main()
