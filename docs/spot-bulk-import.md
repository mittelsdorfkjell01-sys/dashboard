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

Der Import ist transaktional: Spot und feldbezogene Quellen werden gemeinsam
geschrieben. Sobald eine neue Zeile oder Quelle fehlschlägt, wird kein neuer
Spot und keine Quelle aus dieser Datei gespeichert. Bereits vorhandene Slugs werden
übersprungen, damit dieselbe Datei gefahrlos erneut ausgeführt werden kann.
Neue Spots werden immer als Entwurf angelegt. Bilder, Klimatologie,
Vorhersagen und andere berechnete Daten gehören nicht in die Importdatei.

`--allow-duplicates` übergeht die Ähnlichkeitswarnung für bewusst nahe oder
ähnlich benannte Spots. Exakte Namen oder Aliasnamen innerhalb derselben Region
und identische vorhandene Slugs werden weiterhin übersprungen. Die Prüfung
berücksichtigt alle lokalen Lebenszykluszustände, also auch Entwürfe und
archivierte Spots.

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
- `best_wind_directions` (meteorologische Richtung, aus der der Wind kommt)
- `water_character`
- `style`
- `aliases` (werden unter `editorial.aliases` gespeichert)
- `facing` (0–359)
- `model_pref`
- `description` (Kurzform für `editorial.description`)
- `editorial` als JSON-Objekt
- `facilities` als JSON-Objekt
- `variant_conditions` für die unterstützten Wind- und Kitefoil-Varianten
- `sources` mit feldbezogenen Quellenbelegen

Listen können in JSON echte Arrays sein. In CSV werden mehrere Werte mit `|`
getrennt oder als JSON-Array geschrieben. `editorial` und `facilities` müssen
in CSV gültiges JSON enthalten. `sources` ist in CSV ebenfalls eine JSON-Liste.

Jede Quelle benötigt `field_path`, `url`, `title` und einen ISO-Zeitstempel
`checked_at` mit Zeitzone. Optional sind `publisher`, `note` und
`verification_status`. Zulässige Prüfstatus sind `unreviewed`, `verified`,
`rejected` und `conflict`. Eine als `verified` importierte Quelle erhält den
angegebenen `--actor` auch als Prüfer; dieser Status darf daher nur für bereits
fachlich geprüfte Belege verwendet werden.

`camping` ist kein zulässiger Facility-Schlüssel. Camping in der Nähe und ein
Übernachtungsverbot auf dem Parkplatz sind unterschiedliche Tatsachen und
müssen bis zu einer eigenen Modellentscheidung im Recherchematerial bleiben.

## JSON-Beispiel

```json
{
  "spots": [
    {
      "spot": {
        "slug": "testregion-nordstrand",
        "name": "Nordstrand",
        "aliases": ["Nordstrand Beach"],
        "region_slug": "testregion",
        "lat": 54.41,
        "lon": 10.22,
        "sports": ["kitesurf", "wing"],
        "water_type": ["sea"],
        "bottom_type": ["sand"],
        "level": ["beginner", "advanced"],
        "best_wind_directions": ["W", "NW"],
        "water_character": ["chop"],
        "style": ["freeride"],
        "facing": 45,
        "description": "Breiter Einstieg mit viel Platz.",
        "facilities": {
          "parking": {"available": true, "note": "Direkt am Strand"}
        },
        "variant_conditions": {
          "kitesurf:foil": {
            "suitability": "eingeschraenkt",
            "usable_depth_m": 1.5
          }
        }
      },
      "sources": [
        {
          "field_path": "best_wind_directions",
          "url": "https://example.test/local-spot-guide",
          "title": "Lokaler Spotguide",
          "publisher": "Beispielverein",
          "checked_at": "2026-11-09T12:00:00+01:00",
          "verification_status": "verified",
          "note": "Belegt West und Nordwest als geeignete Windrichtungen."
        }
      ]
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
stdout enthält `created`, `skipped`, `errors` und die Zahl `source_records`.
