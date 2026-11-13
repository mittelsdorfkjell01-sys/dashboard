# Gezeitenbetrieb

Die technische Zielarchitektur für den europäischen 10-Tage-Forecast, die
Tidenkarte, freie Pegelquellen und die stationsgestützte Geokorrektur steht in
[`docs/architecture/tide-platform-v2.md`](architecture/tide-platform-v2.md).

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

1. In **My AVISO+ → My products** prüfen, dass **FES (Finite Element Solution
   – Oceanic Tides Heights)** aktiv ist. Ein AVISO-Konto ohne diese
   Produktfreigabe erhält beim Download weiterhin HTTP 401.
2. Benutzername und Passwort ausschließlich für die aktuelle Installationsshell
   setzen; nie in `.env`, GitHub, Vercel oder das Repository schreiben:
   `AVISO_USERNAME` und `AVISO_PASSWORD`.
3. Den Zugriff ohne Modelldownload prüfen:
   `python -m scripts.fes2022_assets access`.
4. Ziel und Platzbedarf gegen den aktuellen offiziellen Katalog prüfen:
   `python -m scripts.fes2022_assets plan --target /opt/surfwinddata/fes2022b`.
5. FES2022b Ocean Tide Elevations und die extrapolierte Rastermaske
   reproduzierbar installieren:
   `python -m scripts.fes2022_assets install --target /opt/surfwinddata/fes2022b --license-accepted-at YYYY-MM-DD`.
   Der Installer lädt genau die 34 offiziellen Höhenkonstituenten und die
   FES-Maske, setzt abgebrochene Downloads fort, entpackt atomar und erzeugt
   `fes2022.yaml`, die gemeinfreie Natural-Earth-Landmaske,
   `tide-assets.json` sowie eine geheimnisfreie `worker.env`. Das Ziel muss
   außerhalb dieses Repositorys liegen. `load_tide` ist nicht nötig, weil der
   Surfwinddata-Worker die astronomische Wasserhöhe und nicht die elastische
   Gezeitenlast berechnet.
   Unter Windows führt
   `.\scripts\install-fes2022.ps1 -LicenseAcceptedAt YYYY-MM-DD` Zugangstest
   und Installation zusammen aus. Das Passwort wird verdeckt abgefragt, nur an
   den Kindprozess übergeben und anschließend aus der Prozessumgebung entfernt.
6. `requirements-tide.txt` in einer Python-3.11-Umgebung installieren; es bindet
   die gemeinsame Anwendungslaufzeit automatisch ein.
7. Die fünf `TIDE_*`-Pfade aus der erzeugten `worker.env` in der privaten
   Worker-Umgebung setzen. Die Datei enthält keine AVISO-Zugangsdaten.
8. Den vollständigen Preflight ausführen:
   `python -m scripts.tide_europe_rollout preflight --verify-checksums`.
9. Den ersten Batch nur ansehen:
    `python -m scripts.tide_europe_rollout bootstrap --limit 5`.
10. Den Batch einplanen:
    `python -m scripts.tide_europe_rollout bootstrap --apply --limit 5`.
11. `python -m app.tides.worker --limit 1` zunächst manuell ausführen.

Die GitHub Action `tide-worker.yml` erwartet einen privaten Self-hosted Runner
mit Label `tide-worker` und dem persistenten Volume. Erst danach wird die
Repository-Variable `TIDE_WORKER_ENABLED=true` gesetzt. AVISO-Zugangsdaten und
Modelldateien werden nicht über GitHub Actions übertragen.

Bei aktivierter Variable läuft der Worker täglich in begrenzten Batches. Der
Bootstrap berücksichtigt ausschließlich veröffentlichte Spots mit `ocean`,
`sea` oder `lagoon`, aktiviert Profile privat und veröffentlicht niemals
automatisch. Die Freigabe erfolgt nach Ankerprüfung in **FES-Tide Europa** im
Adminbereich. `python -m scripts.tide_europe_rollout status` zeigt den
betrieblichen Stand.

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
