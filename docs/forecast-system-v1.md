# Surfwinddata Forecast-System V1

Stand: 2026-08-12. Der öffentliche Vertrag umfasst zehn Tage; Tage 1–5
enthalten Stundenwerte, Tage 6–10 ausschließlich belastbare Tagestrends.

## Datenfluss und Fallbacks

1. Direkte Provider werden nach Region, Laufalter, Horizont und Vollständigkeit geroutet.
2. Rohwerte werden in SI-Einheiten und meteorologische u/v-Komponenten normalisiert.
3. Ein versioniertes Geoprofil korrigiert jeden Modellbeitrag separat und begrenzt.
4. Der familienbewusste Vektorkonsens erzeugt einen Surfwinddata Forecast.
5. Erst ein vollständiger Snapshot wird atomar aktiviert.

Fallback-Reihenfolge: regionaler korrigierter Konsens, globaler korrigierter
Konsens, globaler Basiskonsens, letzter gültiger Snapshot, Open-Meteo während
der Migration, Nichtverfügbarkeitszustand. Ein fehlgeschlagener Job deaktiviert
niemals den zuletzt gültigen Snapshot.

## Provider und Aktivierung

| Modell | Rolle | Zugang | Status |
|---|---|---|---|
| NOAA GFS 0.25° | global | NOMADS, räumliche GRIB-Subsets | direkter Adapter, Shadow |
| DWD ICON Global | global | DWD Open Data, variablenweise GRIB2/BZip2 | direkter Adapter, Shadow |
| DWD ICON-EU | Europa | DWD Open Data | direkter Adapter, Shadow |
| DWD ICON-D2 | Mitteleuropa/Kurzfrist | DWD Open Data | direkter Adapter, Shadow |
| ECMWF IFS/AIFS Open | global | ECMWF Open Data | Registry; Downloader nach Lastmessung |
| Open-Meteo | Übergang | Forecast/Marine API | aktiver Migrationsfallback |

Shadow bedeutet: Abruf und Normalisierung dürfen diagnostisch laufen, aber nur
vollständige und validierte Läufe können später in einen veröffentlichten
Snapshot eingehen. Die Open-Meteo-Ausgabe bleibt während dieser Phase stabil.

Nicht im ersten Schnitt aktiviert: Météo-France, DMI/KNMI HARMONIE, MET Norway,
MeteoSwiss und weitere Regionalmodelle. Grund sind die noch nicht je Provider
gemessenen Downloadmengen, Zeitachsen und Dekodier-/Nutzungsbedingungen; es
werden keine inoffiziellen Scraper oder Zugriffsumgehungen eingesetzt.

## Geoprofil und Physik

Jeder Spot erhält idempotent mindestens ein Koordinatenprofil. Optional
bereitgestellte lokale NASA-SRTM-HGT-Kacheln ergänzen Höhe und 16 gerichtete
Geländesektoren. Fehlende Raster erzeugen eine Warnung und neutrale Korrektur.
Es werden keine Höhen, Küsten oder lokalen Effekte erfunden.

Die erste automatische Korrektur berücksichtigt begrenzt den Höhenunterschied
zwischen Modell und Spot sowie gerichtete Geländeabschattung. Der Gesamtfaktor
bleibt zwischen 0,78 und 1,18. Thermik, Düse, Fetch, Rauigkeitswechsel und
Stabilitätskorrektur verändern den Hauptwert noch nicht. Jede aktive
Teilkorrektur wird intern mit Version, Faktor, Begründung und Unsicherheit geführt.

## Konsens und Qualität

Windrichtungen werden nie als Gradwerte gemittelt. Korrigierte u/v-Vektoren
werden nach Auflösung, Lead Time, Laufalter und Vollständigkeit gewichtet.
Beiträge derselben Modellfamilie erhalten gemeinsam ein Gewichtslimit. Böen
werden separat behandelt und niemals unter Mittelwind veröffentlicht.

Interne Stufen: `baseline`, `automatic`, `calibrated`, `reviewed`. Öffentlich
erscheinen nur der Produktname, verständliche Konfidenz, Unsicherheit,
Aktualisierungszeit und Quellen – keine Modelle, Gewichte oder Korrekturfaktoren.

## Jobs, Backfill und Betriebsschutz

Neue Spots und Koordinatenänderungen erzeugen einen deduplizierten Job. Manuelle
Jobs laufen über `/admin/weather/spots/{id}/recalculate`; Batch-Vorschau und
Batch-Neuberechnung sind begrenzt. Der bestehende Maintenance-Cron verarbeitet
höchstens `FORECAST_JOB_BATCH_SIZE` Jobs pro Lauf.

Sicherer Backfill:

```powershell
python scripts/forecast_backfill.py --batch-size 10 --dry-run
python scripts/forecast_backfill.py --batch-size 10
```

Grenzen: 25 Spots je Backfill-Batch, standardmäßig drei Jobs je Cron-Lauf,
50 MB je Providerlauf, 250 MB pro Tag, zwei parallele Abrufe und 18 Stunden
Rohdatenhaltung. Überschreitungen führen zum sicheren Abbruch, nicht zu Retry-Stürmen.

## Attributionen

Das zentrale Register liegt in `app/forecast/registry.py`. Geprüfte Primärquellen:

- NOAA/NCEP GFS/NOMADS: https://www.nco.ncep.noaa.gov/pmb/products/gfs/nomads/
- DWD Open Data: https://opendata.dwd.de/weather/nwp/
- ECMWF Open Data: https://data.ecmwf.int/forecasts/
- NASA SRTM: https://www.earthdata.nasa.gov/data/instruments/srtm
- Open-Meteo Übergang: https://open-meteo.com/

Vor einer kommerziellen Nutzung werden alle Quellen erneut geprüft. Zugangsdaten
und Datenbank-URLs gehören ausschließlich in die Laufzeitumgebung.

## Erweiterung

Ein neuer Provider implementiert dieselben `ProviderRequest`- und
`NormalizedModelValue`-Verträge, erhält einen Registry-Eintrag und muss Fixture-,
Vertrags-, Ausfall-, Zeitachsen-, Einheiten- und Kostenlimit-Tests bestehen.
Aktivierung erfolgt erst nach Shadow-Vergleich und vollständigem Qualitätsgate.
