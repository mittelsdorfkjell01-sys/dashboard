---
target: Landingpage-Header beim Scrollen
total_score: 15
max_score: 24
na_heuristics: 5,7,9,10
p0_count: 0
p1_count: 1
timestamp: 2026-09-04T13-40-08Z
slug: frontend-src-components-landingheader-tsx
---
Method: dual-agent (A: /root/header_design_review · B: /root/header_technical_evidence)

## Design Health Score

| # | Heuristik | Wert | Kernbefund |
|---|---|---:|---|
| 1 | Sichtbarkeit des Systemstatus | 2/4 | Der neue Zustand ist erkennbar, aber Doppelbilder machen den eigentlichen Hand-off unklar. |
| 2 | Bezug zur realen Welt | 3/4 | Eine andockende Suche ist vertraut; visuell verhält sie sich aber nicht wie dasselbe Objekt. |
| 3 | Kontrolle und Freiheit | 3/4 | Der Zustand ist durch Zurückscrollen reversibel, besitzt an der Schwelle aber keine Hysterese. |
| 4 | Konsistenz und Standards | 2/4 | Der gedockte Landing-Header stimmt geometrisch und auf Mobile nicht mit `ResultsHeader` überein. |
| 5 | Fehlervermeidung | n/a | Im untersuchten Header-Übergang gibt es keine riskante Eingabe. |
| 6 | Erkennen statt Erinnern | 3/4 | Suche und Konto bleiben auffindbar; mobil wird die Suche jedoch abrupt zum reinen Icon. |
| 7 | Flexibilität und Effizienz | n/a | Für diese Persuade-/Landingpage-Interaktion nicht sinnvoll bewertbar. |
| 8 | Ästhetik und Minimalismus | 2/4 | Die Endzustände sind sauber, der Zwischenzustand enthält konkurrierende Logos und Suchfelder. |
| 9 | Fehlerdiagnose und Erholung | n/a | Kein Fehlerzustand im betrachteten Ablauf. |
| 10 | Hilfe und Dokumentation | n/a | Für diesen Landingpage-Übergang nicht anwendbar. |
| **Gesamt** |  | **15/24** | **Akzeptabel (62,5 %)** |

## Design-Spezifität

Der Ausgangs- und Zielzustand wirken klar nach Surfwinddata: Wortmarke, Surf-Fotografie, Spotsuche und die Transformation von Inspiration zu Utility passen zum Produkt. Der eigentliche Hand-off ist dagegen implementierungsgetrieben und austauschbar. Er simuliert kein physisches Andocken, sondern blendet geklonte Logos und Suchkomponenten gleichzeitig um. Die Idee ist markengerecht, die Bewegung noch nicht.

Der deterministische Impeccable-Scan von `frontend/src/components/LandingHeader.tsx` lief genau einmal und meldete `[]`: 0 Regeln, 0 Findings, keine False Positives. Das ist plausibel, weil das Problem nicht aus einem statisch erkennbaren Anti-Pattern entsteht, sondern erst aus Z-Index, Scrollschwelle, Laufzeit-Geometrie und mehreren nicht synchronisierten Animationsuhren.

Eine sichtbare Impeccable-Overlay-Injektion war mangels nativer Browseroberfläche nicht verlässlich möglich. Als Ersatz wurden frische Headless-Chromium-Kontexte mit Screenshots und gemessenen Styles für Desktop, Mobile und `prefers-reduced-motion` verwendet.

## Gesamteindruck

Oben wirkt die Landingpage großzügig und aspirational; nach dem Scrollen ist die kompakte Utility-Leiste sinnvoll und klar. Der schwache Moment liegt genau dazwischen: Die weiße Fläche härtet früh aus, Wortmarken überlagern sich, Suchfelder wechseln ihre Interaktionshoheit bei halber Sichtbarkeit und die alte Hero-Suche schiebt sich sichtbar durch den neuen Header. Der größte Hebel ist ein bewusst inszenierter Hand-off mit genau einem visuellen Besitzer pro Phase.

## Was bereits funktioniert

- Beide Endzustände sind reduziert und zweckmäßig: erst starke Markenbühne, danach Logo, Suche und Konto als persistente Utility.
- Desktop bindet den Fortschritt an den echten Such-Sentinel und aktualisiert per `requestAnimationFrame`; das ist konzeptionell besser als ein willkürlicher Seitenprozentsatz.
- Mobile behält eine stabile 84-px-Leiste und 44×44-px-Bedienelemente. Der teure Blur ist auf groben Touch-Pointern bereits deaktiviert.

## Priorisierte Probleme und Vorschläge

### P1 — Die Hero-Suche malt über den gedockten Header

Die Hero-Suche liegt mit `z-[1200]` über dem festen Header mit `z-[1000]`. Bei Desktop `scrollY≈704` lief das große Suchfeld sichtbar durch den Bereich der neuen Leiste; auf Mobile entsteht ebenfalls eine Phase mit altem und neuem Suchzugang.

**Vorschlag:** Nur das portalisierte, geöffnete Such-Overlay darf über dem Header liegen. Der eingeklappte Hero-Trigger gehört darunter und sollte beim Eintritt in die Headerzone ausblenden beziehungsweise nicht mehr interaktiv sein. Noch besser: Hero- und Header-Suche als ein Shared-Layout-Element behandeln.

### P2 — Mobile ersetzt den gesamten Header innerhalb von 2–3 Scrollpixeln

Der Coarse-Pointer-Zweig setzt den Fortschritt per `IntersectionObserver` direkt von 0 auf 1. Gemessen wurde der komplette Wechsel zwischen `scrollY=507` und `509`. Beim Herunterscrollen erscheint die weiße Fläche sofort, während Logo und Suchbutton noch 150 ms kreuzblenden; beim Zurückscrollen entsteht die inverse Leerstelle. Ein Zittern um ±1 px erzeugte zehn komplette Zustandswechsel.

**Vorschlag:** Auch auf Touch eine kurze kontinuierliche Zone von etwa 64–96 px verwenden; Blur bleibt dort weiterhin deaktiviert. Interaktivität separat mit Hysterese schalten, etwa Andocken unter 76 px Sentinel-Abstand und Abdocken erst wieder über 100 px.

### P2 — Desktop zeigt einen Vierfach-Crossfade statt eines Morphs

Bei Fortschritt 0,5 sind große Wortmarke, kleine Wortmarke und kompakte Suche jeweils halb sichtbar, während die Hero-Suche noch im Dokument weiterläuft. Die kompakte Suche liegt dabei direkt über der verblassenden großen Wortmarke. Das erzeugt visuelle Matsche statt Kontinuität.

**Vorschlag:** Eine klare Drei-Phasen-Choreografie: (1) große Wortmarke und Hero-Trigger verlassen, (2) kleine Wortmarke und kompakte Suche docken ein, (3) Padding und Divider setzen sich. Die bessere, technisch aufwendigere Variante bewegt eine einzige Wortmarke von Mitte/XL nach links/MD und eine einzige Search-Shell von Hero nach Header.

### P2 — Material, Geometrie und Interaktion laufen auf verschiedenen Uhren

Der Hintergrund ist durch `progress * 3` bereits bei einem Drittel vollständig opak, Inhalt und Höhe laufen aber bis 1 weiter. Pointer-Events wechseln bei 0,5, also mitten im Crossfade. Desktop schrumpft von 122 auf 90 px; der unsichtbare XL-Wordmark-Track hält den Zielzustand höher als den etwa 76 px hohen `ResultsHeader`.

**Vorschlag:** Explizite Phasen mit einem gemeinsamen Easing definieren. Die Oberfläche während der Annäherung nur transluzent machen und erst im Docking voll auflösen; Pointer-Besitz erst bei 80–90 % Sichtbarkeit übergeben. Den Center-Track absolut positionieren und seine Höhe von 58 auf 44 px interpolieren. Zielgeometrie und Controls aus einer gemeinsamen Docked-Header-Basis mit `ResultsHeader` beziehen.

### P3 — Reduced Motion vereinfacht den Übergang nicht

Mit `prefers-reduced-motion: reduce` waren Fortschritt, Geometrie, 12-px-Blur und 150-ms-Opacity-Transition identisch; lediglich Lenis war deaktiviert.

**Vorschlag:** In Reduced Motion einen synchronen Zustandswechsel mit fixer gedockter Geometrie verwenden, ohne scroll-gescrubbten Morph und Blur. `motion-reduce:transition-none` verhindert die aktuelle Mischung aus sofortigen und nachlaufenden Elementen.

## Persona-Warnsignale

- **Jordan, Erstnutzer:** Doppelte Logos und zwei Suchzugänge wirken wie ein unerwarteter Navigationswechsel. Der englische Claim innerhalb der sonst deutschen UI schwächt zusätzlich kurz die Orientierung.
- **Riley, Stresstester:** Mikroscrolling um die mobile Schwelle thrash't den kompletten Zustand. Schnelles Umkehren legt unsynchronisierte Frames und die Z-Index-Kollision reproduzierbar offen.
- **Casey, mobiler Nutzer:** Das 44-px-Ziel ist gut, aber der primäre Suchzugang springt beim Scrollen abrupt von einem beschrifteten großen Control zu einem Icon oben. In der Kollisionsphase ist nicht vertrauenswürdig, welcher Suchzugang aktiv ist.

## Kleinere Beobachtungen

- Bei der mobilen Umschaltung wird Interaktivität nicht exakt mit der sichtbaren Dominanz übergeben.
- Eine feine 1-px-Trennlinie würde die gedockte Leiste auf hellem Content besser absetzen als ein schwerer Standardschatten.
- Die Desktop-Pill wird bereits bei `progress > 0` lazy gemountet. Ein stabil vormontierter Shell-Platzhalter reduziert Varianz im ersten Animationsframe.
- Die zwei beobachteten 401-Ressourcenmeldungen traten in allen Browserkontexten auf, verursachten aber keine Page Exceptions oder fehlgeschlagenen Requests und sind kein Beleg für den Headerfehler.

## Leitfragen

- Soll die Bewegung wie ein echter physischer Dock-Vorgang wirken, oder reicht ein bewusst sauberer Zustandswechsel? Der aktuelle Hybrid vereint die Nachteile beider Ansätze.
- Welches Objekt soll auf Mobile die Kontinuität tragen: Wortmarke oder Suche?
- Soll die Hero-Identität beim ersten Pixel nach oben zurückkehren, oder erst nach einer klaren Rückkehr in die Herozone?
