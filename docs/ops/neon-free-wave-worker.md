# Kostenloser Wellen-Worker mit Neon und GitHub Actions

Diese Betriebsart veröffentlicht EWAM, GWAM und NOAA GFS-Wave ohne permanenten
Server. GitHub Actions führt die vorhandene Python-Pipeline aus, Neon Postgres
bleibt die Control Plane und ein öffentlicher Neon-Object-Storage-Bucket enthält
die unveränderlichen Feldartefakte.

## Einmalige Neon-Konfiguration

Im bestehenden Produktionsprojekt einen Bucket mit `public_read` anlegen.
Modellartefakte dürfen nicht in Postgres oder Vercel Blob gespeichert werden.
Der Workflow löst die branchgebundene S3-Konfiguration mit dem Neon CLI erst
zur Laufzeit auf; Storage-Schlüssel werden nicht lokal kopiert.

Folgende Werte werden benötigt:

| Ziel | Name | Art |
|---|---|---|
| GitHub Secret | `NEON_API_KEY` | Neon-API-Zugriff für den Worker |
| GitHub Secret | `POOLED_DATABASE_URL` | gepoolte Produktionsdatenbank |
| GitHub Secret | `VERCEL_TOKEN` | nur für den manuellen Bootstrap |
| GitHub Variable | `NEON_PROJECT_ID` | bestehendes Neon-Projekt |
| GitHub Variable | `WEATHER_FIELD_STORAGE_BUCKET` | Bucket-Name |
| GitHub Variable | `WEATHER_FIELD_STORAGE_PREFIX` | z. B. `production` |
| GitHub Variable | `WAVE_FIELD_WORKER_ENABLED` | erst nach Smoke-Test `true` |

`WORKER_JWT_SECRET` wird aus den bereits vorhandenen Repository-Secrets
verwendet. Der manuelle Workflow **Configure Production Wave Storage** überträgt
die von Neon gelieferten Werte direkt in beide Vercel-Produktionsprojekte.

Die Vercel-Produktionsumgebungen benötigen dieselben
`WEATHER_FIELD_STORAGE_*`-Werte sowie:

```text
WEATHER_FIELD_STORAGE_BACKEND=s3
WEATHER_FIELD_STORAGE_ADDRESSING_STYLE=path
WEATHER_FIELD_STORAGE_BUDGET_BYTES=4500000000
WEATHER_FIELD_PIPELINE_ENABLED=true
WAVE_FIELD_PUBLIC_ENABLED=true
WAVE_FIELD_AUTO_ACTIVATE=true
```

Der API-Prozess benötigt die Zugangsdaten zum Lesen von Manifesten und
Serien-Tiles, obwohl der Bucket für Browserzugriffe öffentlich lesbar ist.

## Kosten- und Sicherheitsgrenzen

- Der Worker verarbeitet die Modelle nacheinander; parallele Läufe können das
  gemeinsame Speicherbudget nicht überbuchen.
- Pro Modell bleiben zwei vollständige Zyklen erhalten. Aktive Veröffentlichung und direkter
  Rollback-Vorgänger werden zusätzlich geschützt.
- Das harte Budget liegt bei 4,5 GB und damit 500 MB unter dem kostenlosen
  5-GB-Limit. Vor jedem Lauf wird Retention ausgeführt.
- Ein einzelner Lauf darf höchstens 800 MB plus eine begrenzte Reserve für
  Manifest und Asset-Index schreiben. Das deckt den gemessenen GWAM-Bedarf von
  rund 740 MB ab; die Pipeline bricht vor dem überschreitenden Objekt ab.
- Abgebrochene direkte Publisher-Läufe werden nach dem Stale-Schwellwert als
  fehlgeschlagen markiert. Ihre Teilassets zählen nicht zu den zwei
  Retention-Zyklen und werden vor dem nächsten Lauf entfernt.
- Ein Storage-Smoke-Test prüft Schreiben, Lesen und Löschen, bevor Modelldaten
  geladen werden.

## Aktivierung

1. Bucket und Basiswerte konfigurieren, `WAVE_FIELD_WORKER_ENABLED` noch nicht setzen.
2. Workflow **Configure Production Wave Storage** einmal ausführen und beide
   Vercel-Projekte neu deployen.
3. Workflow **Production Wave Field Publication** manuell mit einem Modell
   starten und Storage- sowie Qualitätsausgabe prüfen.
4. Manuell mit `all` starten. Der serielle Lauf darf bis zu vier Stunden dauern;
   der abschließende Doctor muss drei aktive,
   gesunde Veröffentlichungen melden.
5. `python -m scripts.production_readiness api-smoke --require-wave-fields`
   gegen die Produktions-API ausführen.
6. Erst danach `WAVE_FIELD_WORKER_ENABLED=true` setzen. Der geplante Lauf startet
   zweimal täglich nach Abschluss der freien Modellzyklen. Die reduzierte
   Frequenz hält den seriellen Drei-Modell-Worker innerhalb des kostenlosen
   Compute-Budgets; manuelle Zusatzläufe nur für Störungsbehebung verwenden.

Bei einem Fehler bleibt die letzte aktive Veröffentlichung erhalten. Das
Storage-Budget oder die Retention dürfen nicht ohne gemessene Assetgrößen
erhöht werden, um einen fehlgeschlagenen Lauf zu erzwingen.
