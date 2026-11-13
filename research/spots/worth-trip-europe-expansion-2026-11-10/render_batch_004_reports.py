"""Render batch 004 comparison, image review and cumulative progress."""

import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
load=lambda n: json.loads((ROOT/n).read_text(encoding="utf-8"))


def esc(v):
    if isinstance(v,dict): v=", ".join(f"{k}={x}" for k,x in v.items())
    if isinstance(v,list): v=", ".join(map(str,v))
    return str(v).replace("|","\\|").replace("\n"," ")


def comparison(blind,results):
    by={x["name"]:x for x in results["spots"]}
    lines=["# Charge 004: feldweiser Vergleich","",
           "Stand: 2026-11-10. Blindrecherche und Bildsuche wurden vor dem Bestandsabgleich eingefroren. Der öffentliche Live-Katalog (46 Spots), Repository-Seed und öffentliche Regionen wurden geprüft; Draft-/Cloud-Daten blieben technisch unzugänglich.",""]
    for x in blind["spots"]:
        y=by[x["name"]]; pubs="; ".join(z["publisher"] for z in x["sources"][:3])
        lines += [f"## {x['name']}","","| Feld | Unabhängiges Ergebnis | Bestandsabgleich | Bewertung / Korrektur | Quellen |","|---|---|---|---|---|",
          f"| Identität | {esc(x['identity'])} | Kein veröffentlichter Live- oder Seed-Datensatz | {esc(y['correction'])} | {esc(pubs)} |",
          f"| Einstieg | {esc(x['entry'])} | `{y['coordinate_status']}` | Discovery-Punkt, keine freigegebene Startzone | Blindrecherche |",
          f"| Sport / Bedingungen | {esc(x['sports'])}; {esc(x['conditions'])} | Keine lokalen Werte | Nur quellenbelegte, konditionale Werte übernehmen | {esc(pubs)} |",
          f"| Zugang / Regeln | {esc(x['access_rules'])} | Keine lokalen Werte | Schutz-, Bade- und Betreiberzonen haben Vorrang | {esc(pubs)} |",
          f"| Region | {esc(y['region'])} | `{y['region_status']}` | Region vor einer Anlage redaktionell prüfen | Live-Regionsabgleich |",
          f"| Bild | Separat gesucht, nichts freigegeben | `{y['image_status']}` | Bildlos lassen bis Ort, Motiv, Lizenz und Auflösung bestätigt sind | Commons / Openverse |",
          f"| Reisewert | {esc(x['trip_value'])} | Keine lokale Einstufung | Abschluss: `{y['verdict']}` | {esc(pubs)} |",""]
    (ROOT/"batch-004-comparison.md").write_text("\n".join(lines),encoding="utf-8")


def images_report(images,results):
    lines=["# Charge 004: unabhängige Bildprüfung","","Kein Suchtreffer ist automatisch freigegeben.","",
           "| Spot | Treffer | Status | Nächster Schritt |","|---|---:|---|---|"]
    for img,res in zip(images["spots"],results["spots"],strict=True):
        items=img["providers"].get("wikimedia_commons",[])+img["providers"].get("openverse",[])
        viable=[z for z in items if z.get("license") not in {"by-nc","by-nc-sa","by-nc-nd","by-nd"} and (z.get("width") or 0)>=1600]
        err=f"; Fehler: {', '.join(img['errors'])}" if img["errors"] else ""
        lines.append(f"| {res['name']} | {len(items)} ({len(viable)} technisch/lizenzseitig vorprüfbar) | `{res['image_status']}`{err} | {'Visuell und geografisch prüfen' if items else 'Nach geklärter Startzone erneut suchen'} |")
    lines += ["","## Ergebnis","","- Kein Bild wurde freigegeben oder Produktdaten zugeordnet.","- Ortsnahe Kandidaten wurden für Apelviken, Viganj, Premantura, Alaçatı und Akyaka gefunden; sie bleiben ungeprüft.","- Zahlreiche Providerabfragen waren rate-limitiert, weshalb Nulltreffer ausdrücklich offen bleiben.",""]
    (ROOT/"batch-004-image-review.md").write_text("\n".join(lines),encoding="utf-8")


def progress(register,results):
    v=Counter(x["verdict"] for x in results["spots"])
    accepted=v["accept_as_worth_trip"]+v["accept_after_correction"]
    excluded=sum(v[k] for k in ("reject_as_duplicate","reject_as_world_class","reject_insufficient_trip_value","reject_insufficient_evidence"))
    lines=["# Europaweite `worth_trip`-Recherche: Fortschritt","",
      "Stand: 2026-11-10. Pilotcharge 001 und Erweiterungscharge 002–004 sind abgeschlossen. Es wurden keine Produktdaten geschrieben.","",
      "## Register und Abdeckung","",f"- Rohkandidaten im Discovery-Register: {register['statistics']['unique_raw_candidates']}",
      "- Charge 004 ergänzt Skandinavien/Baltikum, Polen, Adria, westliches Schwarzes Meer und die europäisch angebundene Ägäis.",
      "- Weiter offen: Balkan-Nebenreviere, Griechenland außerhalb der Pilotgebiete, Schwarzes Meer Ukraine/Georgien (nur bei vertretbarer aktueller Recherche), Atlantikinseln, zusätzliche Binnenreviere.","",
      "## Charge 004","",f"- vollständig geprüft: {len(results['spots'])}",f"- direkt `accept_as_worth_trip`: {v['accept_as_worth_trip']}",
      f"- `accept_after_correction`: {v['accept_after_correction']}",f"- blockiert / Hold: {v['hold_for_more_research']}",
      f"- ausgeschlossen oder anders einzustufen: {excluded}",f"- Duplikate innerhalb Charge/Bestand: {v['reject_as_duplicate']}","",
      "## Kumuliert","","- vollständig geprüft: 100",f"- direkt akzeptiert: {15+v['accept_as_worth_trip']}",
      f"- potenziell akzeptabel einschließlich Korrekturfällen: {48+accepted}","- noch bis 400 vollständig geprüften Kandidaten: 300",
      f"- noch bis 400 potenziell akzeptablen `worth_trip`-Spots: {400-(48+accepted)}",f"- noch bis 400 direkt akzeptierten Spots: {400-(15+v['accept_as_worth_trip'])}","",
      "## Duplikatgrenze","","- Öffentlicher Live-Katalog und Repository-Seed geprüft; keine neue Bestandsdublette gefunden.",
      "- Ada Bojana wird mangels unabhängiger Identität nicht zusätzlich zu Velika Plaža gezählt.",
      "- Vollständiger Draft-/Cloud-Abgleich bleibt vor jeder späteren Anlage zwingend.","",
      "## Nächste Charge","","Charge 005 priorisiert Frankreichs Atlantik-/Mittelmeer-Nebenreviere, Spanien außerhalb der bisherigen Cluster, Griechenland sowie belastbare europäische Binnenreviere.",""]
    (ROOT/"progress.md").write_text("\n".join(lines),encoding="utf-8")


if __name__=="__main__":
    b=load("batch-004-blind-research.json"); r=load("batch-004-results.json"); i=load("batch-004-blind-image-candidates.json"); reg=load("raw-candidates.json")
    comparison(b,r); images_report(i,r); progress(reg,r)
