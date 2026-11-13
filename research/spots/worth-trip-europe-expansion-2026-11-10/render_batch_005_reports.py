"""Render batch 005 comparison, image review and cumulative progress."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
load = lambda n: json.loads((ROOT / n).read_text(encoding="utf-8"))


def esc(v):
    if isinstance(v, dict): v = ", ".join(f"{k}={x}" for k, x in v.items())
    if isinstance(v, list): v = ", ".join(map(str, v))
    return str(v).replace("|", "\\|").replace("\n", " ")


def comparison(blind, results):
    by = {x["name"]: x for x in results["spots"]}
    lines = ["# Charge 005: feldweiser Vergleich", "",
      "Stand: 2026-11-10. Blindrecherche und Bildsuche wurden vor dem Bestandsabgleich eingefroren. Der öffentliche Live-Katalog (46 Spots), Repository-Seed und öffentliche Regionen wurden geprüft; Draft-/Cloud-Daten blieben technisch unzugänglich.", ""]
    for x in blind["spots"]:
        y = by[x["name"]]; pubs = "; ".join(z["publisher"] for z in x["sources"][:3])
        existing = f"Bestandsdublette: {y['duplicate_of']}" if y["public_live_duplicate"] else "Kein veröffentlichter Live- oder Seed-Datensatz"
        lines += [f"## {x['name']}", "", "| Feld | Unabhängiges Ergebnis | Bestandsabgleich | Bewertung / Korrektur | Quellen |", "|---|---|---|---|---|",
          f"| Identität | {esc(x['identity'])} | {esc(existing)} | {esc(y['correction'])} | {esc(pubs)} |",
          f"| Einstieg | {esc(x['entry'])} | `{y['coordinate_status']}` | Discovery-Punkt, keine neue freigegebene Startzone | Blindrecherche |",
          f"| Sport / Bedingungen | {esc(x['sports'])}; {esc(x['conditions'])} | Keine zusätzlichen lokalen Werte | Nur quellenbelegte, konditionale Werte übernehmen | {esc(pubs)} |",
          f"| Zugang / Regeln | {esc(x['access_rules'])} | Keine zusätzlichen lokalen Werte | Schutz-, Bade- und Betreiberzonen haben Vorrang | {esc(pubs)} |",
          f"| Region | {esc(y['region'])} | `{y['region_status']}` | Region vor einer Anlage redaktionell prüfen | Live-Regionsabgleich |",
          f"| Bild | Separat gesucht, Providerfehler, nichts freigegeben | `{y['image_status']}` | Bildlos lassen bis Ort, Motiv, Lizenz und Auflösung bestätigt sind | Commons / Openverse |",
          f"| Reisewert | {esc(x['trip_value'])} | Blind: `{y['blind_verdict']}` | Abschluss: `{y['verdict']}` | {esc(pubs)} |", ""]
    (ROOT / "batch-005-comparison.md").write_text("\n".join(lines), encoding="utf-8")


def images_report(images, results):
    lines = ["# Charge 005: unabhängige Bildprüfung", "", "Beide Suchprovider schlugen in dieser Charge fehl; kein Nulltreffer wird als Beleg fehlender Bilder interpretiert.", "",
             "| Spot | Treffer | Status | Nächster Schritt |", "|---|---:|---|---|"]
    for img, res in zip(images["spots"], results["spots"], strict=True):
        items = img["providers"].get("wikimedia_commons", []) + img["providers"].get("openverse", [])
        errors = ", ".join(img["errors"]) or "keine"
        lines.append(f"| {res['name']} | {len(items)} | `{res['image_status']}`; Fehler: {errors} | Nach geklärter Startzone mit funktionsfähigen Providern erneut suchen |")
    lines += ["", "## Ergebnis", "", "- Kein Bild wurde freigegeben oder Produktdaten zugeordnet.", "- Die Providerfehler sind für alle 25 Kandidaten im Rohartefakt erhalten.", ""]
    (ROOT / "batch-005-image-review.md").write_text("\n".join(lines), encoding="utf-8")


def progress(register, results):
    v = Counter(x["verdict"] for x in results["spots"])
    accepted = v["accept_as_worth_trip"] + v["accept_after_correction"]
    excluded = sum(v[k] for k in ("reject_as_duplicate", "reject_as_world_class", "reject_insufficient_trip_value", "reject_insufficient_evidence"))
    lines = ["# Europaweite `worth_trip`-Recherche: Fortschritt", "",
      "Stand: 2026-11-10. Pilotcharge 001 und Erweiterungscharge 002–005 sind abgeschlossen. Es wurden keine Produktdaten geschrieben.", "",
      "## Register und Abdeckung", "", f"- Rohkandidaten im Discovery-Register: {register['statistics']['unique_raw_candidates']}",
      "- Charge 005 ergänzt Frankreichs Atlantik- und Mittelmeer-Nebenreviere, Nord-/Ost-/Südspanien sowie westliches und insulares Griechenland.",
      "- Weiter offen: Portugal-Nebenreviere und Atlantikinseln, Italien/Adria-Nebenreviere, Balkan und Schwarzes Meer, zusätzliche Binnenreviere.", "",
      "## Charge 005", "", f"- vollständig geprüft: {len(results['spots'])}", f"- direkt `accept_as_worth_trip`: {v['accept_as_worth_trip']}",
      f"- `accept_after_correction`: {v['accept_after_correction']}", f"- blockiert / Hold: {v['hold_for_more_research']}",
      f"- ausgeschlossen oder anders einzustufen: {excluded}", f"- bereits vorhandene Duplikate: {v['reject_as_duplicate']}", "",
      "## Kumuliert", "", "- vollständig geprüft: 125", f"- direkt akzeptiert: {19 + v['accept_as_worth_trip']}",
      f"- potenziell akzeptabel einschließlich Korrekturfällen: {60 + accepted}", "- noch bis 400 vollständig geprüften Kandidaten: 275",
      f"- noch bis 400 potenziell akzeptablen `worth_trip`-Spots: {400 - (60 + accepted)}", f"- noch bis 400 direkt akzeptierten Spots: {400 - (19 + v['accept_as_worth_trip'])}", "",
      "## Duplikatgrenze", "", "- Öffentlicher Live-Katalog (46 Spots), öffentliche Regionen und Repository-Seed wurden nach dem Blind-Freeze geprüft.",
      "- Leucate – La Franqui, Somo und Prasonisi sind Bestandsduplikate und zählen nicht erneut.",
      "- Vollständiger Draft-/Cloud-Abgleich bleibt vor jeder späteren Anlage zwingend.", "",
      "## Nächste Charge", "", "Charge 006 priorisiert Portugal außerhalb des bestehenden Live-Katalogs, Azoren/Madeira und weitere belastbare Atlantikreviere.", ""]
    (ROOT / "progress.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    b = load("batch-005-blind-research.json"); r = load("batch-005-results.json")
    i = load("batch-005-blind-image-candidates.json"); reg = load("raw-candidates.json")
    comparison(b, r); images_report(i, r); progress(reg, r)
