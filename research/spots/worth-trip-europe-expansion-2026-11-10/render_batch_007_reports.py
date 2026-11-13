"""Render batch 007 comparison, image review and cumulative progress."""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
load=lambda n:json.loads((ROOT/n).read_text(encoding="utf-8"))
def esc(v):
 if isinstance(v,dict): v=", ".join(f"{k}={x}" for k,x in v.items())
 if isinstance(v,list): v=", ".join(map(str,v))
 return str(v).replace("|","\\|").replace("\n"," ")

def comparison(blind,results):
 by={x["name"]:x for x in results["spots"]}
 lines=["# Charge 007: feldweiser Vergleich","","Stand: 2026-11-10. Blindrecherche und Bildsuche wurden vor dem Bestandsabgleich eingefroren. Öffentlicher Live-Katalog (46 Spots), Repository-Seed und öffentliche Regionen wurden danach geprüft; Draft-/Cloud-Daten blieben technisch unzugänglich.",""]
 for x in blind["spots"]:
  y=by[x["name"]]; pubs="; ".join(z["publisher"] for z in x["sources"][:3])
  lines += [f"## {x['name']}","","| Feld | Unabhängiges Ergebnis | Bestandsabgleich | Bewertung / Korrektur | Quellen |","|---|---|---|---|---|",
   f"| Identität | {esc(x['identity'])} | Kein veröffentlichter Live- oder Seed-Datensatz | {esc(y['correction'])} | {esc(pubs)} |",
   f"| Einstieg | {esc(x['entry'])} | `{y['coordinate_status']}` | Discovery-Punkt, keine freigegebene Startzone | Blindrecherche |",
   f"| Sport / Bedingungen | {esc(x['sports'])}; {esc(x['conditions'])} | Keine lokalen Werte | Nur quellenbelegte, konditionale Werte übernehmen | {esc(pubs)} |",
   f"| Zugang / Regeln | {esc(x['access_rules'])} | Keine lokalen Werte | Schutz-, Bade-, Hafen- und Betreiberzonen haben Vorrang | {esc(pubs)} |",
   f"| Region | {esc(y['region'])} | `{y['region_status']}` | Region vor einer Anlage redaktionell prüfen | Live-Regionsabgleich |",
   f"| Bild | Separat gesucht, nichts freigegeben | `{y['image_status']}` | Ort, Motiv, Lizenz und Auflösung visuell prüfen | Commons / Openverse |",
   f"| Reisewert | {esc(x['trip_value'])} | Keine lokale Einstufung | Abschluss: `{y['verdict']}` | {esc(pubs)} |",""]
 (ROOT/"batch-007-comparison.md").write_text("\n".join(lines),encoding="utf-8")

def image_report(images,results):
 lines=["# Charge 007: unabhängige Bildprüfung","","Kein Suchtreffer ist automatisch freigegeben.","","| Spot | Treffer | Providerfehler | Status | Nächster Schritt |","|---|---:|---|---|---|"]
 for img,res in zip(images["spots"],results["spots"],strict=True):
  items=sum(len(v) for v in img["providers"].values()); errors=", ".join(img["errors"]) or "keine"
  lines.append(f"| {res['name']} | {items} | {errors} | `{res['image_status']}` | Visuell, geografisch und lizenzseitig prüfen bzw. erneut suchen |")
 lines += ["","## Ergebnis","","- Kein Bild wurde freigegeben oder Produktdaten zugeordnet.","- Treffer bleiben unreviewte Kandidaten; Providerfehler und Nulltreffer bleiben offen.",""]
 (ROOT/"batch-007-image-review.md").write_text("\n".join(lines),encoding="utf-8")

def progress(register,results):
 v=Counter(x["verdict"] for x in results["spots"]); accepted=v["accept_as_worth_trip"]+v["accept_after_correction"]
 excluded=sum(v[k] for k in ("reject_as_duplicate","reject_as_world_class","reject_insufficient_trip_value","reject_insufficient_evidence"))
 lines=["# Europaweite `worth_trip`-Recherche: Fortschritt","","Stand: 2026-11-10. Pilotcharge 001 und Erweiterungscharge 002–007 sind abgeschlossen. Es wurden keine Produktdaten geschrieben.","",
  "## Register und Abdeckung","",f"- Rohkandidaten im Discovery-Register: {register['statistics']['unique_raw_candidates']}","- Charge 007 ergänzt Norditaliens Seen, nördliche/mittlere Adria, Puglia, Toskana, Lazio und weitere sizilianische Reviere.","- Weiter offen: Balkan und östliches Schwarzes Meer, zusätzliche Atlantikinseln, Frankreich/Spanien-Binnenreviere und weitere Alpen-/Nordosteuropa-Seen.","",
  "## Charge 007","",f"- vollständig geprüft: {len(results['spots'])}",f"- direkt `accept_as_worth_trip`: {v['accept_as_worth_trip']}",f"- `accept_after_correction`: {v['accept_after_correction']}",f"- blockiert / Hold: {v['hold_for_more_research']}",f"- ausgeschlossen oder anders einzustufen: {excluded}",f"- bereits vorhandene Duplikate: {v['reject_as_duplicate']}","",
  "## Kumuliert","","- vollständig geprüft: 175",f"- direkt akzeptiert: {37+v['accept_as_worth_trip']}",f"- potenziell akzeptabel einschließlich Korrekturfällen: {96+accepted}","- noch bis 400 vollständig geprüften Kandidaten: 225",f"- noch bis 400 potenziell akzeptablen `worth_trip`-Spots: {400-(96+accepted)}",f"- noch bis 400 direkt akzeptierten Spots: {400-(37+v['accept_as_worth_trip'])}","",
  "## Duplikatgrenze","","- Öffentlicher Live-Katalog (46 Spots), öffentliche Regionen und Repository-Seed wurden nach dem Blind-Freeze geprüft.","- Keine exakte Live- oder Seed-Dublette in Charge 007; Puzziteddu/Mondello/Pozzallo sind von Lo Stagnone getrennte Reviere.","- Vollständiger Draft-/Cloud-Abgleich bleibt vor jeder späteren Anlage zwingend.","",
  "## Nächste Charge","","Charge 008 priorisiert Slowenien, Kroatien, Bosnien-Herzegowina, Montenegro, Albanien und Nordmazedonien außerhalb bereits geprüfter Hauptspots.",""]
 (ROOT/"progress.md").write_text("\n".join(lines),encoding="utf-8")

if __name__=="__main__":
 b=load("batch-007-blind-research.json"); r=load("batch-007-results.json"); i=load("batch-007-blind-image-candidates.json"); reg=load("raw-candidates.json")
 comparison(b,r); image_report(i,r); progress(reg,r)
