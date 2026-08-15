---
target: Frontend Admin-Dashboard
total_score: 25
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-08-15T16-47-47Z
slug: frontend-src-pages-adminhome-tsx
---
# Frontend-Dashboard UI Review

## Design Health Score

| # | Heuristik | Score | Kernproblem |
|---|---|---:|---|
| 1 | Sichtbarkeit des Systemstatus | 2/4 | Board zeigt beim Laden potenziell bereits einen leeren Zustand; Benachrichtigungsfehler bleiben unsichtbar. |
| 2 | Übereinstimmung mit der realen Welt | 3/4 | Gute Domänensprache, aber „Spot(s)“ und unkommentierte Klimatologie-Begriffe wirken technisch. |
| 3 | Kontrolle und Freiheit | 3/4 | Abbrechen, Bestätigen und explizite Bewegungen vorhanden; Undo fehlt. |
| 4 | Konsistenz und Standards | 3/4 | Starke Tokens, aber neue Admin-Primitives und umgebogene Legacy-Utilities laufen parallel. |
| 5 | Fehlervermeidung | 3/4 | Bestätigungen helfen; dauerhaft sichtbare destruktive Kartenaktionen erhöhen Fehlklickrisiko. |
| 6 | Wiedererkennen statt Erinnern | 3/4 | Navigation und Labels sind sichtbar; versteckter Seitentitel schwächt Orientierung. |
| 7 | Flexibilität und Effizienz | 3/4 | Auswahl, Drag-and-drop, Bewegungsaktionen und Shortcut unterstützen Profis. |
| 8 | Ästhetik und Minimalismus | 2/4 | Ruhig, aber zu viele gleich gewichtete Module und Kartenaktionen. |
| 9 | Fehler erkennen und beheben | 2/4 | Teilweise gute Fehlerzustände, aber Benachrichtigungsfehler sind still und Recovery fehlt. |
| 10 | Hilfe und Dokumentation | 1/4 | Keine kontextuelle Hilfe, Shortcut-Erklärung oder Statusdefinitionen. |
| **Gesamt** |  | **25/40** | **Solide Basis, deutlicher Verbesserungsbedarf** |

## Design Specificity Verdict

Die Oberfläche ist fachlich auf Spot-, Moderations-, Wetter- und Veröffentlichungsarbeit zugeschnitten, visuell aber weitgehend austauschbar. Die dokumentierte Linear/Vercel-Anmutung, Sidebar, Utility-Bar, Board, Statuslisten und Kennzahlen könnten nahezu unverändert in vielen CMS-Produkten stehen. Produktcharakter entsteht fast nur durch Wordmark und Teal. Die Chance liegt in einer eigenen, kompakten „Spot Health“-Sprache, die Region, redaktionelle Vollständigkeit, Medien, Wetterfrische und Moderation zusammenführt.

Der automatische Scan fand 0 Verstöße in `AdminHome.tsx`, `AdminShell.tsx` und `components/admin/**`. Das ist ein gutes Signal für offensichtliche Code-Antipatterns, bewertet aber weder die CSS-only-Theme-Datei noch visuelle Hierarchie. Der bestehende Playwright-Flow bestand Desktop und Pixel 5 (2/2), ohne horizontales Overflow bei 320 px und ohne schwere/kritische axe-Verstöße.

## Gesamteindruck

Das Dashboard ist funktional, ruhig und fachlich brauchbar. Sein größtes Problem ist nicht Dekoration, sondern Priorität: Der Code verspricht eine handlungsorientierte Übersicht, visuell gewinnt aber das Board. Der Nutzer bekommt mehrere ähnlich gewichtete Arbeitszonen statt eines klaren operativen Briefings.

## Was funktioniert

- Die Inhalte spiegeln echte Operator-Arbeit: Regionsfehler, Moderation, Publikationsreife, fehlende Inhalte und Klimatologie statt Vanity Metrics.
- Die responsive Navigation behält Textlabels und aktive Zustände; Rollen filtern irrelevante Ziele.
- Das Board bietet Drag-and-drop sowie zugänglichere Alternativen, Auswahl, Bulk-Löschen, Validierung und Schutz vor ungespeicherten Änderungen.

## Prioritätsprobleme

### P1 — Widersprüchliche Informationshierarchie

Das Board steht vor der priorisierten Aufgabenliste, obwohl `AdminHome.tsx` ausdrücklich „Was ist zu tun?“ als Leitprinzip nennt. Der sichtbare Seitentitel fehlt, und die Aufgabenliste hat keine sichtbare Überschrift.

**Auswirkung:** Dringende Moderations- und Veröffentlichungsthemen rutschen unter Teamkoordination; Nutzer müssen die Priorität selbst rekonstruieren.

**Anpassung:** Sichtbares „Übersicht“-Header mit kompaktem Betriebsstatus; nach blockierenden Regionsfehlern sofort die Aktionsliste; Board als sekundären Teamarbeitsbereich positionieren.

**Passender Befehl:** `$impeccable layout`

### P1 — Fokusindikator im Dark Theme potenziell kaum sichtbar

Der globale Fokus nutzt `--sw-ink`, während das Admin-Theme `--a-ring` definiert, es aber nicht an den Fokus koppelt.

**Auswirkung:** Keyboard- und Low-Vision-Nutzer können ihre aktuelle Position auf dunklen Flächen verlieren.

**Anpassung:** Admin-spezifisches `:focus-visible` mit `var(--a-ring)` und ausreichendem Offset; Links, Buttons, Checkboxen, Nav-Pills, Popover und Modals prüfen.

**Passender Befehl:** `$impeccable audit`

### P1 — Lade- und Fehlerzustände können falsche Sicherheit geben

Das Board kann zunächst „Keine Aufgaben“ zeigen; Benachrichtigungsfehler werden verschluckt.

**Auswirkung:** Operatoren interpretieren noch nicht geladene oder fehlgeschlagene Daten als erledigte Arbeit.

**Anpassung:** Loading, Empty, Stale, Success und Error klar trennen; bestehende Daten bei Refresh-Fehler erhalten und Retry anbieten.

**Passender Befehl:** `$impeccable harden`

### P2 — Zu viele dauerhaft sichtbare Kartenaktionen

Auswahl, Drag, Verschieben, Bearbeiten und Löschen stehen parallel auf jeder Board-Karte.

**Auswirkung:** Dichte Boards werden visuell laut, Fehlklicks wahrscheinlicher und der wichtigste Statuswechsel bleibt unklar.

**Anpassung:** Auswahl und primären Übergang sichtbar lassen; Edit/Löschen in ein beschriftetes, tastaturfähiges Overflow-Menü verschieben.

**Passender Befehl:** `$impeccable distill`

### P2 — Kompetent, aber visuell generisch

Monochromes Dark UI und Standardkarten sind konsistent, transportieren jedoch wenig Surfwind-spezifische Identität.

**Auswirkung:** Das Dashboard wirkt wie ein solides Standard-Admin statt eines vertrauenswürdigen Kontrollzentrums für Surf- und Wetterdaten.

**Anpassung:** Ein vereinheitlichtes „Spot Health“-Muster entwickeln; semantische Zustände und Datenfrische konsistent visualisieren, ohne weitere Panels hinzuzufügen.

**Passender Befehl:** `$impeccable bolder`

## Persona-Warnsignale

**Alex (Power User):** Ein Shortcut existiert, ist aber nicht auffindbar. Acht gleichrangige Navigationsziele und mehrere Arbeitszonen verlangsamen den Scan. Bulk-Löschen existiert, Bulk-Statuswechsel fehlen. Permanente Kartenaktionen sind eher laut als effizient.

**Sam (Keyboard/Screenreader/Low Vision):** Der mögliche Dark-on-dark-Fokus ist das größte Risiko. Nicht-dragbare Bewegungsbuttons sind positiv; Drag-Anweisungen und Drop-Semantik fehlen. Benachrichtigungsfehler werden nicht angekündigt. 32×32-px-Header-Controls und kleine Checkboxen erschweren motorische Bedienung.

**Jordan (First-Time Operator):** „Board“, „Review“, „Klimatologie“ und Rangfarben werden nicht erklärt. Versteckter Seitentitel und unbeschriftete Aufgabenliste schwächen Orientierung. Der voreilige Empty State kann Vertrauen beschädigen.

## Kleinere Beobachtungen

- Die aktive Desktop-Navigation kombiniert Hintergrund, Text und Akzentmarker überzeugend.
- Die mobile Navigation scrollt horizontal; versteckte Ziele bleiben trotz Auto-Scroll schlecht entdeckbar.
- „Fertig — nichts offen“ ist faktisch toter Text, da grüne/erledigte Spots aus den Spalten ausgeschlossen werden.
- Kommentare widersprechen sich: `AdminShell.tsx` erwähnt einen Theme-Toggle, das Theme ist aber dark-only.
- Klimatologie-Fehler stehen in einem schwachen Textstreifen ohne Reparaturpfad.
- Die Inhaltsbreite ist unbeschränkt; auf großen Displays entstehen lange Scanwege.
- Touch-Ziele im Header sollten systemweit auf mindestens etwa 44×44 px vereinheitlicht werden.
- Semantische Admin-Tokens sollten Legacy-Remaps schrittweise ersetzen, damit ein Zustand nur eine visuelle Definition besitzt.

## Fragen

- Soll die Startseite primär persönliche Aktionsliste, Team-Board oder Systemzustand sein?
- Kann ein einheitliches Spot-Health-Modell mehrere getrennte Statusmodule ersetzen?
- Welche Board-Aktionen sind häufig genug, um auf jeder Karte sichtbar zu bleiben?
