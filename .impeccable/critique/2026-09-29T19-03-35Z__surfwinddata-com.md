---
target: Öffentliches Surfwinddata-Tool auf Smoothness und Produktreife testen
total_score: 14
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-09-29T19-03-35Z
slug: surfwinddata-com
---
## Design Health Score

| # | Heuristik | Score | Hauptbefund |
|---|---|---:|---|
| 1 | Sichtbarkeit des Systemstatus | 0/4 | HTTP-500 erscheint als Leere oder Nulltreffer |
| 2 | System und reale Welt | 2/4 | Suchsprache verständlich, Domänenkontext dünn |
| 3 | Kontrolle und Freiheit | 3/4 | Schließen, Löschen und Zurück funktionieren |
| 4 | Konsistenz und Standards | 3/4 | Visuell weitgehend kohärent; „Dark Mode/Darkmode“ inkonsistent |
| 5 | Fehlervermeidung | 1/4 | Leere Suche darf in einen Dead End führen |
| 6 | Wiedererkennen statt Erinnern | 2/4 | Optionen sichtbar; Suchkontext geht bei Rückkehr verloren |
| 7 | Flexibilität und Effizienz | 1/4 | Wenige Abkürzungen; mobiler Kalender sehr ineffizient |
| 8 | Ästhetik und Minimalismus | 2/4 | Eigenständig und ruhig, aber zu viel funktionslose Leere |
| 9 | Fehlerdiagnose und Recovery | 0/4 | Kein ehrlicher Fehlerzustand, kein Retry |
| 10 | Hilfe und Dokumentation | 0/4 | Keine kontextuelle Hilfe erkennbar |
| **Gesamt** | | **14/40** | **Poor – Kernreise nicht releasefähig** |

## Design-Spezifität

Surfwinddata besitzt mit Wortmarke, erdiger Farbwelt und ruhiger Editorial-Anmutung eine erkennbare Identität. Die zentrale Suche „Wohin? / Wann? / Welche Sportart?“ wirkt jedoch wie ein generisches Reiseportal. Ohne erreichbare Karte, Spots, Wind-/Swell-Daten oder maritime Mikrointeraktionen wird die eigentliche Produktidee visuell nicht eingelöst.

Der deterministische Scan von `MapView.tsx` meldete 0 Regelverstöße. Das widerspricht den Browserbefunden nicht: Die schwersten Probleme entstehen aus Produktion, Laufzeitstatus und unerreichbaren Datenzuständen. Ein Live-Overlay konnte wegen der öffentlichen CSP `script-src 'self'` nicht injiziert werden; Playwright, axe und CLI-Scan dienten als Fallback-Evidenz.

## Gesamteindruck

Der Einstieg fühlt sich zunächst klar und markant an. Sobald ein Nutzer wirklich einen Spot finden will, bricht das Produkt ab: zentrale öffentliche APIs antworten reproduzierbar mit HTTP 500. Die Oberfläche kommuniziert das nicht ehrlich, sondern zeigt „Keine Spots gefunden“, „Keine Regionen gefunden“ oder eine fast leere „Entdecken“-Seite. Das Tool ist aktuell nicht smooth nutzbar.

## Was bereits funktioniert

- Die drei Suchdimensionen bilden ein schnell verständliches mentales Modell.
- Wortmarke, Typografie, Rundungen und warme Farben wirken zusammengehörig.
- Die mobile Vollbildsuche hat einen klaren Schließen-Weg und sinnvoll platzierte Aktionen im unteren Daumenbereich.
- Die geprüften degradierten Ansichten hatten kein dokumentweites horizontales Overflow; axe meldete dort 0 Verstöße. Das ist keine Freigabe der unerreichbaren regulären Zustände.

## Priorisierte Produktlücken

### P0 – Öffentlicher Datenpfad blockiert die Kernreise

`/api/spots/version`, `/api/spots`, `/api/search`, `/api/regions`, Top-Spots und Spotdetail lieferten auf Desktop und Mobile reproduzierbar 500. Dadurch waren Marker, Cluster, reguläre Spotdetails, aktuelle Bedingungen und Forecast nicht erreichbar.

**Warum relevant:** Das Produkt kann seine Hauptaufgabe nicht erfüllen.

**Fix:** Produktionskonfiguration/Datenpfad stabilisieren und synthetisches Monitoring für `Start → Suche/Karte → Spotdetail` sowie Health-Checks der Kernendpunkte einführen.

**Passender nächster Schritt:** `$impeccable harden` – nach der Backendbehebung für belastbare Runtime-Zustände.

### P1 – Serverfehler werden als echte Nulltreffer dargestellt

„Tarifa“ und ein absichtlich ungültiger Begriff endeten beide in Nulltreffern; die Ergebnisroute blieb fast leer. Nutzer können Laden, echte Nulltreffer und Systemausfall nicht unterscheiden.

**Warum relevant:** Das zerstört Vertrauen und erschwert Support und Recovery.

**Fix:** Getrennte Loading-, Empty-, Offline- und Error-Zustände; Eingaben erhalten; konkrete Meldung und „Erneut versuchen“ anbieten.

**Passender nächster Schritt:** `$impeccable harden` und `$impeccable clarify`.

### P1 – Leere Suche führt in eine inhaltsleere Ergebnisseite

Eine Suche ohne Kriterien ist möglich und navigiert nach `/search`, ohne sinnvollen Default oder hilfreiche nächste Aktion.

**Warum relevant:** Ein einziger Klick erzeugt einen Dead End.

**Fix:** Entweder bewusst „Alle Spots“ zeigen oder vor Navigation mindestens ein Kriterium verlangen. Jede Ergebnisroute braucht Karte/Liste, Skeleton oder erklärenden Fehlerzustand.

**Passender nächster Schritt:** `$impeccable onboard`.

### P2 – Mobile Datumsauswahl erzeugt eine Optionswand

Bis zu zwölf Monate und hunderte Tagesoptionen liegen in einer langen linearen Reihenfolge.

**Warum relevant:** Mobile Nutzer verlieren Kontext; Tastatur- und Screenreader-Navigation wird unnötig lang.

**Fix:** Einen Monat zeigen, Vor/Zurück-Navigation und Presets wie „Heute“, „Dieses Wochenende“, „7 Tage“ und „Flexibel“ anbieten.

**Passender nächster Schritt:** `$impeccable distill` und `$impeccable adapt`.

### P2 – Touch-Ziele, Kartenfokus und Hero-Kontrast brauchen Nacharbeit

Mobile Filter-Buttons maßen als tatsächliche Button-Box nur etwa 24 px. Die Leaflet-Karte ist als unbenanntes `div[tabindex="0"]` ein stiller Fokuspunkt. Teile von Logo/Hauptüberschrift sind auf dem dunklen Hero schwach sichtbar.

**Warum relevant:** Motorische, visuelle und Tastaturzugänglichkeit leiden.

**Fix:** Ganze Filterzeile als mindestens 44 px hohes Ziel; zugänglichen Namen/Anleitung für die Karte; Kontrast gegen WCAG AA prüfen.

**Passender nächster Schritt:** `$impeccable audit` und `$impeccable adapt`.

## Persona-Red-Flags

- **Jordan, Erstnutzer:** „Beste Sammlung“ verspricht viel, doch „Tarifa“ liefert Nulltreffer. Auf „Entdecken“ ist nicht erkennbar, ob geladen wird, nichts existiert oder das System ausgefallen ist.
- **Casey, mobil:** Die unteren Hauptaktionen sind gut erreichbar, aber Filterziele sind zu klein, der Jahreskalender zu lang und der Suchzustand nach Rückkehr nicht sichtbar.
- **Sam, Accessibility:** Grundlegende Landmarken und Fokusdarstellung sind vorhanden. Der unbenannte Kartenfokus, lange Kalenderreihenfolge und nicht angekündigte Fehlerstatus bleiben klare Risiken.

## Weitere Beobachtungen

- Browser-Zurück funktioniert, Reload behebt den Fehler erwartbar nicht.
- `/api/account/me` mit 401 ist für anonyme Nutzer erwartbar und kein Kernfehler.
- Fehlantworten kamen oft nach 93–179 ms; das misst nur schnelle Fehler, nicht echte Produktperformance.
- Die Search-Route machte den aktiven `sport=surf`-Filter im sichtbaren Inhalt nicht nachvollziehbar.
- „Dark Mode“ und „Darkmode“ werden uneinheitlich geschrieben.

## Fragen, die das Produkt beantworten sollte

- Soll ein API-Ausfall wirklich so aussehen, als gäbe es keine Spots?
- Ist „Wann?“ für die erste Suche so wichtig wie „Wohin?“, oder gehört Zeit erst nach der Spotwahl?
- Was ist die kleinste Kernreise, die garantiert funktionieren muss: Ort → Karte → Spot → jetzt/nächstes Wochenende?
- Wie kann bereits der erste Viewport Wind, Küste und Spotqualität zeigen, statt hauptsächlich leere Fläche?
