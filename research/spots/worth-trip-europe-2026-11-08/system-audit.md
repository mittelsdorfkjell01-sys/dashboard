# Systemprüfung: „Eine Reise wert“-Spots Europa

Stand: 2026-11-08 (Europe/Berlin)

## Geprüfte Bestände

- Repository: aktueller Arbeitsbaum von `dashboard-main`, einschließlich der bereits vorhandenen, nicht von diesem Auftrag stammenden Änderungen.
- Lokale Datenbank: Migration `0095_best_wind_directions`, 28 Regionen, 51 Spots, 51 feldbezogene Quellenzeilen. Dies ist ausdrücklich **nicht** der Cloud-Live-Bestand.
- Öffentliche Production-API (`https://surfwinddata.com/api`): Der Regionsendpunkt liefert 30 veröffentlichte Regionen und der Spotendpunkt 46 veröffentlichte Spots. Alle 46 sichtbaren Spots sind `published`, `editorial` und `world_class`. Zwei veröffentlichte Spots referenzieren zusätzlich die im Regionsendpunkt nicht ausgegebenen Regionen `Dalmatien` (HR) und `Noord-Holland` (NL); diese dürfen bei einer Erweiterung nicht dupliziert werden.
- Admin-Production (`https://dashboardsurfwind.vercel.app/api`): Healthcheck erreichbar und mit demselben Schema-Fingerprint wie die öffentliche Production-API; `/admin/spots` antwortet ohne Sitzung mit `401`. Weder eine vorhandene Browsersitzung noch ein lokaler Admin-Schlüssel oder lokale Bootstrap-Zugangsdaten standen zur Verfügung.

Die öffentliche API reicht nur für die Prüfung gegen veröffentlichte Spots. Eine abschließende Duplikatsprüfung gegen verdeckte Entwürfe ist damit nicht möglich.

## Aktuelle Spotfelder und zulässige Werte

- Identität: `id` (automatisch), `slug`, `name`, normalisierter Name (automatisch), `region_id`, geografischer Punkt.
- Sportarten: `kitesurf`, `windsurf`, `wing`, `surf`.
- Varianten: `windsurf:fin`, `windsurf:foil`, `kitesurf:classic`, `kitesurf:foil`; Eignung `geeignet`, `eingeschraenkt`, `ungeeignet`, `unbekannt`. Es gibt keinen allgemeinen Sportwert `foil` und keine eigene Surf-Foil-Variante.
- Niveau: `beginner`, `advanced`, `expert`, `competition`.
- Wassertyp: `ocean`, `sea`, `lake`, `lagoon`.
- Untergrund: `sand`, `rock`, `reef`, `mixed`.
- Wassercharakter: `flach`, `chop`, `welle_klein`, `welle_gross`, `tiefes_wasser`.
- Stil: `freeride`, `freestyle`, `big_air`, `wave_riding`, `wavekite`.
- Einrichtungen: `parking`, `shower`, `toilet`, `changing`, `food`, `school`. Fehlender Schlüssel bedeutet unbekannt; `available: false` darf nur bei belastbarem Negativbeleg gesetzt werden.
- `camping` ist im aktuellen Schreibschema kein zulässiger Einrichtungsschlüssel, obwohl ältere veröffentlichte Datensätze ihn noch enthalten. Neu recherchierte Campingangaben müssen bis zu einer Produktentscheidung außerhalb des importierbaren Spotobjekts erhalten bleiben.
- Windrichtungen: der aktuelle lokale Arbeitsbaum unterstützt 16 meteorologische Richtungen von `N` bis `NNW`. Die öffentliche Production-Antwort enthält dieses neue Feld noch nicht; Cloud-Unterstützung ist deshalb vor Import erneut zu prüfen.
- Facing: Gradwert 0–359. Er wird nicht automatisch aus einer Karte abgeleitet.
- Herkunft: `editorial` oder `community`; für diesen Auftrag wäre `editorial` vorgesehen.
- Reiseeinstufung: `world_class`, `worth_trip`, `worth_checking_out`; für bestätigte Kandidaten ausschließlich `worth_trip`.
- Lebenszyklus: `draft`, `published`, `archived`; neue Einträge müssen `draft` bleiben.
- Inhaltsreife: `unreviewed`, `in_review`, `verified`, `review_due`, `conflict`.

## Manuell zu recherchieren

Name und Aliasnamen, exakter Einstieg, Region, Sporteignung pro Sport und Variante, Niveau, Wasser/Untergrund, Disziplinen, belegte Windrichtungen, Facing, Tide/Strömung/Gefahren, Zugang, Zonen und Regeln, Einrichtungen, saisonale Einschränkungen, Reisegrund, sachliche Beschreibung und feldbezogene Quellen.

## Automatisch oder nachgelagert erzeugt

ID und normalisierter Name werden beim Anlegen erzeugt. ERA5-Zelle, Forecast-/Wetterdaten, Klimatologie und abgeleitete Saisonwerte gehören nicht in den Forschungsimport. Sie werden durch die jeweiligen Systemprozesse erzeugt. Bilder sind kein Pflichtteil dieses Forschungsauftrags und werden ohne geklärte Rechte nicht vorbereitet.

## Quellen- und Übersetzungslücken

`spot_content_sources` kann URL, Seitentitel, Herausgeber, Prüfzeitpunkt, Notiz, Prüfstatus und einen konkreten `field_path` speichern. Der lokale Spot-Bulk-Importer wurde am 2026-11-09 so erweitert, dass er Spot und feldbezogene Quellen gemeinsam validiert und transaktional als Entwurf anlegt. Der Cloud-Adminweg ist in dieser Sitzung weiterhin nicht autorisiert; seine Bereitstellung darf nicht vorausgesetzt werden.

Spotbeschreibungen besitzen kein unterstütztes separates Feld `description_en`; nur Regionen haben `description` und `description_en`. Daher werden keine englischen Spotübersetzungen in ein untypisiertes Metadatenfeld geschrieben.

## Schreibentscheidung

Solange kein authentifizierter Zugriff auf alle Live-Spots einschließlich Entwürfen und kein autorisierter Cloud-Schreibweg verfügbar sind, werden Kandidaten ausschließlich unter `research/spots/worth-trip-europe-2026-11-08/` vorbereitet. Der lokale Quellenimport beseitigt die Formatlücke, autorisiert aber keinen Remote-Schreibvorgang. Es erfolgen keine direkten SQL-Schreibvorgänge und keine lokalen Einträge, die als Cloud-Datensätze ausgegeben werden könnten.
