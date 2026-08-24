---
target: Meteogramm
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
timestamp: 2026-08-23T18-41-37Z
slug: frontend-src-components-data-meteogram-tsx
---
# Meteogramm – Darstellung und Datenqualität

## Design Health Score

| # | Heuristik | Score | Kernbefund |
|---|---|---:|---|
| 1 | Sichtbarkeit des Systemstatus | 3 | Auswahl, fehlende Werte und Marine-Verfügbarkeit sichtbar; Cursor unbeschriftet. |
| 2 | Übereinstimmung mit der realen Welt | 2 | Einheiten vorhanden, aber Böen, Modellspanne und „Welle m · s“ unklar. |
| 3 | Kontrolle und Freiheit | 2 | Tastaturfokus und Scrollen vorhanden; keine Tagesnavigation oder Zoomstufe. |
| 4 | Konsistenz und Standards | 3 | Saubere Slot-Ausrichtung; Skalenwerte nicht wie eine vertikale Achse angeordnet. |
| 5 | Fehlervermeidung | 2 | Dynamische Skalen vermeiden Clipping; Regenbalken sättigen dennoch ohne Hinweis. |
| 6 | Wiedererkennen statt Erinnern | 2 | Nutzer müssen Opazität, Whisker, Pfeile, Striche und Cursor selbst entschlüsseln. |
| 7 | Flexibilität und Effizienz | 2 | Für Experten dicht und effizient; mobil fehlen Sprung- und Verdichtungsoptionen. |
| 8 | Ästhetik und Minimalismus | 3 | Ruhige, kompakte Komposition; 8–9-px-Texte und viele gleichrangige Signale. |
| 9 | Fehler erkennen und beheben | 2 | Lücken erkennbar, Ursachen und Bedeutung der Striche aber nicht erklärt. |
| 10 | Hilfe und Dokumentation | 1 | SVG-Beschreibung vorhanden, sichtbare Legende und Datenalternative fehlen. |
| **Gesamt** | | **22/40** | **Brauchbar, aber erklärungs- und barrierearm** |

## Designspezifität

Das Meteogramm ist inhaltlich klar auf Wind- und Wassersport zugeschnitten: Wetter, Regen, Temperatur, Mittelwind, Böen, Modellspanne, Richtung, Swell, Periode und Tagesvertrauen teilen sich eine Zeitachse. Die visuelle Sprache bleibt hingegen generisch-technisch. Der Produktcharakter entsteht primär aus den Daten, nicht aus einer besonders verständlichen Instrumentengestaltung.

Der deterministische Scan meldete 0 Befunde. Das ist kein Widerspruch: Die wichtigsten Probleme sind semantisch und fachlich – fehlende Legende, missverständliche Skalen, Datenzuordnung und Regen-Sättigung – und liegen außerhalb der mechanisch erkannten Muster.

## Gesamteindruck

Fachlich ist eine gute Basis vorhanden: keine erfundenen Messwerte, dynamische Skalen, lokale Zeitzone, explizite Marine-Verfügbarkeit und Modellbandbreite. Die größte Chance liegt darin, aus dem dichten Expertenchart ein erklärbares Prognoseinstrument zu machen, ohne seine Informationsdichte zu verlieren.

## Was funktioniert

- Die feste 76-px-Beschriftungsspalte hält die Messgrößen beim horizontalen Scrollen sichtbar.
- Fehlende Werte werden als fehlend dargestellt; Temperaturpfade werden über Datenlücken nicht künstlich verbunden.
- Temperatur-, Wind- und Wellenskalen berücksichtigen Extremwerte; die Windskala umfasst auch Böen und Modellobergrenze.
- Die Backend-Pipeline validiert Zahlenbereiche, sortiert eindeutige UTC-Zeitpunkte und gruppiert nach lokalem Datum.

## Prioritäten

### P1 – Undokumentierte visuelle Grammatik

Mittelwind, Böe, Modellspanne, Windrichtung, ausgewählte Uhrzeit, fehlende Werte und Sicherheit sind nicht sichtbar erklärt. Das führt gerade bei den entscheidenden Windinformationen zu Fehlinterpretationen. Eine kompakte Legende mit den echten Zeichen und klaren deutschen Bezeichnungen ist erforderlich. Empfohlener Befehl: `$impeccable clarify`.

### P1 – 3-Stunden-Zuordnung ist vertraglich fragil

Die Auswahl vergleicht nur die lokale Stunde und verwendet den ersten Treffer. Sie verlässt sich darauf, dass jedes Backend-Tagesobjekt bereits korrekt nach lokalem Datum gruppiert ist. Bei wiederholten DST-Stunden, adaptierten Payloads oder gebrochenen Verträgen kann der falsche Zeitpunkt gewählt werden. Nach vollem zoniertem Datum plus Stunde beziehungsweise eindeutigem UTC-Zeitpunkt zuordnen und Vertragsverletzungen validieren. Empfohlener Befehl: `$impeccable harden`.

### P1 – Skalen werden visuell falsch gelesen

Maximum und Minimum stehen horizontal nebeneinander, obwohl die Daten vertikal skaliert sind. Das erschwert quantitative Vergleiche. Maximal-, Mittel- und Minimalwert müssen an den entsprechenden horizontalen Gittern ausgerichtet werden. Empfohlener Befehl: `$impeccable layout`.

### P1 – Keine gleichwertige barrierefreie Datendarstellung

SVG-Titel und Beschreibung nennen nur das Thema, nicht Werte, Beziehungen, Lücken oder Sicherheit. Eine strukturierte Tageszusammenfassung oder Datentabelle sollte als zugängliche Alternative bereitstehen. Empfohlener Befehl: `$impeccable audit`.

### P2 – Regenbalken sind fachlich irreführend

Ab etwa 3,43 mm/h werden alle Balken gleich hoch gezeichnet, ohne Überlaufmarke oder Skala. Eine dynamische beziehungsweise deklarierte Niederschlagsskala oder ein sichtbarer Clipping-Indikator ist notwendig. Empfohlener Befehl: `$impeccable harden`.

## Persona-Risiken

- **Alex, Power User:** schätzt Dichte und exakte Windwerte, kann aber nicht sicher erkennen, ob transparente Erweiterung Böe und Whisker Modellspanne bedeuten. Achsenticks und Tagesnavigation fehlen.
- **Sam, Screenreader/Low Vision:** erhält keine gleichwertige Prognose; 8-px-Texte und 0,4-px-Linien sind fragil. Mehrere Bedeutungen hängen von Farbe, Opazität und Form ab.
- **Casey, mobil und abgelenkt:** sieht nur einen kleinen Ausschnitt des 1.520-px-Charts und muss horizontales Scrollen entdecken. Der ausgewählte Zeitpunkt ist nicht beschriftet.

## Kleinere Beobachtungen

- Zeitangaben sollten `00:00`, `03:00` usw. statt `00`, `03` lauten.
- Dynamische Skalen sollten als solche erkennbar sein; gleiche Balkenhöhen sind zwischen Ansichten nicht direkt vergleichbar.
- „Welle m · s“ sollte in „Wellenhöhe (m)“ und „Periode (s)“ getrennt werden.
- Ein beliebiger ausgewählter Stundenwert kann zwischen den gezeigten 3-Stunden-Samples liegen.
- Bei weniger als zehn gelieferten Tagen werden zusätzliche leere Zukunftstage synthetisiert.
- Clientseitige Laufzeitvalidierung für NaN, Infinity und ungültige IANA-Zeitzonen fehlt.
- Tests fehlen für DST-Fold/Gap, ungültige Zeitzonen, kurze Horizonte, Regenlimit, Cursor-Ausrichtung und gerenderte Barrierefreiheit.

## Fragen

1. Soll zuerst die fachliche Robustheit, die Verständlichkeit oder die mobile/barrierefreie Nutzung verbessert werden?
2. Soll die hohe Informationsdichte für Experten erhalten bleiben oder für Einsteiger progressiv aufgedeckt werden?
3. Soll der nächste Schritt nur die vier P1-Punkte oder zusätzlich alle P2/P3-Befunde umfassen?
