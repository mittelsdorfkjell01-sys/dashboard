# Wetterdaten W1 – globaler Datenvertrag

Stand: 2026-08-13. W1 erweitert den bestehenden Open-Meteo-Übergangspfad additiv. Der öffentliche Produktname bleibt **Surfwinddata Forecast**; Windkonsens, Gewichte und Geoprofilphysik werden nicht geändert.

## Vertrag und Einheiten

`contract_version=weather-v2`, `timezone=<IANA>` und die Gruppen `atmosphere`, `solar`, `marine` begleiten jeden neuen Snapshot. Stunden liegen als UTC-Instants vor und Tage als lokales `local_date`. Neue Stundenfelder sind `apparent_temperature_c` (°C), `cloud_cover_pct` (%), `pressure_msl_hpa` (hPa), `uv_index`, roher `weather_code`, `weather_condition` und `is_day`. Bestehende `air`, `precip`, `swell`, `period`, `swell_dir` und `sst` bleiben kompatibel. Tagesfelder liegen additiv in `summary`: Temperatur min/max (°C), Niederschlagssumme (mm), UV-Maximum, WMO-Zustand, UTC-Sonnenzeitpunkte und `solar_state`.

Fehlende oder unplausible Einzelwerte sind `null`, niemals erfundene Nullen. Strukturell unsortierte oder doppelte Stundenachsen verhindern die Veröffentlichung. Alte Snapshots ohne v2-Felder bleiben über optionale Defaults lesbar.

## Provider und Marine

Atmosphäre fordert zehn Tage in metrischen Einheiten einschließlich Gefühlstemperatur, Niederschlag, Bewölkung, Meeresspiegeldruck, UV, WMO-Code und Tag/Nacht an. Täglich werden Temperatur, Niederschlag, Wettercode, Sonnenzeiten, Tageslichtdauer und UV-Maximum angefordert. Marine verwendet `cell_selection=sea`, den real zurückgegebenen Horizont und Wellenhöhe/-periode/-richtung sowie Meeresoberflächentemperatur.

Marine wird nur für `water_type` ocean, sea oder lagoon abgerufen. lake/river/reservoir ist `not_applicable_inland`; unbekannte Klassifikation ist `unknown_location_type`. Ein zurückgegebener Meeresrasterpunkt darf höchstens `WEATHER_MARINE_GRID_MAX_KM` (Standard 25 km) entfernt sein. Provider- oder Marinefehler löschen keinen gültigen Atmosphärenforecast.

## Lebenszyklus und Betrieb

Create, Community-Freigabe, Koordinatenänderung, Admin/Curator, Cron und `scripts/forecast_backfill.py` nutzen denselben Publisher. Der Schlüssel enthält Spot, Koordinatenhash, Jobgrund, Vertragsversion und Stundenbucket; ein laufender Spotjob blockiert Parallelgenerationen. Snapshots werden erst nach Validierung innerhalb derselben Transaktion aktiviert; ein jüngerer aktiver Snapshot gewinnt ein Rennen.

Backfill ist auf zehn begrenzt und unterstützt `--dry-run`, `--mode canary`, `--mode validation` und `--offset`. Fehler bleiben spotlokal. W1 führt keine Migration ein, da Payload und interne Diagnostik bereits versionierte JSONB-Felder sind.

## W2-Empfehlung

W2 sollte modell- und lead-time-spezifische Wetterwerte ausschließlich im Shadow-Betrieb gegen qualifizierte Beobachtungen vergleichen. Erst ausreichende Messreihen rechtfertigen eine neue öffentliche Gewichtung oder Genauigkeitsaussage.
