# Recherchefortschritt: Europa `worth_trip`

Stand: 2026-11-09

## Live- und Schreibstatus

- Öffentlicher Produktionsbestand geprüft: 46 veröffentlichte Spots, alle `world_class`, sowie 30 über den Regionsendpunkt ausgegebene Regionen. Spotreferenzen belegen zusätzlich die bereits vorhandenen Regionen `Dalmatien` und `Noord-Holland`.
- Die öffentliche API zeigt keine unveröffentlichten Entwürfe. Eine vollständige Live-Duplikatsprüfung ist deshalb noch nicht möglich.
- Der Cloud-Adminweg antwortet ohne autorisierte Sitzung beziehungsweise Schlüssel mit `401`.
- Der lokale Importer ist ein unterstützter Create-only-Weg für Entwürfe und legt Spot plus feldbezogene Quellen inzwischen transaktional an. Er darf weiterhin nicht für unangemeldete Remote-Schreibvorgänge verwendet werden.
- Folgerung: Es wurden keine Cloud-Datensätze geschrieben. 23 konfliktfreie Kandidaten wurden inzwischen über den unterstützten Importer als lokale, unveröffentlichte Entwürfe mit `content_status=unreviewed` angelegt. `rhodes-theologos` wurde wegen eines bereits vorhandenen lokalen Entwurfs übersprungen.

## Bestand der Recherchedateien

| Datei | Ergebnis |
|---|---|
| `system-audit.md` | Datenmodell, Taxonomie, Regionen, Live-Bestand und Importlücken geprüft |
| `batch-001.json` | 6 vorbereitete Kandidaten, 1 Kandidat ohne gesicherte Einstiegskordinate, 2 Ausschlüsse |
| `batch-002.json` | 4 vorbereitete Kandidaten; bei Neeltje Jans saisonalen Regelkonflikt ausdrücklich offengelassen |
| `batch-003.json` | 3 vorbereitete Kandidaten, 1 Ausschluss wegen aktueller Zugangs-/Infrastrukturänderung |
| `batch-004.json` | 5 vorbereitete Kandidaten, 1 World-Class-Grenzfall ausgeschlossen |
| `batch-005.json` | 6 vorbereitete Kandidaten in sechs neu angelegten lokalen Regionsentwürfen; 37 feldbezogene Quellen |
| `regions-expansion-001.json` | 40 neue Regionsentwürfe für zusätzliche europäische Küsten-, Insel- und Binnenreviere; lokal importiert, Cloud-Import ausstehend |
| `image-review-001.json` | Fünf Picker-Tabs geprüft; 18 visuell passende Wikimedia-Bilder lokal adoptiert, 6 Spots bewusst ohne Auswahl |

Insgesamt sind 24 Kandidaten fachlich vorbereitet. Ein weiterer Kandidat (Marmari – Fun2Fun) bleibt bis zur Bestätigung der exakten Einstiegskordinate blockiert. 23 neue Spotdatensätze sind ausschließlich lokal als Entwurf importiert; keiner ist in die Cloud geschrieben oder veröffentlicht.

## Bildprüfung und lokale Zuordnung

- Die Oberfläche hat fünf Tabs, aber nur vier echte Provider: Unsplash, Pexels, Wikimedia Commons und Openverse; `nearby` kombiniert standortnahe Wikimedia- und Openverse-Suchen.
- Wikimedia und Openverse waren lokal verfügbar. Unsplash und Pexels waren wegen fehlender lokaler API-Schlüssel deaktiviert.
- 18 Bilder wurden visuell geprüft und über den unterstützten Adopt-Workflow übernommen: 9 als Hero, 9 als Galerie. Der Workflow speichert Provider, Quelldatei, Lizenz, Urheber, Abrufzeitpunkt und lokale responsive Bilddateien.
- Alle 18 Treffer stammen von Wikimedia Commons. Openverse lieferte keine bessere eindeutige Auswahl als die bereits geprüften Commons-Treffer.
- Sechs Spots bleiben ohne Bild: Vrouwenpolder, Theologos, Neeltje Jans, Gwithian Towans, Xagó und Agios Ioannis / Myloi. Die vorhandenen Treffer waren ortsunsicher, zeigten nicht den eigentlichen Spot oder waren nur als Video verfügbar.
- Der Provider markiert textbasierte Wikimedia-Suchen technisch weiterhin mit `geo_verified=false`; die redaktionelle Sichtprüfung ist in `image-review-001.json` dokumentiert und ersetzt keine koordinatenbasierte Providerbestätigung.

## Vorbereitete Kandidaten

| Region | Spot | Primäre Sportzuordnung |
|---|---|---|
| Zeeland | Domburg Noordduine | Surf |
| Zeeland | Vrouwenpolder | Kitesurf |
| Naxos | Agios Georgios Lagoon | Windsurf |
| Rhodes | Theologos | Kitesurf, Windsurf, Wing |
| Sardinia | Chia – Su Giudeu | Kitesurf |
| Cornwall | Perranporth | Surf |
| Zeeland | Neeltje Jans | Kitesurf |
| Cornwall | Gwithian Towans | Surf |
| Cornwall | Sennen Cove | Surf |
| Donegal | Rossnowlagh | Surf |
| Asturias | Salinas | Surf |
| Cantabria | Valdearenas – Liencres | Surf |
| Basque Country | Bakio Beach | Surf |
| Asturias | Xagó | Surf |
| Asturias | Vega / Berbes | Surf |
| Cantabria | Los Locos | Surf |
| Basque Country | Plentzia | Surf |
| Basque Country | Karraspio | Surf |
| Algarve | Praia da Arrifana | Surf |
| Devon | Saunton Sands | Surf |
| Mayo | Carrowniskey Strand | Surf, Kitesurf, Windsurf |
| Hel Peninsula | Chałupy – Puck Bay | Kitesurf, Windsurf, Wing |
| Lefkada | Agios Ioannis / Myloi | Kitesurf, Windsurf, Wing |
| Halland | Apelviken | Surf, Kitesurf, Windsurf, Wing |

## Bewusst nicht als fertiger Entwurf übernommen

- **Marmari – Fun2Fun (Kos):** Sport- und Reisewert belegt, exakte Einstiegskordinate widersprüchlich.
- **Gruissan – Plage des Chalets (Languedoc):** wegen international herausragender Wettkampfidentität als World-Class-Grenzfall ausgeschlossen.
- **Gomati (Lemnos):** noch keine ausreichend spotgenaue, unabhängige Belegkette.
- **Barinatxe / La Salvaje (Basque Country):** Zugang und Servicegebäude befinden sich laut aktueller Meldung in einer Veränderungsphase; neuer Zustand noch nicht verifiziert.
- **Anguileiro – Tapia de Casariego (Asturias):** wegen der hervorgehobenen Weltmeisterschafts- und Pionieridentität als World-Class-Grenzfall ausgeschlossen.

## Gemeinsame Qualitätsprüfung

- 25 Kandidatenobjekte in fünf Batches; davon 24 mit Status `prepared_*` und eines mit blockierter Koordinate.
- Keine doppelten Slugs innerhalb der Recherchebatches.
- Keine ungültigen Werte in den geprüften Sport-, Wasser-, Boden-, Niveau-, Stil-, Wassercharakter- oder Windrichtungsfeldern.
- Die Kandidaten aus Batch 001–004 verwenden bereits sichtbare Live-Regionen. Batch 005 verwendet sechs über den unterstützten Region-Importer lokal angelegte Regionsentwürfe; deren Cloud-Existenz ist noch nicht hergestellt.
- Alle positiven Kandidaten verwenden die Klassifikation `worth_trip`.
- Alle vorgesehenen Lebenszyklen sind `origin=editorial`, `status=draft`, `content_status=unreviewed`.
- Die öffentliche Live-Duplikatsprüfung ist pro Kandidat dokumentiert; die Prüfung versteckter Entwürfe bleibt überall ausdrücklich `false`.
- Der lokale Import erzeugte 23 neue Entwürfe und 152 feldbezogene Quellenbelege. Theologos wurde wegen eines bestehenden lokalen Entwurfs nicht dupliziert.
- Die Bildzuordnung erzeugte 18 lizenzierte lokale Medienverwendungen; alle Spotdatensätze bleiben `draft`.

## Erforderlicher nächster operativer Schritt vor jedem Import

1. Autorisierten Lesezugriff auf die vollständige Admin-Spotliste herstellen.
2. Namen, Aliasse, Unterspots und Koordinatennähe erneut gegen veröffentlichte **und** unveröffentlichte Live-Datensätze prüfen.
3. Den erweiterten Importer mit Quellen-, Varianten-, Wind- und Aliasfeldern im autorisierten Cloud-Deployment bereitstellen.
4. Erst danach die noch konfliktfreien Kandidaten als Entwürfe importieren; keine Veröffentlichung und keine vorzeitige Verifizierung.

## Regionserweiterung

Der Nutzer hat am 2026-11-09 die Anlage fehlender Regionen ausdrücklich in den Auftrag aufgenommen. Der unterstützte Importer wurde geprüft: neue Regionen starten automatisch als `draft`, prüfen Duplikate und werden transaktional geschrieben. Ein erster Erweiterungssatz mit 40 Regionen wurde gegen `RegionCreate` validiert und anschließend über diesen Importer in die lokale PostGIS-Datenbank geschrieben.

Verifikation: 40 angefordert, 40 vorhanden, 40 `draft`, 0 `published`, 0 ohne Mittelpunkt. Ein zweiter Import legte nichts erneut an und übersprang alle 40 Regionen. Die Cloud-Persistierung ist noch nicht erfolgt, weil die Adminauthentifizierung fehlt und unveröffentlichte Live-Regionen nicht vollständig geprüft werden können. Es wurden keine direkten SQL-Schreibvorgänge oder Validierungsumgehungen verwendet.

Batch 005 nutzt erstmals sechs dieser neuen lokalen Regionen (`algarve`, `devon`, `mayo`, `hel-peninsula`, `lefkada`, `halland`). Alle sechs Spotobjekte bestehen die aktuelle `SpotCreate`-Schemavalidierung. Die Recherche ergab außerdem eine Modelllücke: `camping` ist trotz älterer Live-Daten kein zulässiges Facility-Feld im aktuellen Schreibschema; Campingangaben bleiben daher als quellenbelegte, nicht importierbare Recherchehinweise erhalten.

