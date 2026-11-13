"""Render batch 003 comparison, image QA, and cumulative progress."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def esc(value):
    if isinstance(value, dict):
        value = ", ".join(f"{k}={v}" for k, v in value.items())
    elif isinstance(value, list):
        value = ", ".join(map(str, value))
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_comparison(blind, results):
    by_name = {x["name"]: x for x in results["spots"]}
    lines = [
        "# Charge 003: feldweiser Vergleich", "",
        "Stand: 2026-11-10. Die Blindrecherche und Bildsuche wurden vor dem Bestandsabgleich eingefroren. Geprüft wurden 46 veröffentlichte Live-Spots und der Repository-Seed; Entwurfsdaten blieben wegen nicht laufender lokaler Datenbank und fehlendem Cloud/Admin-Zugriff offen.", "",
    ]
    for s in blind["spots"]:
        r = by_name[s["name"]]
        pubs = "; ".join(x["publisher"] for x in s["sources"][:3])
        lines += [
            f"## {s['name']}", "",
            "| Feld | Unabhängiges Ergebnis | Bestandsabgleich | Bewertung / Korrektur | Quellen |",
            "|---|---|---|---|---|",
            f"| Identität | {esc(s['identity'])} | Kein veröffentlichter Live- oder Seed-Datensatz | {'offen' if 'open' in r['coordinate_status'] else 'plausibel'}; {esc(r['correction'])} | {esc(pubs)} |",
            f"| Einstieg | {esc(s['entry'])} | `{r['coordinate_status']}` | Koordinate bleibt Discovery-Punkt, bis die Startzone belegt ist | Blindrecherche |",
            f"| Sport / Bedingungen | {esc(s['sports'])}; {esc(s['conditions'])} | Keine lokalen Werte | Nur belegte Disziplinen und konditionale Hinweise übernehmen | {esc(pubs)} |",
            f"| Zugang / Regeln | {esc(s['access_rules'])} | Keine lokalen Werte | Primärregel am konkreten Einstieg erforderlich | {esc(pubs)} |",
            f"| Region | {esc(r['region'])} | `{r['region_status']}` | Fehlende Region vor einer Anlage redaktionell prüfen | Live-Regionsabgleich |",
            f"| Bild | Separat gesucht, nichts freigegeben | `{r['image_status']}` | Bildlos lassen, bis Ort, Motiv, Lizenz und Auflösung visuell bestätigt sind | Commons / Openverse |",
            f"| Reisewert | {esc(s['trip_value'])} | Keine lokale Einstufung | Abschluss: `{r['verdict']}` | {esc(pubs)} |", "",
        ]
    (ROOT / "batch-003-comparison.md").write_text("\n".join(lines), encoding="utf-8")


def render_images(images, results):
    by_name = {x["name"]: x for x in results["spots"]}
    lines = ["# Charge 003: unabhängige Bildprüfung", "",
             "Suchtreffer sind keine Freigaben. Ortsbezug, sichtbare Sportnutzung, Lizenz, Urheberangabe und ausreichende Auflösung müssen einzeln geprüft werden.", "",
             "| Spot | Treffer | Status | Nächster Schritt |", "|---|---:|---|---|"]
    for row in images["spots"]:
        items = row["providers"].get("wikimedia_commons", []) + row["providers"].get("openverse", [])
        viable = [x for x in items if x.get("license") not in {"by-nc", "by-nc-sa", "by-nc-nd", "by-nd"} and (x.get("width") or 0) >= 1600]
        err = f"; Fehler: {', '.join(row['errors'])}" if row["errors"] else ""
        lines.append(f"| {row['spot']} | {len(items)} ({len(viable)} technisch/lizenzseitig vorprüfbar) | `{by_name[row['spot']]['image_status']}`{err} | {'Kandidaten visuell und geografisch prüfen' if items else 'Nach geklärter Startzone erneut suchen'} |")
    lines += ["", "## Ergebnis", "", "- Kein Bild wurde freigegeben oder Produktdaten zugeordnet.", "- Exakte Suchansätze bestehen für Llangennith, Brandon Bay, Inch Strand, Strandhill, Hoddevik und Sola; auch diese bleiben ungeprüfte Kandidaten.", "- Mehrere Commons-/Openverse-Abfragen waren rate-limitiert; ein Nulltreffer ist daher kein Beleg, dass kein geeignetes Bild existiert.", ""]
    (ROOT / "batch-003-image-review.md").write_text("\n".join(lines), encoding="utf-8")


def render_progress(register, results):
    v = Counter(x["verdict"] for x in results["spots"])
    accepted = v["accept_as_worth_trip"] + v["accept_after_correction"]
    excluded = v["reject_as_world_class"] + v["reject_insufficient_evidence"] + v["reject_as_duplicate"]
    lines = [
        "# Europaweite `worth_trip`-Recherche: Fortschritt", "",
        "Stand: 2026-11-10. Pilotcharge 001 sowie Erweiterungscharge 002 und 003 sind abgeschlossen. Es wurden keine Produktdaten geschrieben.", "",
        "## Register und Abdeckung", "",
        f"- Rohkandidaten im Discovery-Register: {register['statistics']['unique_raw_candidates']}",
        "- Charge 003 ergänzt erstmals systematisch UK, Irland, Norwegen, Island, Schweden, Finnland, Estland, Lettland und Litauen.",
        "- Weiter offen: Färöer, weite Teile Schwedens/Finnlands/Baltikums, Balkan, Schwarzes Meer und zusätzliche Insel-/Binnenreviere.", "",
        "## Charge 003", "",
        f"- vollständig geprüft: {len(results['spots'])}",
        f"- direkt `accept_as_worth_trip`: {v['accept_as_worth_trip']}",
        f"- `accept_after_correction`: {v['accept_after_correction']}",
        f"- blockiert / Hold: {v['hold_for_more_research']}",
        f"- ausgeschlossen oder anders einzustufen: {excluded}",
        f"- bestätigte lokale/Live-Duplikate: {v['reject_as_duplicate']}", "",
        "## Kumuliert", "",
        "- vollständig geprüft: 75",
        f"- direkt akzeptiert: {10 + v['accept_as_worth_trip']}",
        f"- potenziell akzeptabel einschließlich dokumentierter Korrekturfälle: {32 + accepted}",
        "- noch bis 400 vollständig geprüften Kandidaten: 325",
        f"- noch bis 400 potenziell akzeptablen `worth_trip`-Spots: {400 - (32 + accepted)}",
        f"- noch bis 400 ohne Korrektur direkt akzeptierten Spots: {400 - (10 + v['accept_as_worth_trip'])}", "",
        "## Einschränkung des Duplikatchecks", "",
        "- Der öffentliche Live-Katalog mit 46 veröffentlichten Spots und der Repository-Seed wurden geprüft.",
        "- Die lokale PostgreSQL-Instanz war nicht erreichbar; Entwürfe konnten deshalb in Charge 003 nicht erneut abgeglichen werden.",
        "- Vor einer späteren Anlage ist für alle akzeptierten Kandidaten zwingend der vollständige Draft-/Cloud-Abgleich nachzuholen.", "",
        "## Nächste Charge", "",
        "Charge 004 sollte die verbleibenden nordischen/baltischen Lücken und anschließend Balkan/Schwarzes Meer bearbeiten, erneut mit höchstens 25 vollständig geprüften Kandidaten.", "",
    ]
    (ROOT / "progress.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    blind = load("batch-003-blind-research.json")
    results = load("batch-003-results.json")
    images = load("batch-003-blind-image-candidates.json")
    register = load("raw-candidates.json")
    render_comparison(blind, results)
    render_images(images, results)
    render_progress(register, results)
