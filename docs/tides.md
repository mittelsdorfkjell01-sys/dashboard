# Gezeitenbetrieb

## Modell und Lizenz

Surfwinddata verwendet FES2022b Ocean Tide Elevations über die offizielle
CNES-Bibliothek PyFES. Die Modelldaten werden von AVISO bereitgestellt. Vor dem
Download muss der Betreiber sich registrieren und die jeweils aktuelle
AVISO-Lizenz akzeptieren.

Die FES-Höhen fallen nach aktuellem Lizenztext unter die Standardlizenz. Daraus
erzeugte abgeleitete Ergebnisse dürfen wissenschaftlich, operativ und
kommerziell verwendet werden. Originale AVISO-Produkte dürfen nicht
weitergegeben werden. Die Lizenz läuft ab Download fünf Jahre und muss danach
erneut geprüft werden. Jede öffentliche Nutzung nennt die Quelle:

> Generated using AVISO+ Products. FES2022 was produced by LEGOS, NOVELTIS and
> CLS Ocean and Climate Division, funded by CNES and distributed by AVISO+.

Verbindliche Quellen:

- https://www.aviso.altimetry.fr/en/data/products/auxiliary-products/global-tide-fes/release-fes22.html
- https://aviso.altimetry.fr/en/data/data-access/fileadmin/documents/data/License_Aviso.pdf
- https://aviso.altimetry.fr/fileadmin/documents/data/tools/hdbk_FES2022.pdf

## Installation

Die Rohdateien gehören nie ins Repository, Neon, Vercel Blob oder den
Vercel-Function-Build. Der externe Worker benötigt ein privates persistentes
Volume. Nach Erhalt des AVISO-Zugangs:

1. FES2022b Ocean Tide Elevations und die extrapolierte Rastermaske laden.
2. Prüfsummen und Modellversion protokollieren.
3. Dateien auf das private Worker-Volume entpacken.
4. Eine PyFES-YAML mit allen gelieferten Komponenten anlegen.
5. Eine aktuelle Natural-Earth-Landmaske als GeoJSON ablegen. Natural Earth ist
   gemeinfrei; Downloadversion und Prüfsumme werden zusammen mit dem Modell
   dokumentiert: https://www.naturalearthdata.com/about/terms-of-use/
6. `requirements-tide.txt` in einer Python-3.11-Umgebung installieren.
7. `TIDE_PYFES_CONFIG`, `TIDE_MASK_FILE` und `TIDE_LAND_GEOJSON` setzen.
8. `python -m app.tides.worker --limit 1` zunächst manuell ausführen.

Die GitHub Action `tide-worker.yml` erwartet einen privaten Self-hosted Runner
mit Label `tide-worker` und dem persistenten Volume. Erst danach wird die
Repository-Variable `TIDE_WORKER_ENABLED=true` gesetzt. AVISO-Zugangsdaten und
Modelldateien werden nicht über GitHub Actions übertragen.

## Ablauf

- Neue Profile sind deaktiviert und nicht öffentlich.
- Der Worker wählt einen FES-Wasserpunkt bis zur konfigurierten Suchdistanz.
- Die direkte Verbindung darf nach Verlassen des Strandpunkts keine Landfläche
  schneiden. FES-Land- und Seemasken werden zusätzlich geprüft.
- Automatische und manuelle Anker müssen nach der Workerprüfung im Dashboard
  bestätigt werden.
- PyFES berechnet eine UTC-Kurve in Fünf-Minuten-Schritten für mindestens 60
  Tage. Parabolisch verfeinerte lokale Extrema ergeben Hoch- und Niedrigwasser.
- Korrekturreihenfolge: Rohzeit + allgemeiner Offset + Ereignisoffset.
- Aktive Einzelüberschreibungen werden zuletzt angewendet und überleben eine
  Neuberechnung anhand von Ereignistyp und reproduzierbarer Rohzeit.
- Erst nach vollständiger erfolgreicher Berechnung ersetzt eine Transaktion die
  aktuelle Generation. Bei Fehlern bleiben zuvor gültige Ereignisse erhalten.

Koordinatenänderungen entfernen beide Anker, deaktivieren die öffentliche Tide
und stellen eine neue Ankerbestimmung ein. Der tägliche Worker erweitert den
Horizont, bevor weniger als 14 Tage verbleiben.

## Qualität und Unsicherheit

Zentrale Fallbackwerte in `app/tides/calculation.py`:

| Qualität | konservative Zeitunsicherheit |
| --- | ---: |
| Nur Modell | 45 Minuten |
| Anker geprüft | 30 Minuten |
| Manuell kalibriert | 20 Minuten |
| Pegelkalibriert | 10 Minuten |

Eine manuell gesetzte Unsicherheit hat Vorrang. Bei mehreren
Kalibrierungseingaben verwendet der Vorschlag Median und mediane absolute
Abweichung; mindestens fünf Minuten Unsicherheit bleiben erhalten. Änderungen
ab 30 Minuten benötigen eine Begründung. 90 Minuten lösen eine Warnung aus,
360 Minuten sind die harte serverseitige Grenze. Alle Werte sind konfigurierbar.

## Grenzen

Die Angaben sind astronomische Prognosen. Wetterbedingter Wasserstand,
Sturmflut, Abfluss und lokale Strömung können abweichen. Buchten, Lagunen und
Flussmündungen benötigen häufig lokale Kalibrierung. Die angegebene Unsicherheit
ist spotbezogen und keine Garantie. Absolute Wasserstände werden nicht
veröffentlicht, weil kein geprüfter vertikaler Höhenbezug vorliegt.
Komponentenspezifische Phasen- und Amplitudenänderungen sind im Schema für eine
spätere fachliche Kalibrierung vorbereitet, werden in dieser Version aber nicht
angewendet. Ohne belastbare Beobachtungsreihe wäre das Scheingenauigkeit.

Vor der öffentlichen Freigabe sind mindestens ein offener Küstenspot, eine
Bucht und eine Flussmündung gegen fachlich bekannte Referenzzeiten zu prüfen.
Ohne installierte FES-Dateien dürfen diese Prüfungen nicht durch erfundene
Sollwerte ersetzt werden.

## Rollback und Monitoring

Profilrevisionen sind unveränderlich. Eine Wiederherstellung erzeugt eine neue
Version und bewahrt den gesamten Verlauf. Migration `0025_tides` kann vor der
Produktivnutzung zurückgesetzt werden; sie löscht ausschließlich Tide-Tabellen.
Nach erzeugten Tideprofilen darf sie nur nach einem Datenexport zurückgesetzt
werden.

`GET /admin/spots/tide/monitoring` liefert aktive Spots, fehlende Anker,
veraltete Horizonte und den letzten erfolgreichen Lauf. Jobfehler und
spotbezogene Fehler stehen zusätzlich im Profil und in `tide_calculation_runs`.
