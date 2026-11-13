# Feldweiser Vergleich pro Spot

Stand: 2026-11-09. `Blind` verweist auf `blind-research.json`; `Bestand` auf Batch 001–005 plus lokale PostGIS-Datensätze. Die vollständigen URLs und Belegnotizen stehen in der Blinddatei beziehungsweise in den Batch-Quellenobjekten.

## Domburg Noordduine

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität/Aliasse | Benannter Strandsektor; Abgrenzung zu Badstrand/Westkapelle noch lokal zu schärfen | Aliasse enthalten auch das sehr breite `Domburg` | `confirmed_with_caveat` | Gemeinde Veere, RWS; Batch 001 | Breiten Alias `Domburg` entfernen oder nur als Suchalias mit Kollisionsschutz führen |
| Einstieg | Blind nicht exakt bestätigt | 51.5550262, 3.4712174 am Pavillon/Schule | `confirmed_with_caveat` | OSM-Punkt und Schulbezug im Batch | Einstieg redaktionell als „Pavillon/Schule“ kennzeichnen, nicht als ganzer Spot |
| Sportarten | Surf bestätigt; Wind/Kite im kommunalen Sektor möglich, aber kein eigener Eignungsnachweis | Nur `surf` | `confirmed` | Gemeinde Veere, lokale Schule | Kein Sport ergänzen ohne spotgenaue Eignungsprüfung |
| Bedingungen/Niveau | Exponierter Beachbreak; bei Energie eher fortgeschritten | `beginner`, `advanced`, SE, Facing 315 | `confirmed_with_caveat` | Surfline sekundär; kommunale Regeln | Beginner ausdrücklich auf kleine Bedingungen/Schulbetrieb begrenzen |
| Regeln/Gefahren | Abschnittsbezogenes Juli-/August-Verbot; Strömung/Buhnen | Entsprechend beschrieben | `confirmed` | Veere APV 2026 | Aktuelle Beschilderung als maßgeblich nennen |
| Reisewert | Domburg ist relevant, aber Eigenständigkeit dieses Sektors noch nicht ausreichend | `worth_trip` | `open` | Blindquellen + Batch | Vor Veröffentlichung eigenständigen Reisegrund gegenüber Domburg-Gesamtspot belegen |
| Bild | Exakte Strandnähe, aber kein Einstieg; Galerie geeignet | Galerie `Domburg strand` | `confirmed_with_caveat` | Commons 52363783 | Galerie behalten, nicht zum Hero/Einstiegsbeleg machen |

Abschlussurteil: `hold_for_more_research`

## Vrouwenpolder

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität/Aliasse | Breezand/Nordsee-Kitezone und Veerse-Meer-Windsurfbereich sind getrennte Einstiege | Aliasse vermischen Veerse Dam/Breezand; Datensatz beschreibt Kitezone | `confirmed_with_caveat` | NKV, Windsurfschool Zeeland | Namen/Koordinate ausdrücklich auf Nordsee-Kitezone begrenzen oder Unterspots modellieren |
| Einstieg | Mehrere mögliche Einstiege | 51.5878683, 3.6312758, erster Fußgängersteg | `confirmed_with_caveat` | NKV, Batch 001 | Einstieg im Namen/Entry-Text fixieren; Veerse Meer nicht über dieselbe Koordinate repräsentieren |
| Sportarten | Kite bestätigt; Surf sowie Wind/Wing in der weiteren Vrouwenpolder-Landschaft | Nur `kitesurf` | `confirmed` | NKV, Zeeland.com, lokale Windsurfschule | Für den Nordsee-Kitedatensatz keine pauschale Mehrsport-Erweiterung |
| Bedingungen | Tideabhängige Lagune, W/NW/N/NE/E, Sand, Beginner | Entspricht | `confirmed` | NKV | Unverändert; „deep“ vs flache Lagune als Zustands-/Tidekontext erklären |
| Regeln/Einrichtungen | Markierte Zone, Schilder/Bojen, bezahltes Parken, Schule, WC/Dusche/Essen | Entspricht | `confirmed` | NKV, Gemeinde Veere | Saison-/Bojenformulierung regelmäßig prüfen |
| Reisewert | Zwei komplementäre Wasserwelten und starke Infrastruktur | `worth_trip` | `confirmed_with_caveat` | Zeeland.com, NKV | Reisewert auf Revierkontext stützen, ohne beide Einstiege zu einem Spot zu verschmelzen |
| Bild | Exakter Breezand-Unsplash-Treffer unabhängig gefunden | Kein Bild | `open` | Unsplash/Fab Lentz | Original/API-Attribution und Auflösung prüfen, dann übernehmen |

Abschlussurteil: `accept_after_correction`

## Agios Georgios Lagoon, Naxos

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Windsurf-Lagune am südlichen Agios-Georgios-Strand | Entsprechend | `confirmed` | Naxos municipality tourism | Keine |
| Einstieg | Zugang gegenüber Naxos Camping, exakter Punkt nicht amtlich angegeben | 37.0893385, 25.3701413 | `confirmed_with_caveat` | Offizielle Schul-/Tourismusseite | Punkt als Schul-/Lagunen-Einstieg notieren |
| Sportarten | Windsurf bestätigt; Kite/Kitefoil ausdrücklich verboten | Nur `windsurf`; Verbot im Hinweis | `confirmed` | Naxos municipality | Verbot als harte lokale Regel erhalten |
| Bedingungen | Flach, seicht, Sand, beginnerfreundlich | Lagune, Sand, `flach`, Beginner, N | `confirmed_with_caveat` | Naxos tourism | N nur behalten, wenn konkrete Quelle Windherkunft belegt |
| Einrichtungen | Schule/Verleih, Parking, Bus; Gastronomie am Strand | Parking/Food/School | `confirmed` | Naxos tourism | Bus/Entfernung nur im Freitext, sofern gewünscht |
| Reisewert | Reise wert als Windsurf-Lernrevier im Naxos-Gesamtrevier | `worth_trip` | `confirmed_with_caveat` | Offizielle Naxos-Seiten | Kitesurf-Assoziation in allen Oberflächen ausschließen |
| Bild | Gespeichertes Foto zeigt Stadtstrand, nicht Lagune | Galerie `City beach Agios Georgios` | `image_mismatch` | Commons 37293267 | Entfernen oder als Ortsbild statt Spotbild führen |

Abschlussurteil: `accept_after_correction`

## Theologos, Rhodes

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Theologos/Tholos; getrennte Kite- und Windsurfstationsbereiche | Lokaler Altentwurf heißt `Theologos (Fanes)`; Batch will `Theologos` | `duplicate_risk` | Visit Rhodes, Betreiber | Bestehenden Datensatz aktualisieren/mergen, keinen zweiten anlegen; `Fanes` entfernen, falls nicht als eigener Ort belegt |
| Einstieg | Betreiberstrand ca. 5 km südlich Flughafen | Altentwurf 36.32, 28.07; Batch 36.3839093, 28.0279257 | `coordinate_risk` | Betreiber, Batch | Altkoordinate nicht verwenden; Batchpunkt vor Ort/über Stationskarte bestätigen |
| Sportarten | Kite, Windsurf, Wing bestätigt; Foil nur Betreiberclaim | Altentwurf nur Kite/Windsurf; Batch ergänzt Wing | `confirmed_with_caveat` | Surf & Kite Theologos | Wing ergänzen; Foil nicht positiv modellieren ohne Detailbeleg |
| Bedingungen | SW side-onshore, Chop/kleine Windwelle, Beginner/Advanced | Alt: W/NW, Beginner; Batch: SW, Beginner/Advanced | `contradicted` | Betreiber vs Altquelle Hanglos | Altwerte ersetzen; Level sport-/stationsbezogen beschreiben |
| Einrichtungen/Regeln | Schule, Verleih, Rescue, Beachbar; keine Behörden-Zonenquelle | Batch entsprechend | `confirmed_with_caveat` | Betreiber, Visit Rhodes | Betreiberangaben als solche kennzeichnen; lokale Zonen offen lassen |
| Reisewert | Etabliertes Multi-Wind-Reiseziel | Batch `worth_trip`; Altentwurf unklassifiziert | `confirmed` | Betreiber + Tourismusseite | Bestehenden Datensatz nach Korrektur klassifizieren |
| Bild | Altentwurf hat Seed-Platzhalter; kein exaktes Strandbild gefunden | Platzhalter, in Review als bildlos geführt | `image_mismatch` | Lokale DB, externe Suche | Veröffentlichung mit Platzhalter blockieren |

Abschlussurteil: `accept_after_correction`

## Chia – Su Giudeu

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Su Giudeu ist ein Strand im Chia-Revier, nicht Synonym für alle Nachbarbuchten | Aliasse `Chia`, `Baia di Chia` sehr breit | `confirmed_with_caveat` | Sardinia region, lokale Guides | Breite Aliasse nur als Revierbezug, nicht Identitätsgleichheit verwenden |
| Einstieg | Strandpunkt plausibel; legaler Sommerstart ungeklärt/Bootslösung | 38.8821866, 8.8642382 | `confirmed_with_caveat` | OSM, regionale Regeln, Betreiberquellen | Eintrittspunkt und saisonal zulässigen Start separat dokumentieren |
| Sportarten | Kite belegt, primär Wave; andere Sportarten offen | `kitesurf` | `confirmed` | Sardegna Turismo, lokale Schule | Keine Erweiterung |
| Wind/Bedingungen | Unabhängige Quellenlage zu Richtungen widersprüchlich; starke Regel-/Strömungsrisiken | E/SE/NE/SW; Advanced | `unsupported` | Kite House vs Gegenrecherche | Windrichtungen bis zu einer zweiten spotgenauen Quelle als offen markieren |
| Regeln | Direkter Start im Sommer eingeschränkt; Primärquelle für genaue Zeitspanne/Zonen fehlt | Mitte Juni–Mitte September als gesichert formuliert | `confirmed_with_caveat` | Regionale Strandregeln + Betreiber | Zeitraum nicht als amtlich gesichert ausgeben; 2026-Verordnung/Capitaneria direkt belegen |
| Reisewert | Landschaftlich stark, aber Zugang macht pauschale Empfehlung riskant | `worth_trip` | `open` | Regionale Regeln, Sekundärguide | Bis Primärquellenklärung halten |
| Bild | Zeigt Su Giudeu/Campana aus Distanz, nicht Einstieg | Hero | `confirmed_with_caveat` | Commons 54881424 | Als Landschafts-Hero okay; nicht als Launch-/Geobeweis |

Abschlussurteil: `hold_for_more_research`

## Perranporth

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität/Aliasse | Perranporth Beach; Perran Sands ist angrenzender Strandteil, nicht sauberer Alias | Aliasliste enthält `Perran Sands` | `confirmed_with_caveat` | RNLI, Visit Cornwall | `Perran Sands` als Nachbar/Subspot, nicht Alias führen |
| Einstieg | Hauptzugang/Surf School plausibel | 50.3471122, -5.1540792 | `confirmed` | RNLI, Geocode | Keine |
| Sportarten | Surf bestätigt; Wind-/Kitesport nicht ausreichend belegt | Nur Surf | `confirmed` | RNLI, Visit Cornwall | Keine |
| Bedingungen/Niveau | Beachbreak für Beginner bis Advanced je nach Tag | Nur Beginner | `confirmed_with_caveat` | RNLI, Schulen | `advanced` ergänzen oder Niveau bedingungsabhängig erläutern |
| Einrichtungen/Sicherheit | Parkplatz, Cafés, Schulen, RNLI-Flaggen | Weitgehend entsprechend | `confirmed` | RNLI, Visit Cornwall | Keine wesentliche Änderung |
| Reisewert | Klarer Cornwall-Surftrip | `worth_trip` | `confirmed` | Visit Cornwall | Keine |
| Bild | Exakter Hauptstrand, Galeriegröße | Galerie | `confirmed` | Commons 133072837 | Behalten |

Abschlussurteil: `accept_after_correction`

## Neeltje Jans

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Mehrere Ufer; Roompotsluis-Sektor muss explizit benannt werden | `Neeltje Jans` mit Alias Roompotsluis | `confirmed_with_caveat` | Veere APV, NKV | Anzeigename oder Entry-Text auf Sektor begrenzen |
| Einstieg | Geocoder zeigt anderen Strand; exakter Start nicht unabhängig bestätigt | 51.6242417, 3.6805594, langer Fußweg ab Parkplatz | `coordinate_risk` | NKV-Spotkarte, Batch | Vor Ort/amtliche Karte bestätigen; nicht nur Kartenpin übernehmen |
| Sportarten | Kite, Wind und Surf im erlaubten Strandsektor; Eignung je Sport offen | Nur Kite | `confirmed_with_caveat` | Veere APV/RWS | Nur Kite belassen, bis Wind/Surf-Eignung spotgenau belegt ist |
| Bedingungen/Niveau | Exponiert, tide-/strömungsrelevant, eher Advanced | Advanced, N/NW/W/SW, flach/chop | `confirmed_with_caveat` | NKV | Strömung/Tide konkretisieren; `flach` nicht pauschal |
| Regeln | Quellen zur saisonalen Freigabe nicht widerspruchsfrei | Safety-Quelle `unreviewed`; Text nennt Konflikt | `open` | RWS/NKV/Veere | Vor Veröffentlichung aktuelle Primärquelle und Beschilderung abgleichen |
| Reisewert | Delta-Works-Landschaft und anspruchsvolle Bedingungen | `worth_trip` | `confirmed_with_caveat` | Natuurmonumenten, Zeeland | Erst nach Regel-/Koordinatenklärung akzeptieren |
| Bild | Nur Insel-/Straßenbilder, kein Start | Kein Bild | `open` | Commons/Unsplash-Suche | Bildlos lassen |

Abschlussurteil: `hold_for_more_research`

## Gwithian Towans

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Eigenständiger Zugang im zusammenhängenden Towans-Strand | Entsprechend | `confirmed` | South West Water, lokale Towans-Seite | Keine |
| Einstieg | Geocode nur Access-/Bus-Proxy | 50.2217795, -5.3945487 am Hauptparkplatz | `confirmed_with_caveat` | Batch, lokale Karte | Entry als Hauptparkplatz/Zugang kennzeichnen |
| Sportarten | Surf sicher; Kite/Windsurf zoniert und historisch belegt | Nur Surf | `confirmed` | WaterFit, Zonenflyer | Keine Sporterweiterung ohne aktuelle Zonenbestätigung |
| Bedingungen/Niveau | Exponiert, starke Rips, breites Niveau | Beginner/Advanced, keine Water Character | `confirmed_with_caveat` | WaterFit, Visit Cornwall | Rippströmungen im Safety-Text ergänzen |
| Regeln/Einrichtungen | Saisonale Aktivitätszonen; Dünenregeln; Parken/Cafés | Allgemeiner Lifeguard-Hinweis, Facilities vorhanden | `confirmed_with_caveat` | Towans code, historischer Zonenflyer | Aktuelle Zonenquelle suchen; historischen Flyer kennzeichnen |
| Reisewert | Beständiger Surf plus St-Ives-Bay-Landschaft | `worth_trip` | `confirmed` | lokale/regionale Quellen | Keine |
| Bild | Exakte Commons-Zugangsbilder auffindbar | Kein Bild | `open` | Commons | Vollauflösung/Repräsentativität prüfen, eher Galerie |

Abschlussurteil: `accept_after_correction`

## Sennen Cove

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Sennen/Whitesands; Gwynver bleibt Nachbar | Aliasse korrekt genug | `confirmed` | Visit Cornwall, Sennen Beach | Keine |
| Einstieg | Hauptstrandpunkt; Flaggen verschieben Surfzone | 50.0787408, -5.6970943 | `confirmed` | Sennen Beach/Visit Cornwall | Keine |
| Sportarten | Surf | Surf | `confirmed` | Visit Cornwall | Keine |
| Bedingungen | Atlantik-Beachbreak, Beginner bis Advanced; E als Offshore plausibel | Entspricht | `confirmed_with_caveat` | Tourism/School | Windrichtung nur behalten, wenn Spotguide-Feldquelle aktuell bleibt |
| Zugang/Sicherheit | Mehrere Parkplätze, Bus, Schule, Lifeguards, starke Wellen/Strömungen | Entspricht | `confirmed` | Visit Cornwall, RNLI-Kontext | Keine |
| Reisewert | Eigenständiges ikonisches Cornwall-Reiseziel | `worth_trip` | `confirmed` | Visit Cornwall | Keine |
| Bild | Exakte Bucht, Hero-tauglich | Hero | `confirmed_with_caveat` | Commons 158690708 | Behalten; nicht als exakter Einstieg ausgeben |

Abschlussurteil: `accept_as_worth_trip`

## Rossnowlagh

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Rossnowlagh/Ros Neamhlach; großer Strand mit mehreren Zugängen | Aliasliste zusätzlich Belalt/Belall | `confirmed_with_caveat` | Donegal tourism | Belalt/Belall nur behalten, wenn amtlich als gleicher Strand bestätigt |
| Einstieg | Dorfkoordinate ungeeignet; gespeicherter Punkt liegt am Strand | 54.5578, -8.2073 | `confirmed` | Batch/Commons-Geokoordinate | Keine |
| Sportarten | Surf und Kite bestätigt; Wind/Wing offen | Nur Surf | `confirmed` | Donegal tourism, Discover Ireland | Kite nur ergänzen, wenn Datensatz den Kitebereich sicher abdeckt; sonst Surf fokussieren |
| Bedingungen/Niveau | Sand-Beachbreak, Beginner bis Advanced, Winter deutlich größer | Entspricht | `confirmed` | Donegal tourism | Keine |
| Einrichtungen/Sicherheit | Schulen, Sommerlifeguards, Parken; Fahrzeug-/Campingpraxis nicht als Recht ableiten | Entspricht vorsichtig | `confirmed` | Donegal tourism | Keine |
| Reisewert | Etablierter irischer Surfstrand | `worth_trip` | `confirmed` | Donegal tourism | Keine |
| Bild | Exakte Geokoordinate, rechtlich nutzbar | Hero | `confirmed` | Commons 55989699 | Behalten |

Abschlussurteil: `accept_as_worth_trip`

## Salinas, Asturias

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Salinas in Castrillón; Namenskonflikt mit Salinas/Luarca | Name `Salinas`, Aliasse klären Castrillón | `confirmed_with_caveat` | Turismo Asturias | Öffentlichen Namen `Salinas, Asturias` oder `Playa de Salinas (Castrillón)` verwenden |
| Einstieg | Offizielle Strandkoordinate 43.577406, -5.962143 | 43.57874, -5.953169 an Schul-/Espartalbereich | `confirmed_with_caveat` | Turismo Asturias, Batch | Gespeicherten Punkt als Schule/östlichen Einstieg benennen, nicht Strandzentrum |
| Sportarten | Surf; Wind/Kite nur außerhalb Badezonen rechtlich möglich, Eignung offen | Nur Surf | `confirmed` | Turismo Asturias, Castrillón ordinance | Keine Erweiterung |
| Bedingungen | Sand-Beachbreak, moderater bis anspruchsvoller Swell | Beginner/Advanced, SE, Facing 315 | `confirmed_with_caveat` | Turismo/Spotguide | Wind/Facing mit zweiter Quelle absichern |
| Zugang/Einrichtungen | Sehr gut ausgestattet, Lifeguards Juni–September | Entspricht | `confirmed` | Turismo Asturias | Keine |
| Reisewert | Starke Surfkultur und Infrastruktur | `worth_trip` | `confirmed` | Turismo Asturias | Keine |
| Bild | Eindeutig Salinas-Castrillón/La Peñona | Hero | `confirmed` | Commons 50484558 | Behalten |

Abschlussurteil: `accept_after_correction`

## Valdearenas – Liencres

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Valdearenas/Liencres; Canallave Nachbar | Entspricht | `confirmed` | Schutzgebietsinventar | Keine |
| Einstieg | Hauptzugang/Access Road | 43.4499, -3.9624 | `confirmed_with_caveat` | Batch, Geocode | Entry als Hauptparkplatz/-zugang benennen |
| Sportarten | Surf sicher; Wind/Kite sekundär | Nur Surf | `confirmed` | Beach inventory | Keine |
| Facing/Wind | Strand öffnet ungefähr NW; beste Surf-Winde S–E plausibel | Facing `0`, S/SE/E | `contradicted` | Geografie/Beach orientation | Facing auf ca. 315 prüfen/korrigieren; 0 nicht veröffentlichen |
| Niveau/Gefahren | Starke Strömungen/Wirbel; Beginner nur kleine Tage/Schule | Beginner/Advanced mit Warnung | `confirmed_with_caveat` | Beach inventory | Beginner bedingungsgebunden formulieren |
| Reisewert | Schutzdünen + ernsthafter Surf | `worth_trip` | `confirmed` | Naturinventar, Strandquelle | Keine |
| Bild | Exakter Strandname, aber felsiger Abschnitt | Hero | `confirmed_with_caveat` | Commons 40073059 | Hero vertretbar; nicht als Hauptzugang darstellen |

Abschlussurteil: `accept_after_correction`

## Bakio Beach

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Ein Strand mit El Callejón, Peñas Rojas und Westpeak | Entspricht | `confirmed` | Basque Government Tourism | Peaks als Unterbereiche erklären |
| Einstieg | Strandpunkt 43.431161, -2.803288 | 43.4305, -2.8087 am Westteil | `coordinate_risk` | Offizielle Tourismuskarte/OSM | Entscheiden, ob Datensatz Gesamtstrand oder Westpeak repräsentiert; Punkt entsprechend benennen |
| Sportarten | Surf | Surf | `confirmed` | Basque tourism | Keine |
| Bedingungen | Sand/Fels, alle Level, ganzjährig | Mixed, Beginner/Advanced, S/SE/NE | `confirmed_with_caveat` | Basque tourism | Windrichtungen bis zu spotgenauem Beleg offen lassen; Expert bei großen Tagen erwägen |
| Einrichtungen | Schulen, Parkplatz, WC, Dusche; Camping verboten | Camping nicht abbildbar | `model_gap` | Basque tourism | Campingverbot außerhalb Facilities dokumentieren |
| Reisewert | Vielseitige Peaks und Basque-Coast-Kontext | `worth_trip` | `confirmed` | Basque tourism | Keine |
| Bild | Exakte Geokoordinate, groß genug | Hero | `confirmed` | Commons 51205238 | Behalten |

Abschlussurteil: `accept_after_correction`

## Xagó

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Playa de Xagó/Xagón | Entspricht | `confirmed` | Turismo Gozón | Keine |
| Einstieg | Beach centroid | 43.603176, -5.920246 | `confirmed_with_caveat` | Turismo Gozón/OSM | Hauptparkplatz-/Zugangspunkt benennen |
| Sportarten | Surf bestätigt; andere offen | Surf | `confirmed` | Turismo Gozón | Keine |
| Bedingungen/Niveau | Sehr exponiert, starke Wellen, NE-Winde; eher Advanced/Expert | Beginner/Advanced, `welle_gross` | `confirmed_with_caveat` | Turismo Gozón, Schule | Beginner nur bei kleinen Tagen/Unterricht; Expert ergänzen oder offen lassen |
| Einrichtungen/Schutz | Parking, WC, Dusche, Essen; Dünen schützen | Entspricht | `confirmed` | Turismo Gozón | Keine |
| Reisewert | Große natürliche Surfkulisse | `worth_trip` | `confirmed` | regionale Quellen | Keine |
| Bild | Kein belastbarer repräsentativer Treffer | Kein Bild | `open` | Gegenrecherche | Bildlos lassen |

Abschlussurteil: `accept_after_correction`

## Vega / Berbes

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Playa de Vega; Berbes ist Orts-/Gebietskontext | Entspricht weitgehend | `confirmed_with_caveat` | Turismo Asturias | Öffentlichen Namen auf `Playa de Vega (Berbes)` vereinheitlichen |
| Einstieg | Beach centroid 43.480175, -5.140522 | 43.479964, -5.138889 | `confirmed` | Turismo Asturias/Commons | Keine |
| Sportarten | Surf | Surf | `confirmed` | Turismo Asturias | Keine |
| Bedingungen | Offener, kräftiger Beachbreak; allgemeines Level offen | Level leer, SSE, `welle_gross` | `confirmed_with_caveat` | Turismo + lokaler Guide | SSE nur mit zweiter Quelle als gesichert markieren |
| Schutz/Zugang | Naturdenkmal; aktuelle Sportzonen dünn belegt | Allgemeiner Schutz-/Gefahrenhinweis | `confirmed_with_caveat` | Turismo, Schutzstatus sekundär | Primärdekret/aktuelle Regeln vor Veröffentlichung belegen |
| Reisewert | Landschaft stark, eigenständiger Sportwert noch dünn belegt | `worth_trip` | `open` | Quellenlage dünn | Weiter recherchieren |
| Bild | Exakte Geokoordinate und Beschreibung | Galerie | `confirmed` | Commons 7733002 | Behalten |

Abschlussurteil: `hold_for_more_research`

## Los Locos

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Eigenständiger Suances-Surfstrand | Entspricht | `confirmed` | Ayuntamiento/Turismo Suances | Keine |
| Einstieg | Offizieller GIS-Punkt 43.44127, -4.04551 | Entspricht | `confirmed` | kommunale/GIS-Quelle | Keine |
| Sportarten | Surf | Surf | `confirmed` | kommunale Quellen | Keine |
| Bedingungen | Starke Wellen, Wind, fortgeschrittene/expertentauglich; Level offen im Bestand | Mixed, `welle_gross`, Level leer | `confirmed` | Suances | Optional niveauabhängige Erklärung ergänzen |
| Zugang | Steile Treppen; temporäre Sperrung einer Nebenstiege im Juli 2026 | Safety nennt aktuelle Sperrungen allgemein | `outdated` | kommunale Meldung 2026 | Nebenstiege nicht als fortdauernd gesperrt darstellen; Hauptzugang nennen |
| Reisewert/Klasse | Surf Natural Reserve, tief etablierte Szene und nationale/internationale Reputation | `worth_trip` | `contradicted` | Turismo Suances, offizielles Panel | Als World-Class-Grenzfall aus worth_trip-Liste entfernen und gesondert bewerten |
| Bild | Ort exakt, Motiv wenig repräsentativ | Hero | `confirmed_with_caveat` | Commons 121574968 | Zur Galerie herabstufen, besseren Hero wählen |

Abschlussurteil: `reject_as_world_class`

## Plentzia

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Geschützte Bucht/Ästuarwelle, angrenzend Gorliz | Alias `Plentzia–Gorliz` verwischt Grenze | `confirmed_with_caveat` | Visit Plentzia, Basque tourism | Gorliz als Nachbar, nicht Alias führen |
| Einstieg | Beach centroid | 43.4112, -2.9459 | `confirmed` | lokale Tourismusseite | Keine |
| Sportarten | Beginner-Surf, Windsurf/Kajak; Kite offen | Nur Surf | `confirmed` | Basque tourism | Surf-Fokus okay |
| Bedingungen | Sehr ruhig, kleine tide-/swellabhängige Welle, Beginner | Beginner, kleine Welle, W/SW | `confirmed_with_caveat` | Visit Plentzia | Windrichtungen nicht als Kernqualität ausgeben |
| Einrichtungen | Sehr gut erschlossen | Entspricht | `confirmed` | Visit Plentzia | Keine |
| Reisewert | Familien-/Anfänger- und Ausweichspot, kein eigenständiger Surftrip | `worth_trip` | `contradicted` | Offizielle Beschreibungen | Auf `worth_checking_out` oder Region-Unterspot abwerten |
| Bild | Exakt, aber Strand-/Drachenbild | Galerie | `confirmed` | Commons 2833150 | Galerie behalten |

Abschlussurteil: `reject_insufficient_trip_value`

## Karraspio

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Karraspio Beach, Mendexa; Garraitz prägt die Welle | Entspricht | `confirmed` | Basque tourism | Keine |
| Einstieg | Beach centroid | 43.364215, -2.493913 | `confirmed` | Basque tourism/OSM | Keine |
| Sportarten | Beginner-Surf, Segeln; kein starker Wind-/Kitebeleg | Surf | `confirmed` | Basque tourism | Keine |
| Bedingungen | Braucht großen Swell, stark tideabhängig, Beginner | Beginner, kleine Welle, S | `confirmed_with_caveat` | Basque tourism | S-Wind nur mit Spotbeleg behalten |
| Einrichtungen | Voll ausgestattet; Camping verboten | Camping nicht abbildbar | `model_gap` | Basque tourism | Verbot außerhalb Facilities erfassen |
| Reisewert | Attraktiver Anfänger-/Lekeitio-Unterspot, kein eigenständiges Reiseziel | `worth_trip` | `contradicted` | Offizielle Quelle | Auf `worth_checking_out`/Unterspot abwerten |
| Bild | Zeigt `Karraspio Txiki`/Mündungsbereich, nicht Hauptstrand | Galerie | `image_mismatch` | Commons 81131229 | Entfernen oder korrekt als Unterspotbild benennen |

Abschlussurteil: `reject_insufficient_trip_value`

## Praia da Arrifana

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Arrifana Beach, Aljezur | Entspricht | `confirmed` | Visit Portugal, Blue Flag | Keine |
| Einstieg | Offizielle Koordinate 37.29442, -8.86601 | Entspricht | `confirmed` | Blue Flag profile | Keine |
| Sportarten | Surf/Bodyboard; Wind-/Kite nicht belegt | Surf | `confirmed` | Visit Portugal | Keine |
| Bedingungen | Geschützte Atlantikbucht, mesotidal, Sand/Felsränder | Sand, Level/Wind offen | `confirmed_with_caveat` | Beach profile | Fels-/Klippenkontext im Safety-Text ergänzen |
| Regeln/Gefahren | Naturpark/Natura 2000, Klippensturzrisiko, Badezonen, steiler Zugang | Nur allgemeine Atlantik-/Parkwarnung | `confirmed_with_caveat` | APA, Blue Flag | Klippenrisiko und Wegepflicht vor Veröffentlichung ergänzen |
| Reisewert | Ganzjähriger, landschaftlich markanter Surfspot | `worth_trip` | `confirmed` | Visit Portugal | Keine |
| Bild | Exakte Geokoordinate, ausreichend groß | Galerie | `confirmed` | Commons 29904187 | Behalten; Hero nach Crop-Prüfung möglich |

Abschlussurteil: `accept_after_correction`

## Saunton Sands

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Langer Strand/Braunton-Burrows-Kontext | Entspricht | `confirmed` | Betreiber, Biosphere-Kontext | Keine |
| Einstieg | Hauptzugang/Nordende plausibel | 51.11817, -4.22057 | `confirmed` | Betreiber/Commons | Keine |
| Sportarten | Surf sicher; Kite nur sekundär | Nur Surf | `confirmed` | Betreiber | Keine |
| Bedingungen | Longboard-/Beachbreak, Beginner–Advanced | Entspricht | `confirmed` | Betreiber/regionale Quellen | Keine |
| Zugang/Sicherheit | Nicht lifeguarded; Paid parking; kein Overnight/Camping; Schutzdünen | Entspricht | `confirmed` | Betreiber | Keine |
| Reisewert | Ikonischer North-Devon-Strand | `worth_trip` | `confirmed` | Betreiber | Keine |
| Bild | Exakte Geokoordinate, groß, repräsentativ | Hero | `confirmed` | Commons 36392739 | Behalten |

Abschlussurteil: `accept_as_worth_trip`

## Carrowniskey Strand

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität/Aliasse | Carrowniskey/Carrownisky/Carrowinskey | Zwei Schreibvarianten, `Carrowinskey` fehlt | `confirmed_with_caveat` | Discover Ireland, GSI | Häufige dritte Schreibweise als Suchalias prüfen |
| Einstieg | 53.7225, -9.9056 nur sekundär als Parkplatz verifiziert | Entspricht | `confirmed_with_caveat` | IrishBeaches, GSI | Primärquelle/Ortstermin vor `verified` |
| Sportarten | Surf bestätigt; Kite/Wind/Wing nur schwach/regionsweit belegt | Surf, Kite, Windsurf | `unsupported` | Discover Ireland vs alte Mayo-Strategie | Kite/Windsurf entfernen oder spotgenau durch aktuelle Quelle belegen |
| Bedingungen/Niveau | Exponierter Atlantic Beachbreak, eher Intermediate/Advanced | Level/Wind/Water Character offen | `confirmed_with_caveat` | Discover Ireland, Sekundärguide | Level weiter offen lassen; Exposition klar benennen |
| Einrichtungen | Schule/Free parking; Toilette als nicht vorhanden sekundär gemeldet | Parking/School | `confirmed_with_caveat` | Surf Mayo, IrishBeaches | Negative Facility nur bei Primärbeleg speichern |
| Reisewert | Surftrip plausibel; Mehrsport-Reisegrund überhöht | `worth_trip` | `confirmed_with_caveat` | Discover Ireland | Reisewert auf Surf und Landschaft begrenzen |
| Bild | Commons-Dateikoordinate liegt rund 70 km entfernt | Galerie | `image_mismatch` | Commons 74050303 | Sofort aus Zuordnung entfernen |

Abschlussurteil: `accept_after_correction`

## Chałupy – Puck Bay

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Mehrere Camps/Launches im Chałupy-Korridor | Ein Punkt an Mole/Boulevard, breite Aliasse | `confirmed_with_caveat` | Puck Police, Schutzgebietsunterlagen | Launch/Camp exakt benennen oder als Revier statt Einzelspot modellieren |
| Einstieg | Kein einzelner universeller Einstieg | 54.759967, 18.504783 an Mole | `coordinate_risk` | Commons/Batch | Punkt als Mole/Boulevard kennzeichnen, nicht für alle Schulen/Camps |
| Sportarten | Kite, Windsurf, Wing bestätigt | Entspricht | `confirmed` | Puck Police | Foil offen lassen, Tiefe/Hindernisse fehlen |
| Bedingungen | Flache Puck Bay, Sand, Beginner–Advanced | Entspricht, Wind offen | `confirmed` | Behörden-/lokale Quellen | Foiltiefe und Schilf/Flachstellen separat recherchieren |
| Schutz/Regeln | Natura 2000, Landschaftspark, gemeinsame Nutzung; campabhängige Regeln | Allgemein erwähnt | `confirmed_with_caveat` | Gov.pl/RDOS, maritime Planung | Aktuelle Schutz-/Launchregeln je Einstieg ergänzen |
| Reisewert/Klasse | International etabliertes Wind-Sport-Revier mit dichter Infrastruktur | `worth_trip` | `contradicted` | Behörden + internationale Identität | Als World-Class-Grenzfall aus worth_trip entfernen |
| Bild | Ort exakt, zeigt Boulevard/Bucht statt Wassersport-Einstieg | Hero | `confirmed_with_caveat` | Commons 134395968 | Zur Galerie herabstufen |

Abschlussurteil: `reject_as_world_class`

## Agios Ioannis / Myloi

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Myloi ist laut offizieller Quelle registrierter Kite-Strand neben Agios Ioannis; nicht vollständig identisch | Ein kombinierter Datensatz mit fünf Aliasnamen | `confirmed_with_caveat` | Lefkada official tourism | Unterspots trennen oder klare räumliche Definition im Namen/Entry hinterlegen |
| Einstieg | Agios-Ioannis-Punkt, Myloi-Grenze offen | 38.8419, 20.6825 | `coordinate_risk` | Offizielle Tourismusseite + Geocode | Exakten Myloi-Start amtlich/lokal bestätigen |
| Sportarten | Kite sicher; Wind bestätigt sekundär; Wing offen | Kite, Windsurf, Wing | `unsupported` | Lefkada official + Sekundärquellen | Wing und sportübergreifende Eignung nur mit spotgenauer Quelle behalten |
| Bedingungen/Niveau | Thermisch SW–NW/N, Chop/kleine Welle; Felsplatten/Shorebreak; eher Advanced am offenen Strand | Beginner/Advanced, SW/W/NW, Mixed | `confirmed_with_caveat` | Offiziell + Sekundärguide | Beginner nur für Schul-/markierte Zone, nicht pauschal |
| Regeln | Kite-exklusiver Myloi-Status bestätigt; konkrete Bojen-/Kite-Pass-Regel nicht amtlich gefunden | Text nennt Zonen/Kite-Pass | `confirmed_with_caveat` | Lefkada official | Betreiberregel als solche kennzeichnen |
| Reisewert | Etabliertes Lefkada-Thermalrevier | `worth_trip` | `confirmed` | Lefkada official | Keine |
| Bild | Exakter Unsplash-Kitesporttreffer vorhanden, aber nicht übernommen | Kein Bild | `open` | Unsplash 2025 | Attribution/Original und Myloi-Abgrenzung prüfen |

Abschlussurteil: `accept_after_correction`

## Apelviken

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Apelviken; Kåsa/Lilla Apelviken und Träslövsläge getrennt | Entspricht | `confirmed` | Visit Varberg | Keine |
| Einstieg | Kommunale Bereichskoordinate 57.082543, 12.258718 | Entspricht | `confirmed` | Varbergs kommun | Als Bereich/Surfparkering, nicht Einzelrampe beschreiben |
| Sportarten | Surf, Kite, Windsurf; Foil/Wing im Revier | Surf, Kite, Windsurf, Wing | `confirmed_with_caveat` | Visit Varberg | Wing explizit spotgenau nachbelegen oder als Foil-Angebot vorsichtig formulieren |
| Bedingungen | Sandige, flache Bucht, Windwellen, Beginner–Advanced, Strömungsgefahr | Level leer, SW/W, Chop/kleine Welle | `confirmed_with_caveat` | Visit Varberg/municipality | Level ergänzen oder bewusst offen lassen; Strömungswarnung erhalten |
| Einrichtungen | Parking, Toilet, Essen, Center/Verleih; Camping nahebei | Entspricht; Camping nicht modellierbar | `model_gap` | Kommune/Visit Varberg | Campinghinweis außerhalb Facilities führen |
| Reisewert | Schwedisches Surfzentrum mit Ganzjahresprofil | `worth_trip` | `confirmed` | Visit Varberg | Keine |
| Bild | Exaktes Apelviken-Winterbild, Galeriecharakter | Galerie | `confirmed_with_caveat` | Commons 18046071 | Behalten, nicht Hero |

Abschlussurteil: `accept_as_worth_trip`

## Marmari – Fun2Fun

| Feld | Ergebnis Blindrecherche | Vorhandener Wert | Bewertung | Quellen | Korrektur |
|---|---|---|---|---|---|
| Identität | Fun2Fun ist ein konkretes Center am Rand von Marmari; andere Marmari-/Caravia-Stationen getrennt | Aliasse enthalten `Marmari Beach` und `Agios Georgios Beach Marmari` | `confirmed_with_caveat` | Fun2Fun, Kos tourism, Windsurfing Kos | Breite/unklare Aliasse entfernen; Centername primär führen |
| Einstieg | Marmari-Ortskoordinate ist kein Fun2Fun-Start | Kein Wert, blockiert | `coordinate_risk` | Kos official, Betreiber | Exakte Center-/Beach-Zufahrt vom Betreiber oder Karte bestätigen |
| Sportarten | Kite, Windsurf, Wing bestätigt | Entspricht | `confirmed` | Fun2Fun | Foils offen lassen |
| Bedingungen | Sand/Sandbänke, on-/side-onshore Lernbedingungen; genaue Windrichtungen offen | N/W, Beginner/Advanced | `unsupported` | Betreiber | N/W nicht speichern, bis spotgenau belegt |
| Einrichtungen/Sicherheit | Schule, Verleih, Rescue; öffentliche Zonenregeln offen | Nur Schule, allgemeiner Safety-Text | `confirmed_with_caveat` | Fun2Fun | Betreiber-/Behördenregeln trennen |
| Reisewert | Multi-Sport-Center mit plausibler Reisequalität | `worth_trip` vorbereitet | `confirmed_with_caveat` | Fun2Fun, Kos tourism | Erst nach Koordinatenklärung akzeptieren |
| Bild | Kein exaktes, rechtlich dokumentiertes Bild | Kein Bild | `open` | Gegenrecherche | Nach Koordinatenklärung neu suchen |

Abschlussurteil: `hold_for_more_research`

