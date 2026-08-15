# Spot-Massenimport (CSV/JSON)

Der Importer ist ausschließlich ein CLI-Werkzeug. Er fügt keine Route und keine
Funktion zum Dashboard hinzu.

## Regionen zuerst importieren

```powershell
python -m app.importers.regions regions.json --spots-file spots.json --dry-run
python -m app.importers.regions regions.json --spots-file spots.json
```

Fehlende Mittelpunkte und Bounds werden aus den zugehörigen Spotkoordinaten
abgeleitet. Bereits vorhandene Slugs oder exakt übereinstimmende Regionsnamen
im selben Land werden übersprungen. Abweichende vorhandene Slugs können beim
Spotimport mit `--region-alias quelle=ziel` zugeordnet werden.

## Sicherer Ablauf

```powershell
python -m app.importers.spots .\imports\spots.json --dry-run
python -m app.importers.spots .\imports\spots.json
```

Mit einem abweichenden Audit-Namen:

```powershell
python -m app.importers.spots .\imports\spots.csv --actor "codex-import-2026-08"
```

Der Import ist transaktional: Sobald eine neue Zeile fehlschlägt, wird kein
neuer Spot aus dieser Datei gespeichert. Bereits vorhandene Slugs werden
übersprungen, damit dieselbe Datei gefahrlos erneut ausgeführt werden kann.
Neue Spots werden immer als Entwurf angelegt. Bilder, Klimatologie,
Vorhersagen und andere berechnete Daten gehören nicht in die Importdatei.

`--allow-duplicates` übergeht die Ähnlichkeitswarnung für bewusst nahe oder
ähnlich benannte Spots. Ein identischer vorhandener Slug wird weiterhin
übersprungen.

## Pflichtfelder

- `slug`: eindeutig, Kleinbuchstaben/Zahlen/Bindestriche
- `name`
- `region_slug`: muss bereits in der Datenbank existieren
- `lat` und `lon`; alternativ in JSON `location: [lon, lat]`
- `sports`

## Optionale Felder

- `water_type`
- `bottom_type`
- `level`
- `water_character`
- `style`
- `facing` (0–359)
- `model_pref`
- `description` (Kurzform für `editorial.description`)
- `editorial` als JSON-Objekt
- `facilities` als JSON-Objekt

Listen können in JSON echte Arrays sein. In CSV werden mehrere Werte mit `|`
getrennt oder als JSON-Array geschrieben. `editorial` und `facilities` müssen
in CSV gültiges JSON enthalten.

## JSON-Beispiel

```json
{
  "spots": [
    {
      "slug": "testregion-nordstrand",
      "name": "Nordstrand",
      "region_slug": "testregion",
      "lat": 54.41,
      "lon": 10.22,
      "sports": ["kitesurf", "wing"],
      "water_type": ["sea"],
      "bottom_type": ["sand"],
      "level": ["beginner", "advanced"],
      "water_character": ["chop"],
      "style": ["freeride"],
      "facing": 45,
      "description": "Breiter Einstieg mit viel Platz.",
      "facilities": {
        "parking": {"available": true, "note": "Direkt am Strand"}
      }
    }
  ]
}
```

## CSV-Beispiel

```csv
slug,name,region_slug,lat,lon,sports,water_type,bottom_type,level,water_character,style,facing,description,facilities
testregion-nordstrand,Nordstrand,testregion,54.41,10.22,kitesurf|wing,sea,sand,beginner|advanced,chop,freeride,45,Breiter Einstieg mit viel Platz.,"{""parking"":{""available"":true}}"
```

Der Prozess beendet sich mit Exit-Code `0` bei Erfolg, `1` bei Zeilenfehlern
und `2` bei einer ungültigen oder nicht lesbaren Datei. Der JSON-Bericht auf
stdout enthält `created`, `skipped` und `errors`.
