# Wetterprofile: Pilot- und Reviewprozess

## Offene Verantwortlichkeiten

Vor fachlichem Start müssen Product Owner, Profilersteller, Zweitprüfer,
akzeptierte Quellenbasis und maximales Live-Testbudget benannt werden. Ohne
diese Angaben werden keine realen Profilwerte eingetragen.

## Pilotmatrix

In `/admin/weather` werden zwölf **vorhandene** Spots ausgewählt: je vier aus
DE, NL und DK. Angestrebt werden offene Küste, Insel/Ästuar, Binnengewässer und
ein komplexer Fall. Fehlende Archetypen werden dokumentiert; es werden keine
Testspots erfunden.

Die freigegebene Namensmatrix liegt in `config/weather-pilot-spots.json`.
`spot_id` bleibt dort so lange `null`, bis ein eindeutiger kanonischer Datensatz
existiert. Der lokale Datenbankstand enthält derzeit keinen Spot; im Seedkatalog
existieren nur `Schilksee`, ein nicht seitengenaues `Brouwersdam` und ein anderer
Fehmarn-Spot. Diese werden nicht still auf die gewünschten Reviere umgebogen.

Pro Spot werden Spot-ID, geprüfte Koordinate, Zeitzone, Höhe samt Quelle,
wasserwärtige Küstennormale samt Quelle/Begründung, Stufe, Referenzpunkte,
Unsicherheiten sowie gegebenenfalls Sektoren dokumentiert. `facing` ist keine
Quelle und darf nicht übernommen werden.

Advanced bleibt unabhängig von vorhandenen Sektoren deaktiviert. Profile sind
keine Voraussetzung für Current oder Forecast.
Das aktuelle Datenmodell besitzt kein eigenes Feld für Ersteller und Prüfer;
diese Angaben müssen bis zu einer bewussten Datenmodellentscheidung im
bestehenden externen Freigabeprotokoll geführt werden. Sie werden nicht in freie
Wetterfelder hineinkodiert.

## Live-Smoke-Test

Der Runner ist standardmäßig blockiert und schreibt keine Wetterwerte:

```powershell
$env:WEATHER_LIVE_SMOKE='1'
$env:WEATHER_SMOKE_MAX_CALLS='400'
$env:WEATHER_SMOKE_MODE='manual'
$env:WEATHER_SMOKE_SIZE='3'
python scripts/weather_live_smoke.py
```

Jeder Spot benötigt zwei Endpunkte; bis zu drei Retry-Versuche werden einzeln
gezählt. Der Runner erzwingt 400 Requests je Lauf, 800 je Berliner Kalendertag,
60 je Minute, höchstens vier parallele Spots sowie höchstens einen automatischen
und einen zusätzlichen manuellen Lauf täglich. Er prüft Vertrag, 10-Tage-Horizont,
Detail-/Trendgrenze, gültige Richtungen, Böenuntergrenze und Current-Auflösung.
Er gibt nur aggregierte Metadaten aus. 429 und Timeouts werden nicht live
provoziert.

Ohne explizite UUIDs wählt der Runner deterministisch veröffentlichte
kanonische Spots mit gültigen Koordinaten und bevorzugt DE, NL und DK. Optional
kann `WEATHER_SMOKE_SPOT_IDS` eine Diagnoseauswahl vorgeben; die Variable und
die Pilotdatei sind niemals produktive Allowlists.

## Rollback

Die Adminseiten sind unabhängig vom Wetterservice zurücknehmbar. Ein Profil
kann auf `coordinates` und inaktiv gesetzt werden, ohne seine Basisdaten zu
löschen. Bei Providerproblemen gibt es keinen persistenten Wetterfallback.
