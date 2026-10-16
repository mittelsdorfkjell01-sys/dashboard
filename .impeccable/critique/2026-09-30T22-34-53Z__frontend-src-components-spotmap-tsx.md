---
target: Windmap auf Spotseite-Daten im Vergleich zu Windfinder
total_score: 20
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-09-30T22-34-53Z
slug: frontend-src-components-spotmap-tsx
---
# Windmap Spotseite-Daten — Vergleich mit Windfinder

## Design Health Score

| # | Heuristik | Score | Hauptproblem |
|---|---|---:|---|
| 1 | Sichtbarkeit des Systemstatus | 2/4 | Zeitpunkt, Produkt, Modelllauf und Aktualität sind auf der Karte nicht eindeutig. |
| 2 | Übereinstimmung mit der realen Welt | 3/4 | Richtung und Werte sind ehrlich; die flächige Animation suggeriert aber räumliche Daten. |
| 3 | Kontrolle und Freiheit | 2/4 | Desktop bleibt statisch; Vollbild und Timeline gibt es nur mobil. |
| 4 | Konsistenz und Standards | 3/4 | Gemeinsamer Zustand und Einheiten sind gut, Titel und aktiver Wellenmodus widersprechen sich. |
| 5 | Fehlervermeidung | 2/4 | Keine erfundenen Richtungen, aber die Punktanimation kann als Windfeld missverstanden werden. |
| 6 | Wiedererkennen statt Erinnern | 2/4 | Timeline und deaktivierte Brandung verlangen Interpretation. |
| 7 | Flexibilität und Effizienz | 1/4 | Keine Modellwahl, Zeitschritte, Wiedergabe oder Desktop-Exploration. |
| 8 | Ästhetik und Minimalismus | 3/4 | Ruhige, kohärente Instrumentenoptik; funktionale Karteninformation ist zu dünn. |
| 9 | Fehlerdiagnose und Erholung | 1/4 | Kachelfehler, Offlinezustand und Retry fehlen auf Kartenebene. |
| 10 | Hilfe und Dokumentation | 1/4 | Punktprognose, Modellstatus und nicht verfügbare Layer werden unzureichend erklärt. |
| **Gesamt** |  | **20/40** | **Akzeptabel, aber erhebliche Funktions- und Vertrauenslücken** |

## Design Specificity Verdict

Die Karte ist bei Datenprovenienz und im dunklen Surfwinddata-Instrumentenrahmen produktspezifisch, im Kartenverhalten jedoch austauschbar. Aktuell zeigt sie eine CARTO/Leaflet-Grundkarte, einen Spotmarker und wenige animierte Streaks. Alle Streaks verwenden denselben einzelnen Spotwert; räumliche Variation existiert nicht. Dadurch sieht die Oberfläche nach regionalem Windfeld aus, obwohl sie nur eine Punktprognose visualisiert.

Der deterministische CLI-Detector meldete 0 Befunde. Der Browser-Detector fand 9 Muster, davon fünf kartenrelevant: 10px-Legendentexte sowie zwei stilistische Border/Shadow-Hinweise. Die wichtigeren Laufzeitprobleme — Modal-Fokus, 36px-Schließen-Ziel, nicht zugängliche Brandungserklärung — wurden erst durch Browserprüfung sichtbar. Selbstbeobachtungs- und Hidden-Element-Funde wurden als Fehlalarme verworfen.

## Overall Impression

Die Karte ist eine gute, ehrliche Spotwert-Visualisierung, aber noch keine Windfinder-artige Wetterkarte. Die größte Chance liegt nicht in weiterer CSS-Politur, sondern in einem echten zeitabhängigen räumlichen Windfeld, einer klaren Zeit-/Modellhierarchie und identischer Exploration auf Desktop und Mobil.

## Was funktioniert

- LiveWind, Nowcast und Forecast bleiben fachlich getrennt; fehlende Richtungen werden nicht erfunden.
- Meteogramm, Sidebar, Karte, Einheiten und Forecastselektion teilen einen kohärenten Zustand.
- Missing-Coordinates, Reduced Motion, Attribution, responsive Grenzen und grundlegende Tastaturbedienung sind solide abgesichert.

## Priority Issues

### P1 — Die Animation behauptet räumliches Wissen

**Warum:** Gleichgerichtete Streaks über dem gesamten Viewport wirken wie Windfinder-Partikel, stammen aber aus nur einem Spotwert. Beim Verschieben bleibt der Wind überall gleich. Das ist ein Vertrauensrisiko.

**Fix:** Kurzfristig als „Punktprognose am Spot · keine Flächenkarte“ kennzeichnen und Bewegung lokal an Marker/Spot begrenzen. Langfristig durch echte u/v-Feldpartikel ersetzen.

### P1 — Zeitstatus und Desktop/Mobil-Parität fehlen

**Warum:** Desktop kann die Karte weder explorieren noch Zeit oder Layer wechseln. Mobil zeigt der Scrubber einen Forecastzeitpunkt, obwohl initial weiterhin „Jetzt“ aktiv sein kann.

**Fix:** Gemeinsame interaktive Map-Shell für Desktop und Mobil; explizites „Jetzt | Prognose“, Wochentag/Datum/Uhrzeit/Zeitzone, ±Zeitschritte, optional Play/Pause sowie Modelllauf und Aktualität.

### P1 — Das räumliche Datenprodukt fehlt

**Warum:** Windfinders Kernnutzen kommt aus kontinuierlichem Farbfeld, echten regionalen Partikeln/Pfeilen, Modellen, Zeitentwicklung und beliebigen Punktabfragen. Die aktuellen `/weather-fields/*`-Endpunkte liefern absichtlich keine aktiven Manifeste.

**Fix:** Lizenzierten Rasteranbieter, Ingestion, Snapshots, Tile-/Vektorproduktion, Storage/CDN und aktives `weather-field-v1`-Manifest aufbauen. Keine Punktwerte künstlich zu Tiles aufblasen.

### P2 — Informationshierarchie ist für Entscheidungen zu schwach

**Warum:** Zeitpunkt, Geschwindigkeit, Böen, Richtung, Modell und Unsicherheit sind nicht als Karten-Readout priorisiert; die Karte wirkt illustrativ.

**Fix:** Reihenfolge: Zeitpunkt/Produkt → Wind/Böe/Richtung/Vertrauen → räumlicher Kontext → Layer/Modell → Provenienzdetails.

### P2 — Accessibility und Recovery sind unvollständig

**Warum:** Vollbildfokus bleibt hinter dem Dialog, der Schließen-Button misst 36×36px, Brandungsgrund steckt nur im `title`, Kartenfläche ist unbenannt, Legende nutzt 10px und Kachelfehler haben keinen Retry.

**Fix:** Fokusmanagement/Inert/Restore, 44px-Ziel, zugängliche Layererklärung, Kartenlabel/Bedienhinweis, größere Funktionstypografie, Tile-Error/Retry/Offline sowie textuelle Werte als Fallback.

## Benötigte Umsetzung

### Sofort, ohne neue Wetterfelder

1. Pseudo-Flächenanimation entfernen oder lokal begrenzen und eindeutig als Punktprognose benennen.
2. Desktop-Vollbild/Exploration und mobile Bedienung vereinheitlichen.
3. `Jetzt` und Forecastzustand synchronisieren; datierte Timeline mit Zeitschritten ergänzen.
4. Karten-Readout für Wert, Richtung, Böen, Zeitpunkt, Quelle und Vertrauen ergänzen.
5. Fokus, Touchziele, Legendengröße, Layererklärung und Fehlerzustände härten.

### Für eine echte Windfinder-artige Karte

1. Zeitindizierte räumliche Felder für `wind_u`, `wind_v`, Geschwindigkeit und Böen beschaffen.
2. Validierte Wellenfelder separat publizieren; Brandung erst mit Nearshore-Modell, Bathymetrie und Holdout-Validierung.
3. `weather-field-v1` mit Modelllauf, Validzeiten, Coverage, Auflösung, Encoding, Qualität und Attribution aktivieren.
4. Immutable Snapshots in Object Storage/CDN publizieren, inklusive stale/failed Fallback und Retention.
5. WebGL/MapLibre-Renderer für Farbfeld, Partikel und Pfeilgitter bauen; Leaflet reicht für Basiskarte, aber nicht ideal für dichte animierte Felder.
6. Beliebige Punktabfrage über Feldwert-Endpunkt oder client-dekodierbare Tiles ermöglichen.
7. Viewport-Stationen als getrennte beobachtete Ebene mit Alter, Qualität und Quelle anbieten.
8. Nur operativ unterstützte Modelle zur Wahl stellen und Modell-/Laufwechsel konsistent halten.

## Persona Red Flags

- **Alex, Power User:** keine Desktop-Exploration, Modellwahl, Zeitschritte, Wiedergabe oder dokumentierte Shortcuts.
- **Jordan, First-Timer:** Animation wird wahrscheinlich als regionales Windfeld verstanden; LiveWind/Baseline/Forecast benötigen Kontext.
- **Sam, Accessibility:** Fokus bleibt hinter dem Vollbilddialog; Farbe/Bewegung tragen zu viel Bedeutung; deaktivierte Brandungserklärung ist nicht erreichbar.
- **Casey, Mobile:** untere Timeline ist gut erreichbar, aber Tageskontext schwach und der Schließen-Touchbereich zu klein.

## Minor Observations

- Dialogtitel bleibt „Windkarte“, selbst wenn „Wellen“ aktiv ist.
- Der Forecast-Day-Scroller ist per Button beschriftet, aber nicht als Gruppe benannt.
- Desktop-Legendentitel, Ticks und Hinweistext sind mit 10px zu klein für funktionale Daten.
- Der Kommentar im Map-Editor behauptet eine MapLibre-Migration, während `SpotMap.tsx` Leaflet verwendet; Dokumentation und Architektur sind auseinander gelaufen.

## Questions to Consider

- Soll die Karte kurzfristig ehrlich als Punktprognose auftreten, bis echte räumliche Felder verfügbar sind?
- Ist der erste Produktschritt eine überzeugende Windkarte oder gleichzeitig Wind, Wellen und Brandung?
- Welche Modelle und welches Lizenz-/Betriebsbudget sind für ein öffentliches räumliches Feld realistisch?
