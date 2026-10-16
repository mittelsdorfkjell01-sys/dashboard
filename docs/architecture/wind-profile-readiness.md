# Windprofil-Bereitschaft

Stand: 25. September 2026.

Dieser Bericht trennt nutzbare Windrichtungen, Forecast-Korrekturen und
Exact-Point-Evidenz. `spots.facing` bleibt vorerst ein eigenes
Empfehlungskriterium und wird nur für die bestehende Beginner-Offshore-Regel
verwendet. Es ist weder Küstennormale noch Quelle für Forecast-Korrekturen oder
nutzbare Richtungen.

## Aktueller Produktionsbefund

Die letzte read-only Prüfung ergab 46 veröffentlichte Spots, davon 32 mit
`kitesurf`. Sieben Kite-Spots besitzen `facing`, 25 nicht. `now`, `next_week`,
`season` und `region` waren leer. Der geschützte Adminpfad zeigt nun pro Spot
die konkreten Ausschlüsse je Surface und die Richtungsprovenienz; der
öffentliche Vertrag enthält diese internen Daten weiterhin nicht.

## Verbindlicher Empfehlungsvertrag

Ein Spot kann in einer Kite-Empfehlung erscheinen, wenn:

- er veröffentlicht ist und `kitesurf` anbietet,
- `facing` gesetzt ist,
- ein aktives `SpotWeatherProfile` existiert,
- belegte nutzbare Richtungen aktiv sind,
- für `now` und `next_week` eine dreistündige Tageslicht-Session im Personal
  Band existiert,
- für `season` zusätzlich eine passende aktive V3-Variante existiert.

`reviewed_at` ist kein Freigabekriterium mehr. Profilanlage und Aktivierung
benötigen keine zweite Profilfreigabe. Das historische Feld bleibt vorerst im
Schema, wird in diesem Ablauf aber weder gesetzt noch gelesen.

## Getrennte Richtungsmodelle

`SpotWeatherSector` enthält nach Migration `0070_usable_wind_directions` nur
versionierte Forecast-Korrekturen. Deren Aktivierung bleibt an WP1 gebunden.
Nutzbare Richtungen liegen separat am `SpotWeatherProfile`:

- Eingabegeometrie und Geometrieversion,
- Regelversion und Berechnungszeit,
- abgeleitete 16er-Sektoren und Fenster,
- Status und vollständige Evidenz/Fehlgründe.

Empfehlungen und V3 `direction_mode=usable` lesen ausschließlich dieses Modell.
Forecast-Serving liest weiterhin ausschließlich aktivierte Korrektursektoren.
Eine Korrektur kann daher keine Empfehlung mehr erweitern.

Die Migration klassifiziert alte Zeilen mit der exakten Markierung
`Windklimatologie V3` vor dem Löschen:

- nur aktivierte, neutrale, kanonische V1-16er-Zeilen werden übernommen,
- deaktivierte Zeilen werden als wirkungslos verworfen,
- gemischte, doppelte oder veränderte aktive Zeilen werden `ambiguous` und
  bleiben ohne aktive Richtungen,
- alle anderen Korrekturzeilen bleiben unverändert.

Vor der lokalen Migration wurde
`python scripts/usable_direction_migration.py --pretty` auf Revision 0069
ausgeführt. Ergebnis: 0 Schreibzugriffe, 0 gefundene Altprofile. Der Dry Run ist
vor jeder produktiven Migration erneut gegen das konkrete Ziel auszuführen und
zu archivieren.

## Automatische Ableitung

Regelversion `onshore-sideshore-16-v1` arbeitet mit meteorologischen
Von-Richtungen. Die Zentren der 16 Sektoren liegen bei `index × 22,5°`.
Ausgehend von jeder wasserseitigen Ufernormalen werden alle Zentren mit einer
Winkeldifferenz bis einschließlich 90° ausgewählt. 0°/360°, beide
Sideshore-Grenzen und die Vereinigung mehrerer Startbereiche sind damit
deterministisch. Belegte lokale Ausschlüsse werden anschließend entfernt.

Ein Ergebnis wird nur aktiv, wenn jeder Startbereich Folgendes enthält:

- benannte und gültige Startfläche,
- tatsächlich nutzbare Wasserfläche,
- daran anschließende Uferlinie,
- geometrisch zum Wasser zeigende Normale,
- nachvollziehbare HTTP(S)-Quelle,
- keine ungelösten lokalen Widersprüche.

Koordinate, `facing`, Spotname oder eine allgemeine Küstenlinie genügen nicht.
Seen und Spots mit mehreren Ufern werden über mehrere Startbereiche abgebildet.
Lokale Ausnahmen benötigen Grund und Quelle. Das Ergebnis beschreibt nur die
geometrische Onshore-/Sideshore-Eignung und keine allgemeine Sicherheit.

Speichern der Evidenz berechnet und aktiviert ein vollständiges Ergebnis
sofort. Es gibt keinen manuellen Freigabeschalter. Eine neue Regelversion macht
ältere automatisch berechnete Ergebnisse sofort unwirksam, bis sie über den
Admin-Endpunkt neu berechnet wurden.

## Pilotkatalog

Die zwölf `core`-Kandidaten wurden gegen den kanonischen Katalog geprüft. Nur
eine Zuordnung ist derzeit eindeutig:

| Kandidat | Status |
|---|---|
| Sankt Peter-Ording – Ording | kein eindeutiger kanonischer Treffer |
| Fehmarn – Gold | `Gold - Fehmarn`, `5ffee534-7c7a-4b2f-ad57-bd2fd3d6f1b5` |
| Steinhuder Meer – Mardorf | kein eindeutiger kanonischer Treffer |
| Walchensee – Urfeld | kein eindeutiger kanonischer Treffer |
| IJmuiden – Noordpier | `Wijk aan Zee / Noordpier` ist nicht eindeutig gleich |
| Texel – Paal 17 | kein eindeutiger kanonischer Treffer |
| Brouwersdam – Nordseeseite | `Brouwersdam` ist räumlich zu breit |
| Workum – IJsselmeer | kein eindeutiger kanonischer Treffer |
| Klitmøller | kein eindeutiger kanonischer Treffer |
| Hvide Sande – Ringkøbing-Fjord-Seite | kein eindeutiger kanonischer Treffer |
| Lynæs | kein eindeutiger kanonischer Treffer |
| Amager Strandpark | kein eindeutiger kanonischer Treffer |

Nur Fehmarn wurde in `config/weather-pilot-spots.json` mit einer ID versehen.
Auch dieser Treffer besitzt noch keine belegte Richtungsgeometrie und kein
`facing`; er ist deshalb nicht empfehlbar. Die übrigen Kandidaten werden erst
nach Anlage beziehungsweise fachlich eindeutiger Zuordnung verknüpft.

## Exact-Point-Workflow

Die beiden Workflows verwenden ausschließlich
`secrets.LIVE_WIND_POINT_DATABASE_URL`. Der Capture-Job schreibt kompakte
u/v-Bundles in `weather_exact_model_bundles` und
`weather_exact_model_points`; der Residual-Job liest diese anschließend mit
`persisted-residuals`. Der GRIB-Cache liegt joblokal unter `$RUNNER_TEMP` und
ist kein Übergabemedium.

Das Datenbankziel muss vor Aktivierung auf Alembic Head migriert sein. Der
Runtime-Login benötigt `CONNECT`, `USAGE` auf dem Anwendungsschema und nur die
für Zielauswahl/Beobachtungen nötigen `SELECT`-Rechte sowie
`SELECT/INSERT/UPDATE` auf Exact-Bundle-/Point- und Residualtabellen. Er erhält
keine DDL- oder Eigentümerrechte. Migrationen erfolgen mit einem getrennten
Owner-Zugang.

Aktivierungsreihenfolge und Grenzen:

1. Secret setzen und Datenbankzugriff/Migrationsstand prüfen.
2. Capture mit `LIVE_WIND_POINT_CAPTURE_ENABLED=true`, Tile-Limit 16 und
   Point-Batch 16 aktivieren.
3. Bundle-Identität, Modellzeiten, Stations-/Spotabdeckung und wiederholbare
   konfliktfreie Inserts prüfen.
4. Erst danach Residuals mit `LIVE_WIND_RESIDUALS_ENABLED=true` und Batch 25
   aktivieren.
5. Bei Provider-, DB- oder Abdeckungsfehlern den jeweiligen Schalter auf
   `false` setzen; bereits persistierte immutable Evidenz bleibt erhalten.

Aktueller Betriebsstatus: Das dedizierte Secret fehlt. Beide Schalter stehen
auf `false`; die letzten geplanten Runs wurden deshalb erwartungsgemäß
übersprungen. `DIRECT_DATABASE_URL` wird nicht ersatzweise verwendet. Es gibt
noch keinen realen Capture-Bundle- oder Residual-Nachweis und der Pfad ist
nicht in Betrieb genommen.

## Nächste Betriebsarbeit

1. Eindeutige kanonische Spots für die elf offenen Core-Kandidaten anlegen oder
   bestätigen.
2. `facing` für die Pilotspots redaktionell belegen.
3. Pro Startbereich die vollständige Geometrie samt Quelle im geschützten
   V3-Admin erfassen; automatische Ergebnisse und Surface-Ausschlüsse prüfen.
4. Passende V3-Läufe berechnen/aktivieren und die vier Surfaces kontrollieren.
5. Einen dedizierten, minimal berechtigten Exact-Point-Datenbankzugang
   bereitstellen und Capture vor Residuals kontrolliert aktivieren.
