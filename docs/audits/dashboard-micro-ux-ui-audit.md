# Dashboard Micro-UX- und UI-Konsistenz-Audit

Auditdatum: 20. August 2026
Geprüfter Stand: `658e39d56f03d8961e5be6ed2d1382eff0cb93b0` auf `feature/hero-admin-and-search-updates`

## 1. Kurzfazit

Das Dashboard wirkt insgesamt geschlossen und produktionsnah: Navigation, Formulare, Zustände und die mobile Kartenansicht folgen einem klaren Admin-System. Auf allen 12 geprüften Routen trat bei 1440 px, 1024 px und 390 px kein dokumentweiter horizontaler Overflow und kein JavaScript-Absturz auf. Die wichtigsten Lücken liegen nicht in einer grundlegenden Neugestaltung, sondern in Barrierefreiheit, einem mobilen Formular-Detail und einer fachlich veralteten Eingabe für Windmonate bei Regionen.

- 12 Seiten in drei Viewports geprüft
- 2 Workflows vollständig und 5 weitere sicher teilweise geprüft
- 2 kleine Workflow-Optimierungen mit messbarer Klickersparnis empfohlen
- 8 Befunde: P0 0, P1 1, P2 6, P3 1
- Top-Quick-Wins: Kartenmarker benennen, mobilen Anlagen-Selector umbrechen, „Filter zurücksetzen“ ergänzen
- Audit Health Score: **14/20 – gut**

| Bereich | Wertung | Kurzbegründung |
|---|---:|---|
| Accessibility | 2/4 | Gute Grundstruktur und sichtbare Fokuszustände; Kartenmarker ohne Namen sowie zwei kleinere Axe-Befunde. |
| Performance | 3/4 | Alle Routen reagierten lokal ohne auffällige Hänger; Kartenansicht bleibt der schwerste UI-Bereich. |
| Responsive | 3/4 | Kein Seiten-Overflow, gute mobile Listen und Sticky-Aktionen; ein Segment-Selector verletzt die Kartenbegrenzung. |
| Theming | 3/4 | Konsistentes semantisches Dark-Theme; bewusst kein Light-Theme, aber ein zu schwacher Text-Token. |
| Implementation Integrity | 3/4 | Wiederverwendbares Admin-UI-System und sauberer Detector-Lauf; Windmonate im Regionenformular widersprechen dem aktuellen Produktzustand. |

Belege: [Desktop-Übersicht](dashboard-micro-ux-ui-audit-assets/desktop-admin.png), [Mobile-Übersicht](dashboard-micro-ux-ui-audit-assets/mobile-admin.png), [Runtime-Matrix](dashboard-micro-ux-ui-audit-assets/runtime-results.json)

## 2. Scope und Testbedingungen

- Umgebung: lokale, isolierte Entwicklungsumgebung mit lokaler PostgreSQL-/Redis-Testinstanz und vorhandenen Seed-Daten
- Browser: Chromium, automatisierte Laufzeitprüfung plus visuelle Kontrolle
- Rolle: Administrator; nicht privilegierte oder gesperrte Rollen waren nicht verfügbar
- Viewports: Desktop 1440 × 900, Tablet 1024 × 900, Mobile 390 × 844
- Theme: Dark Mode vollständig geprüft. Light Mode ist im Admin bewusst nicht implementiert und daher nicht prüfbar.
- Sicher ausgeführt: Navigation, Suche/Filter, Öffnen und Verlassen eines Datensatzes, Unsaved-Changes-Dialog, responsive Darstellung, DOM-/Axe-Prüfung
- Nicht ausgelöst: persistierende Create/Update/Delete-Aktionen, absichtliche Serverfehler, Rollenentzug und produktive Nebenwirkungen
- Automatischer UI-Detector: keine Treffer für die vom Audit-Werkzeug erkannten generischen Anti-Patterns

## 3. Seitenabdeckung

| Route | Seite | Desktop | Tablet | Mobile | Dark | Light | Workflow / Ergebnis |
|---|---|---:|---:|---:|---:|---:|---|
| `/admin` | Übersicht | ✓ | ✓ | ✓ | ✓ | n. v. | Navigation und KPI-/Arbeitslisten geprüft; keine Laufzeitfehler. |
| `/admin/spots` | Spots | ✓ | ✓ | ✓ | ✓ | n. v. | Suche, Öffnen, Rückkehr und Filterkontext vollständig geprüft. |
| `/admin/spot/new` | Spot anlegen | ✓ | ✓ | ✓ | ✓ | n. v. | Formular und mobile Sticky-Aktion geprüft; Submit nicht ausgelöst. |
| `/admin/hero` | Hero | ✓ | ✓ | ✓ | ✓ | n. v. | Darstellung und Navigation geprüft. |
| `/admin/regions` | Regionen | ✓ | ✓ | ✓ | ✓ | n. v. | Liste und Navigation geprüft. |
| `/admin/region/new` | Region anlegen | ✓ | ✓ | ✓ | ✓ | n. v. | Formular geprüft; Submit nicht ausgelöst. |
| `/admin/review` | Review | ✓ | ✓ | ✓ | ✓ | n. v. | Empty State geprüft; keine Review-Fälle vorhanden. |
| `/admin/map` | Karte | ✓ | ✓ | ✓ | ✓ | n. v. | Karte und Marker geprüft; Marker haben keine zugänglichen Namen. |
| `/admin/activity` | Aktivität | ✓ | ✓ | ✓ | ✓ | n. v. | Darstellung und Navigation geprüft. |
| `/admin/operations` | Operationen | ✓ | ✓ | ✓ | ✓ | n. v. | Empty State und Tabelle geprüft; keine laufenden/fehlgeschlagenen Jobs vorhanden. |
| `/admin/weather` | Wetterprofile | ✓ | ✓ | ✓ | ✓ | n. v. | Darstellung und Navigation geprüft. |
| `/admin/users` | Nutzer | ✓ | ✓ | ✓ | ✓ | n. v. | Darstellung und Navigation geprüft. |

`n. v.` = nicht verfügbar. Der Admin erzwingt derzeit ein dunkles Farbschema; ein Theme-Schalter existiert nicht.

## 4. Workflow-Optimierungen

### WF-01 – Filter schneller vollständig leeren

- Priorität / Aufwand: P2 / S
- Seite und Position: `/admin/spots`, am Ende der Filterzeile; mobil unter den Filtern über die verfügbare Breite
- Ziel: eine gefilterte Spotliste mit einer Aktion in den Ausgangszustand versetzen
- Ist-Pfad: zwei bis fünf aktive Such-/Filterfelder einzeln leeren; 2–5 Interaktionen
- Soll-Pfad: „Filter zurücksetzen“ wählen; 1 Interaktion
- Messbarer Nutzen: 1–4 Klicks beziehungsweise Taps pro Reset weniger
- Exaktes Label / Aktion: **„Filter zurücksetzen“**; leert Suche, Status, Region, Sport, Vollständigkeit, Medienfilter und Offset. Die Sortierung darf erhalten bleiben.
- Warum nicht bereits vorhanden: Einzelne Controls können zurückgesetzt werden, aber es gibt keine gebündelte Aktion für kombinierte Filter.
- Überladungsprüfung: nur anzeigen, wenn mindestens zwei Filter aktiv sind; dadurch entsteht im Normalzustand kein zusätzlicher Button.
- Zustände: kein Ladezustand nötig; Erfolg ist die unmittelbar ungefilterte Liste; bei ungültigem URL-State auf Defaultwerte zurückfallen.
- Desktop / Mobile: bestehender sekundärer `Button`; Desktop inline rechts, Mobile als kompakte volle Zeile unter den Controls.
- Abnahmekriterium: Bei mindestens zwei aktiven Filtern ist der Button sichtbar und setzt alle genannten Filter mit genau einer Aktivierung zurück; Fokus bleibt nachvollziehbar in der Filtergruppe.
- Konfidenz: hoch; vollständig am realen Suchworkflow geprüft.

### WF-02 – Speichern und zur Liste zurückkehren

- Priorität / Aufwand: P2 / S
- Seite und Position: Spot-Bearbeitung, im bestehenden rechten Aktionsbereich direkt bei „Speichern“; mobil in der Sticky-Aktionsleiste ohne dritte gleichgewichtete Primäraktion
- Ziel: typische Kurzkorrekturen abschließen und unmittelbar in den erhaltenen Listenkontext zurückkehren
- Ist-Pfad: „Speichern“, Erfolg abwarten, „Zurück zu den Spots“; 2 Klicks nach der Eingabe
- Soll-Pfad: „Speichern und zurück“; 1 Klick
- Messbarer Nutzen: 1 Klick und ein bewusster Kontextwechsel weniger je Kurzkorrektur
- Exaktes Label / Aktion: **„Speichern und zurück“**; validiert und speichert wie „Speichern“, navigiert erst nach Erfolg über den vorhandenen Return-State zurück.
- Warum nicht bereits vorhanden: Speichern und Navigation sind heute getrennte, funktionierende Aktionen.
- Überladungsprüfung: nur im Edit-Modus und als sekundäre Aktion; „Speichern“ bleibt primär. Mobil kann die Aktion in ein kleines vorhandenes Aktionsmenü wandern, falls zwei breite Buttons nicht passen.
- Zustände: während des Requests deaktiviert und mit bestehendem Loading-Muster; Erfolg navigiert zur vorherigen gefilterten Liste; Fehler bleibt im Formular und zeigt die vorhandene Feld-/Servermeldung.
- Desktop / Mobile: bestehende `Button`-Komponente, Variante secondary; keine neue Komponente.
- Abnahmekriterium: Nach erfolgreichem Speichern landet der Nutzer mit einem Klick auf derselben gefilterten Spotliste; bei Fehler erfolgt keine Navigation.
- Konfidenz: hoch für den Pfad, mittel für die mobile Platzierung.

Der getestete Kernworkflow ist bereits positiv: Suche nach „Tarifa“ → Spot öffnen → „Zurück zu den Spots“ stellte URL und Suchwert wieder her. Ebenso blockiert der konsistente Dialog „Ungespeicherte Änderungen“ eine versehentliche Navigation, bis „Abbrechen“ oder „Änderungen verwerfen“ gewählt wurde.

## 5. Bewertung möglicher zusätzlicher Buttons

| Kandidat | Entscheidung | Begründung |
|---|---|---|
| Filter zurücksetzen | Empfohlen | Spart bei kombinierten Filtern nachweisbar 1–4 Aktionen und erscheint nur bedingt. |
| Speichern und zurück | Empfohlen | Spart im häufigen Kurzkorrektur-Pfad einen Klick und nutzt bestehenden Return-State. |
| Region anlegen direkt im Spotformular | Vorläufig nicht empfohlen | Ein bloßer Link würde bei bereits ausgefülltem Spotformular den Unsaved-Changes-Dialog auslösen. Erst mit sicherer Draft-Wiederherstellung und Return-State wäre die Abkürzung wirklich besser. |
| Öffentliche Vorschau im Spoteditor | Nicht empfohlen | Eine Vorschauaktion existiert bereits im Spot-Ops-Bereich; ein Duplikat erhöht nur die Aktionsdichte. |
| Zusätzliche „Bearbeiten“-Buttons auf Übersichtskarten | Nicht empfohlen | Die vorhandenen verlinkten Zeilen/Karten decken den Pfad ab; zusätzliche Buttons wären visuelles Rauschen. |
| „Nächster Fall“ im Review | Nicht verifiziert | Ohne Review-Fälle konnte weder der heutige Ablauf noch eine Einsparung belastbar gemessen werden. |
| Betroffenen Spot aus Operation öffnen | Nicht verifiziert | Ohne Job-Läufe fehlte ein realer Datensatz für die Pfadprüfung. |

## 6. UI- und Micro-UX-Befunde

### Accessibility

#### UI-01 – Kartenmarker besitzen keinen zugänglichen Namen

- Priorität: **P1**
- Route / Kontext: `/admin/map`, Desktop 1440 px, Tablet 1024 px und Mobile 390 px, Dark Mode
- Reproduktion: Karte öffnen, Marker per Tastatur oder Accessibility Tree untersuchen.
- Evidenz: Axe `button-name`; 4 betroffene Marker auf Desktop, 3 auf Tablet, 2 im mobilen Initial-Viewport; Ziel `.leaflet-marker-icon.swd-admin-pin.leaflet-interactive`; Implementierung in `AdminMap.tsx` im Marker-/Cluster-Aufbau.
- Beobachtung: Interaktive Marker haben `role="button"` und `tabindex="0"`, aber keinen Accessible Name.
- Auswirkung: Screenreader-Nutzer hören nur einen unbenannten Button und können Spot beziehungsweise Cluster nicht unterscheiden.
- Empfehlung: jedem Spotmarker `aria-label="Spot öffnen: {Spotname}"`, jedem Cluster `aria-label="{Anzahl} Spots anzeigen"` geben; Popup-Inhalt nicht als alleinigen Namen verwenden.
- Abnahmekriterium: Axe meldet auf `/admin/map` keinen `button-name`-Fehler; jeder fokussierbare Marker hat einen eindeutigen, lokalisierten Namen.
- Konfidenz: hoch.

#### UI-02 – Sidebar-Fußzeile unterschreitet den Kontrast

- Priorität: **P2**
- Route / Kontext: alle Desktop-/Tablet-Seiten mit sichtbarer Sidebar, Dark Mode
- Reproduktion: beliebige Adminroute bei 1024 px oder 1440 px öffnen und `surfwind data · Back office` prüfen.
- Evidenz: Axe `color-contrast`; Vordergrund `#55555c` auf `#111112`, Verhältnis 2,55:1; Ziel `.text-admin-faint`, `AdminShell.tsx` Fußzeile.
- Beobachtung: Der schwächste Text-Token ist für diese kleine Schrift zu dunkel.
- Auswirkung: Die Systemzuordnung ist für Nutzer mit reduziertem Kontrastsehen schwer lesbar.
- Empfehlung: nur den semantischen `--a-faint`-Token beziehungsweise diese Footer-Nutzung auf mindestens 4,5:1 anheben.
- Abnahmekriterium: Text erreicht mindestens 4,5:1 in Dark Mode und Axe meldet keinen Kontrastfehler.
- Konfidenz: hoch.

#### UI-03 – Horizontal scrollbare Operationstabelle ist nicht per Tastatur fokussierbar

- Priorität: **P2**
- Route / Kontext: `/admin/operations`, Tablet und Mobile, Dark Mode
- Reproduktion: schmalen Viewport öffnen und per Tab durch die Seite navigieren.
- Evidenz: Axe `scrollable-region-focusable`; Wrapper mit `overflow-x-auto`, Implementierung im Tabellenbereich von `AdminOperations.tsx`.
- Beobachtung: Der Scrollcontainer kann Inhalte horizontal verbergen, erhält aber keinen Tastaturfokus.
- Auswirkung: Tastaturnutzer können verdeckte Spalten nicht zuverlässig erreichen beziehungsweise scrollen.
- Empfehlung: Wrapper mit `tabIndex={0}`, verständlichem `aria-label` und sichtbarem Fokus versehen; vorhandenen Focus-Ring wiederverwenden.
- Abnahmekriterium: Container ist per Tab erreichbar, mit Pfeil-/Shift+Mausrad horizontal scrollbar und Axe-fehlerfrei.
- Konfidenz: hoch.

### Responsive Darstellung

#### UI-04 – Anlagen-Selector ragt mobil aus seiner Karte

- Priorität: **P2**
- Route / Kontext: `/admin/spot/new`, Mobile 390 × 844, Dark Mode
- Reproduktion: zum Abschnitt Anlagen scrollen und die Optionen „Vorhanden“, „Nicht vorhanden“, „Unbekannt“ betrachten.
- Evidenz: [Mobile Spot anlegen](dashboard-micro-ux-ui-audit-assets/mobile-admin-spot-new.png); Segmented-Control in `AdminSpotForm.tsx` im Anlagenabschnitt.
- Beobachtung: Die drei Optionen bleiben zwar innerhalb des Viewports, überschreiten aber die Innenkante ihrer jeweiligen Karte und brechen den horizontalen Rhythmus.
- Auswirkung: Das Formular wirkt beschädigt; lange deutsche Labels werden bei kleineren Geräten riskant.
- Empfehlung: ab schmalem Breakpoint in ein 1- oder 2-spaltiges Grid umbrechen und Buttons auf `min-width: 0`/volle Zellbreite begrenzen.
- Abnahmekriterium: Bei 320–390 px liegen alle drei Optionen vollständig innerhalb der Karten-Paddings, ohne Clipping oder Dokument-Overflow.
- Konfidenz: hoch.

#### UI-06 – Mobile Topbar-Aktionen sind funktional, aber knapp bemessen

- Priorität: **P3**
- Route / Kontext: alle mobilen Adminseiten, 390 px, Dark Mode
- Reproduktion: mobile Topbar und horizontale Navigation prüfen.
- Evidenz: gemessene Größen: Glocke 32 × 32 px, Logout 94 × 34 px, Navigationstabs ca. 32 px hoch; [Mobile Übersicht](dashboard-micro-ux-ui-audit-assets/mobile-admin.png).
- Beobachtung: Die Ziele erfüllen die 24-px-Mindestgröße, bleiben aber unter der komfortablen 44-px-Touchgröße.
- Auswirkung: Bei Bewegung oder eingeschränkter Motorik steigt die Fehlertap-Wahrscheinlichkeit.
- Empfehlung: Topbar-Icons und zentrale mobile Navigation auf mindestens 40 px, ideal 44 px, erhöhen, ohne die visuelle Icongröße zu vergrößern.
- Abnahmekriterium: interaktive Topbar-Ziele besitzen bei 390 px mindestens 40 × 40 px Hit Area und überlappen nicht.
- Konfidenz: hoch.

### Fachliche Konsistenz

#### UI-05 – Regionenformular bietet veraltete Windmonate an

- Priorität: **P2**
- Route / Kontext: `/admin/region/new` und Region-Bearbeitung, alle Viewports, Dark Mode
- Reproduktion: Region anlegen oder bearbeiten und den Monatsbereich Jan–Dez öffnen.
- Evidenz: Laufzeitkontrolle der zwölf Monatsbuttons; Implementierung in `AdminRegionCreate.tsx` und `AdminRegionForm.tsx`.
- Beobachtung: Das Dashboard suggeriert, dass Windmonate auf Regionenebene redaktionell gepflegt werden. Der aktuelle Produktstand behandelt Regionen jedoch vorerst als **„Unbekannt“**; belastbare Klimatologie wird spotbezogen angezeigt.
- Auswirkung: Redakteure können fachlich nicht mehr maßgebliche Werte pflegen und erwarten eine öffentliche Wirkung, die so nicht vorgesehen ist.
- Empfehlung: den lokalen Eingabeblock vorerst aus Create/Edit entfernen oder deaktiviert als „Windverfügbarkeit: Unbekannt“ anzeigen. Keine Datenmodelländerung und keine neue Seitenstruktur nötig.
- Abnahmekriterium: Regionenformulare erlauben keine Monatsauswahl mehr und zeigen eindeutig „Windverfügbarkeit: Unbekannt“, bis eine neue Regionenregel definiert ist.
- Konfidenz: hoch, basierend auf dem festgelegten Produktzustand und der Laufzeitansicht.

### Workflow-Effizienz

#### UI-07 – Kein Sammel-Reset für kombinierte Spotfilter

- Priorität: **P2**
- Evidenz und Abnahme: siehe WF-01.

#### UI-08 – Speichern und Rückkehr erfordern zwei getrennte Aktionen

- Priorität: **P2**
- Evidenz und Abnahme: siehe WF-02.

## 7. Konsistenzmatrix zentraler Muster

| Muster | Liste/Übersicht | Formular | Sonderseiten | Bewertung |
|---|---|---|---|---|
| Seitenkopf | Kompakt, ruhig, konsistent | Gleiche Hierarchie | Review/Operations folgen dem Muster | Konsistent |
| Primäraktion | Klar hervorgehoben | Speichern/Anlegen dominant | Zustandsabhängig | Konsistent |
| Sekundäraktion | Zurückhaltend | Abbrechen/Zurück klar getrennt | Empty States ruhig | Konsistent |
| Felder | Einheitliche Höhe, Radius und Labels | Durchgehend wiederverwendet | Filter passen zum System | Konsistent |
| Status/Feedback | Badges und Empty States verständlich | Validierungsflächen vorhanden | Fehlerpfade nicht vollständig testbar | Teilweise verifiziert |
| Navigation | Desktop-Sidebar und mobile Tab-Leiste | Kontext bleibt erhalten | Alle 12 Routen erreichbar | Konsistent |
| Responsive | Listen werden mobil sinnvoll verdichtet | Sticky Save funktioniert | Keine globale Überbreite | Eine lokale Abweichung |
| Theme | Semantische Dark-Tokens | Durchgehend dunkel | Kein Light Mode vorhanden | Produktkonsistent, Kontrastdetail offen |

## 8. Priorisierte Quick Wins

1. Kartenmarker und Cluster mit eindeutigen `aria-label`s versehen (P1, S).
2. Anlagen-Segmentsteuerung im Spotformular mobil umbrechen (P2, S).
3. Bedingten Button „Filter zurücksetzen“ in der Spotliste ergänzen (P2, S).
4. Sidebar-Faint-Text auf mindestens 4,5:1 Kontrast anheben (P2, XS).
5. Scrollcontainer der Operationstabelle fokussierbar und beschriftet machen (P2, XS).
6. Regionen-Windmonate vorerst durch „Windverfügbarkeit: Unbekannt“ ersetzen (P2, S).
7. Sekundäre Aktion „Speichern und zurück“ im Spoteditor ergänzen (P2, S).
8. Mobile Topbar-Hit-Areas auf mindestens 40 px erhöhen (P3, S).

## 9. Bewusst nicht empfohlene Änderungen

- Keine neue Dashboard-Struktur: Die lange Arbeitsliste auf der Übersicht ist umfangreich, aber verständlich und außerhalb des gewünschten Mikro-UX-Scopes.
- Kein zusätzlicher Light/Dark-Schalter: Das Admin-Theme ist derzeit bewusst Dark-only; ein zweites Theme wäre ein eigenes Produktvorhaben.
- Kein zweiter Vorschau-Button: Die öffentliche Vorschau ist bereits im Spot-Ops-Bereich vorhanden.
- Keine zusätzlichen „Bearbeiten“-Buttons auf jeder Karte oder Zeile: Das würde die visuelle Hierarchie verschlechtern, ohne einen belastbaren Klickgewinn zu bringen.
- Kein direkter „Region anlegen“-Link im ausgefüllten Spotformular, solange ein Regionswechsel den Spot-Draft nicht sicher wiederherstellt.
- Keine Änderung am Datenmodell oder an der Informationsarchitektur für Winddaten; empfohlen ist nur die lokale Korrektur des veralteten Regionenfelds.

## 10. Nicht verifiziert / offene Testgrenzen

- Light Mode: im Admin nicht verfügbar.
- Review-Entscheidung, Erfolgsfeedback und automatischer Sprung zum nächsten Fall: keine Review-Fälle in den sicheren Testdaten.
- Operations-Zustände „läuft“, „fehlgeschlagen“, Retry und Link zum betroffenen Spot: keine Job-Läufe vorhanden.
- Nicht-Admin-, Read-only- und verweigerte Berechtigungszustände: keine entsprechende Testrolle verfügbar.
- Absichtliche Netzwerk-/Serverfehler und Offlinezustände: nicht ausgelöst, um den Audit read-only und nebenwirkungsfrei zu halten.
- Erfolgreiches Anlegen oder Speichern von Spot/Region: nicht ausgeführt, da dies persistierende Testdaten verändert hätte.
- Sehr lange reale Inhalte, Übersetzungen außerhalb Deutsch sowie 200-%-Zoom: nicht Bestandteil dieses Laufs.

Der Audit hat ausschließlich Bericht und Evidenzdateien erzeugt. Produktcode, Konfiguration, Datenmodell und Informationsarchitektur wurden nicht verändert.
