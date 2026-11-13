# System- und Zugriffsprüfung

Stand: 2026-11-09 (Europe/Berlin)

## Geprüfter Zustand

- Repository: `dashboard-main` ist die kanonische Quelle. Der Arbeitsbaum war vor Beginn stark verändert; die Gegenprüfung verändert ausschließlich den neuen Ordner `research/spots/worth-trip-europe-countercheck-2026-11-09/`.
- Messkampagne: Die Europa-Windmessung läuft im Shadow-Modus bis `2026-11-21T17:00:00+00:00`; die Kampagne ist nicht beendet.
- Lokale Datenbank: lokales Docker-PostgreSQL/PostGIS, gesund und erreichbar. Kein `DATABASE_URL` war in der Sitzung gesetzt; für die reine Leseprüfung wurde ausschließlich `localhost:5432/surfwind` verwendet.
- Lokaler Bestand: 74 Spots (63 `draft`, 11 `published`), davon 23 `worth_trip` und 11 `world_class`; 68 Regionen (40 `draft`); 203 feldbezogene Quellenzeilen (170 `verified`, 0 `conflict`); 9 `spot_images`, davon 9 sichtbar und 0 providerseitig geoverifiziert.
- Cloud-Zugriff: kein autorisierter Zugriff auf die vollständige Admin-/Cloud-Spotliste. Es gibt daher keine belastbare Prüfung gegen unveröffentlichte Cloud-Entwürfe. Öffentliche Endpunkte dürfen nicht als vollständiger Bestand behandelt werden.
- Schreibstatus: keine SQL-Schreibvorgänge, keine Remote-Schreibvorgänge, keine Veröffentlichung, keine Änderung an Spot-, Regions-, Quellen- oder Mediendatensätzen.

## Relevantes Datenmodell

| Bereich | Repräsentation | Wichtige Grenzen |
|---|---|---|
| Spotidentität | `spots.slug`, `name`, `normalized_name`, `region_id`, PostGIS `location` | Eindeutigkeit pro Region; Aliasse liegen offen in `editorial.aliases` |
| Sportarten | `kitesurf`, `windsurf`, `wing`, `surf` | Kitefoil/Windfoil sind Varianten, kein allgemeiner Sport `foil` |
| Varianten | `kitesurf:classic`, `kitesurf:foil`, `windsurf:fin`, `windsurf:foil` | Fehlende Variante bedeutet `unbekannt`; keine Surf-Foil-Variante |
| Einstufung | `world_class`, `worth_trip`, `worth_checking_out` | Reiseeinstufung ist redaktionell und getrennt von Veröffentlichung/Inhaltsreife |
| Lebenszyklus | Spot: `draft`, `published`, `archived`; Inhalt: `unreviewed`, `in_review`, `verified`, `review_due`, `conflict` | Die geprüften Kandidaten sind lokale `draft`/`unreviewed`-Datensätze |
| Bedingungen | kontrollierte Arrays für Wasser, Boden, Niveau, Windrichtung, Wassercharakter und Stil; `facing` 0–359 | Windrichtung ist meteorologische Herkunftsrichtung; viele Details liegen offen in JSON |
| Einrichtungen | `parking`, `shower`, `toilet`, `changing`, `food`, `school` | `camping` ist aktuell nicht schreibbar; fehlend bedeutet unbekannt, nicht „nein“ |
| Feldquellen | `spot_content_sources` mit `field_path`, URL, Titel, Herausgeber, `checked_at`, Status und Notiz | Eine Quelle belegt nur ihr konkretes Feld; `verified` ersetzt keine Konfliktauflösung |
| Hero | `spots.image` als kanonisches JSONB-Objekt | Pflicht: URL, Quelle, Lizenz, Credit; zusätzlich Provider, Source Page, Abrufzeit, Größe und optional `geo_verified` |
| Galerie | `spot_images` mit Lizenz-/Urheber-Snapshot, Provider, Source URL, Abrufzeit, Rolle/Status und Reihenfolge | `geo_verified=false` bei allen 9 aktuellen Zeilen; redaktionelle Sichtprüfung ist keine koordinatenbasierte Bestätigung |

## Gültige kontrollierte Werte

- Niveau: `beginner`, `advanced`, `expert`, `competition`
- Wassertyp: `ocean`, `sea`, `lake`, `lagoon`
- Untergrund: `sand`, `rock`, `reef`, `mixed`
- Wassercharakter: `flach`, `chop`, `welle_klein`, `welle_gross`, `tiefes_wasser`
- Stil: `freeride`, `freestyle`, `big_air`, `wave_riding`, `wavekite`
- Wind: 16 Richtungen `N` bis `NNW`
- Varianten-Eignung: `geeignet`, `eingeschraenkt`, `ungeeignet`, `unbekannt`
- Bildstatus: `pending`, `approved`, `published_hero`, `rejected`, `removed`

## Prüfgrenzen

1. `duplicate_risk` kann lokal vollständig, in der Cloud aber nur gegen öffentlich sichtbare Datensätze beurteilt werden.
2. Pexels- und Unsplash-API-Schlüssel waren lokal nicht vorhanden. Öffentliche Suchtreffer wurden ergänzend geprüft, sind aber keine vollständige Providerabfrage.
3. Keine der aktuell gespeicherten Galeriezeilen ist providerseitig geoverifiziert. Dateiname, Kategorie oder Sichtprüfung können einen Ort plausibel machen, aber keinen exakten Einstieg beweisen.
4. Offene JSON-Felder können Zugang, Tide, Regeln und Gefahren textlich aufnehmen, erzwingen aber keine feldweise Struktur oder Aktualitätslogik.
5. `camping` ist ein bestätigter `model_gap`: recherchierbar, aber im aktuellen Facility-Schema nicht speicherbar.

