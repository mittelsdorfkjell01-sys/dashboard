# Kostenloser Wellen-Worker mit Neon und GitHub Actions

Diese Betriebsart veröffentlicht EWAM, GWAM und NOAA GFS-Wave ohne permanenten
Server. GitHub Actions führt die vorhandene Python-Pipeline aus, Neon Postgres
bleibt die Control Plane und ein öffentlicher Neon-Object-Storage-Bucket enthält
die unveränderlichen Feldartefakte.

## Einmalige Neon-Konfiguration

Im bestehenden Produktionsprojekt einen Bucket mit `public_read` anlegen und
eine S3-kompatible Zugangsberechtigung erzeugen. Modellartefakte dürfen nicht in
Postgres oder Vercel Blob gespeichert werden.

Folgende Werte werden benötigt:

| Ziel | Name | Art |
|---|---|---|
| GitHub Secret | `WEATHER_FIELD_STORAGE_ENDPOINT` | S3-Endpunkt |
| GitHub Secret | `WEATHER_FIELD_STORAGE_ACCESS_KEY` | Zugriffsschlüssel |
| GitHub Secret | `WEATHER_FIELD_STORAGE_SECRET_KEY` | geheimer Schlüssel |
| GitHub Variable | `WEATHER_FIELD_STORAGE_REGION` | Bucket-Region |
| GitHub Variable | `WEATHER_FIELD_STORAGE_BUCKET` | Bucket-Name |
| GitHub Variable | `WEATHER_FIELD_STORAGE_PREFIX` | z. B. `production` |
| GitHub Variable | `WEATHER_FIELD_PUBLIC_BASE_URL` | öffentliche HTTPS-Basis-URL |
| GitHub Variable | `WAVE_FIELD_WORKER_ENABLED` | erst nach Smoke-Test `true` |

`DIRECT_DATABASE_URL` und `WORKER_JWT_SECRET` werden aus den bereits
vorhandenen Repository-Secrets verwendet.

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
- Pro Modell bleiben drei Zyklen erhalten. Aktive Veröffentlichung und direkter
  Rollback-Vorgänger werden zusätzlich geschützt.
- Das harte Budget liegt bei 4,5 GB und damit 500 MB unter dem kostenlosen
  5-GB-Limit. Vor jedem Lauf wird Retention ausgeführt.
- Ein einzelner Lauf darf höchstens das bestehende Aktivierungslimit plus eine
  begrenzte Reserve für Manifest und Asset-Index schreiben. Die Pipeline bricht
  vor dem überschreitenden Objekt ab.
- Ein Storage-Smoke-Test prüft Schreiben, Lesen und Löschen, bevor Modelldaten
  geladen werden.

## Aktivierung

1. Bucket und Werte konfigurieren, `WAVE_FIELD_WORKER_ENABLED` noch nicht setzen.
2. Workflow **Production Wave Field Publication** manuell mit einem Modell
   starten und Storage- sowie Qualitätsausgabe prüfen.
3. Manuell mit `all` starten. Der abschließende Doctor muss drei aktive,
   gesunde Veröffentlichungen melden.
4. Vercel-Umgebungsvariablen setzen und neu deployen.
5. `python -m scripts.production_readiness api-smoke --require-wave-fields`
   gegen die Produktions-API ausführen.
6. Erst danach `WAVE_FIELD_WORKER_ENABLED=true` setzen. Der geplante Lauf startet
   viermal täglich nach Abschluss der freien Modellzyklen.

Bei einem Fehler bleibt die letzte aktive Veröffentlichung erhalten. Das
Storage-Budget oder die Retention dürfen nicht erhöht werden, um einen
fehlgeschlagenen Lauf zu erzwingen.
