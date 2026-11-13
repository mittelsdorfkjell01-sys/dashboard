"""Render human-readable reports for batch 009."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
blind = json.loads((ROOT / "batch-009-blind-research.json").read_text(encoding="utf-8"))
results = json.loads((ROOT / "batch-009-results.json").read_text(encoding="utf-8"))
images = json.loads((ROOT / "batch-009-blind-image-candidates.json").read_text(encoding="utf-8"))

def esc(value):
    return str(value).replace("|", "\\|").replace("\n", " ")

lines = [
 "# Charge 009: feldweiser Vergleich", "",
 "Stand: 2026-11-10. Blindrecherche und Bildsuche wurden vor dem Bestandsabgleich eingefroren. Der öffentliche Live-Katalog (46 Spots), Repository-Seed, öffentliche Regionen und frühere Chargen wurden danach geprüft; Draft-/Cloud-Daten blieben technisch unzugänglich.", "",
]
for item, result in zip(blind["spots"], results["spots"], strict=True):
    pubs = "; ".join(source["publisher"] for source in item["sources"])
    stock = "Duplikat/Subspot von " + result["duplicate_of"] if result["duplicate_of"] else "Kein veröffentlichter Live- oder Seed-Datensatz"
    lines.extend([
        "## " + item["name"], "",
        "| Feld | Unabhängiges Ergebnis | Bestandsabgleich | Bewertung / Korrektur | Quellen |",
        "|---|---|---|---|---|",
        "| Identität | {} | {} | {} | {} |".format(esc(item["identity"]), esc(stock), esc(result["correction"]), esc(pubs)),
        "| Einstieg | lat={}, lon={}, status={} | `{}` | Discovery-Punkt, keine freigegebene Startzone | Blindrecherche |".format(item["entry"]["lat"], item["entry"]["lon"], item["entry"]["status"], result["coordinate_status"]),
        "| Sport / Bedingungen | {}; {} | Keine lokalen Werte | Nur quellenbelegte, konditionale Werte übernehmen | {} |".format(esc(", ".join(item["sports"])), esc(item["conditions"]), esc(pubs)),
        "| Zugang / Regeln | {} | Keine lokalen Werte | Schutz-, Bade-, Hafen- und Betreiberzonen haben Vorrang | {} |".format(esc(item["access_rules"]), esc(pubs)),
        "| Region | {} | `{}` | Region vor einer Anlage redaktionell prüfen | Live-Regionsabgleich |".format(esc(result["region"]), result["region_status"]),
        "| Bild | Separat gesucht, nichts freigegeben | `{}` | Ort, Motiv, Lizenz und Auflösung visuell prüfen | Commons / Openverse |".format(result["image_status"]),
        "| Reisewert | {} | Blind: `{}` | Abschluss: `{}` | {} |".format(esc(item["trip_value"]), item["blind_verdict"], result["verdict"], esc(pubs)),
        "",
    ])
(ROOT / "batch-009-comparison.md").write_text("\n".join(lines), encoding="utf-8")

lines = [
 "# Charge 009: Bildprüfung", "",
 "Die Bildsuche lief vor dem Bestandsabgleich. Kein Treffer ist freigegeben: Suchrelevanz beweist weder Ort noch Motiv, Lizenzkette oder ausreichende Auflösung.", "",
 "| Kandidat | Treffer | Status | Nächster Prüfschritt |", "|---|---:|---|---|",
]
for item, image in zip(blind["spots"], images["spots"], strict=True):
    count = sum(len(values) for values in image["providers"].values())
    lines.append("| {} | {} | unreviewed | Geografie, Motiv, Urheber, Lizenz, Originalauflösung und Nutzbarkeit prüfen |".format(esc(item["name"]), count))
(ROOT / "batch-009-image-review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
