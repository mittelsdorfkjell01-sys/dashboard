---
target: Klimatologie/Windmonate für Spot-Beobachtung und Urlaubsplanung
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
timestamp: 2026-08-29T19-05-30Z
slug: frontend-src-pages-spotdetail-tsx
---
# Windklimatologie / Windmonate – fachliche und UX-Prüfung

## Design Health Score

| # | Heuristik | Score | Kernbefund |
|---|---|---:|---|
| 1 | Visibility of System Status | 3 | Gute Lade- und Wechselzustände; aktuelle und gewählte Woche sind kaum erklärt. |
| 2 | Match System / Real World | 2 | Der Windtag wird definiert, Fachbegriffe und die Bedeutung von „Zuverlässigkeit“ bleiben zu abstrakt. |
| 3 | User Control and Freedom | 3 | Presets, Slider und Richtungsfilter sind stark; Reset und echte Entscheidungspfade fehlen. |
| 4 | Consistency and Standards | 2 | V3 und stiller V2-Fallback zeigen nicht vergleichbare Metriken unter ähnlicher Oberfläche. |
| 5 | Error Prevention | 2 | Eingaben werden begrenzt; eine zu selbstsichere Buchungsinterpretation wird nicht verhindert. |
| 6 | Recognition Rather Than Recall | 2 | Auswahl ist sichtbar; Farbstufen, Heute-Marker und mobile Jahresnavigation müssen erschlossen werden. |
| 7 | Flexibility and Efficiency | 3 | URL, Persistenz und individuelle Windfenster sind gut; Spotvergleich, Watchlist und Alarm fehlen. |
| 8 | Aesthetic and Minimalist Design | 2 | Ruhige Datenästhetik, aber widersprüchliche Achse und ein 14-zeiliges Detail schwächen die Hierarchie. |
| 9 | Error Recovery | 1 | Der V3-Fehler zeigt eine rohe Meldung ohne Retry; V2 hat dagegen eine Wiederholen-Aktion. |
| 10 | Help and Documentation | 2 | Methodik ist vorhanden, aber Schwellen, Farblogik und statistische Unsicherheit fehlen am Entscheidungspunkt. |
| **Gesamt** | | **22/40** | **Akzeptabel; als Buchungshilfe noch nicht vertrauenswürdig genug.** |

## Design Specificity Verdict

**Fachlich spezifisch, entscheidungslogisch noch austauschbar.** Windfenster, spotgeprüfte Windrichtungen, Drei-Stunden-Sessions und ERA5 verankern die Oberfläche im Surfprodukt. Die Komposition bleibt jedoch ein generisches Analytics-Muster aus Filter, Balkendiagramm, Kennzahlentabelle und Kleingedrucktem. Die beiden eigentlichen Jobs „Spot beobachten“ und „Urlaub buchen“ werden nicht getrennt.

**Deterministischer Scan:** Der CLI-Detector meldete 0 Findings in SpotDetail, V3-Modul, Slider und V2-Fallback. Im headless Browser fand der injizierte Detector innerhalb des Klimatologie-Moduls 2 `line-length`-Gruppen: die Definition der historischen Wahrscheinlichkeit und der Methodiktext. Das stützt den manuellen Befund, dass die entscheidenden Erklärungen zu lang und zu spät kommen. Keine erkennbaren False Positives.

**Visual overlays:** Die Browserprüfung lief headless; daher steht kein sichtbarer `[Human]`-Tab mit Overlays zur Verfügung.

## Overall Impression

V3 misst etwas Sinnvolles: nicht mittleren Wind, sondern die historische Trefferquote einer praktisch nutzbaren Woche. Für saisonale Orientierung ist das gut. Für eine Urlaubsbuchung ist die Darstellung zu sicher, statistisch zu punktgenau und in zwei Grenzfällen rechnerisch verzerrt. Der größte Hebel ist, aus „beste Zeit“ eine ehrliche, vergleichbare historische Erfolgsquote mit Unsicherheit und klarem nächsten Schritt zu machen.

## Fachliche Prüfung der Berechnung

- Datengrundlage: die letzten 20 vollständigen Jahre ERA5, stündlicher 10-Meter-Wind am nächsten Rasterpunkt, lokale Zeitzone und Tageslicht.
- V3-Erfolg: mindestens zwei Tage innerhalb der Saisonwoche; pro Tag mindestens drei echte, zusammenhängende Stunden im gewählten Windbereich; optional nur geprüfte brauchbare Windrichtungen.
- Datenhygiene: eine Jahr/Woche-Probe zählt erst ab 95 % Vollständigkeit; unter 15 gültigen Jahren wird keine Zuverlässigkeit veröffentlicht.
- Die Kennzahl ist eine historische Trefferquote, keine Vorhersage. 10 erfolgreiche von 20 Jahren ergeben 50 %. Ein grobes 95-%-Wilson-Intervall liegt dabei bei etwa 30–70 %; selbst 14/20 = 70 % liegt ungefähr bei 48–85 %. Die UI zeigt diese Unsicherheit nicht.
- Zwei der 52 „Wochen“ umfassen acht statt sieben Tage (Woche 1 und 27). Damit haben sie systematisch mehr Gelegenheit, die Zwei-Tage-Regel zu erfüllen.
- Die „beste Planungszeit“ ist der längste Lauf von mindestens vier Wochen mit mindestens 50 % Trefferquote. Sie ist nicht zwingend der windstärkste oder robusteste Zeitraum und verbindet Dezember/Januar nicht zirkulär.
- Das Standardfenster 15–20 kt ist ohne Sport, Können, Board/Kite/Segel und individuelle Obergrenze willkürlich. Wind über 20 kt zählt darin als unbrauchbar, obwohl er für andere Nutzer gerade attraktiv sein kann.
- ERA5 kann lokale Thermik, Düsen, Abschattung, Küstenform und kleinräumige Böen nicht zuverlässig abbilden. Ohne Stations-/Community-Kalibrierung bleibt die Aussage eine regionale Modellorientierung.

## Entscheidungswert

| Ziel | V2 „Windmonate“ | V3 |
|---|---|---|
| Spot im Blick behalten | Niedrig: Anteil einzelner Tageslichtstunden, keine zusammenhängenden Sessions, keine Richtung. | Mittel: aktuelle Woche, brauchbare Sessions und Richtung; aber kein Watch-/Alarm-Übergang. |
| Urlaub buchen | Nicht ausreichend. Prozentwerte sind keine Reise-Erfolgswahrscheinlichkeit. | Als Vorauswahl brauchbar, für eine Buchung allein zu unsicher und zu selbstsicher beschriftet. |

## What's Working

1. **Die Kernmetrik passt zum Surfjob.** Zusammenhängende, tageslichtgebundene Sessions und mehrere Windtage sind viel entscheidungsnäher als Monatsmittel.
2. **Die Auswahl ist flexibel.** Presets, genauer Slider, geprüfte Richtung, persistierter Zustand und teilbare URL unterstützen wiederholte Nutzung.
3. **Die Evidenz ist grundsätzlich vorhanden.** Erfolgreiche/Gültige Jahre, Sessionstunden, Spanne, Zeitraum und Modellgrenzen können Vertrauen korrekt kalibrieren.

## Priority Issues

### P1 – Die Saisonempfehlung ist mathematisch und sprachlich zu sicher

**Warum es zählt:** Ein exaktes orangefarbenes Buchungsfenster basiert nur auf dem längsten Lauf über einer 50-%-Schwelle. Winter-Saisons über den Jahreswechsel werden geteilt; ein längerer mittelmäßiger Lauf kann einen kürzeren sehr starken Lauf schlagen.

**Fix:** Saison zirkulär berechnen, alternative Fenster ausgeben und nach robuster Trefferquote statt nur Lauflänge ordnen. Text ändern in „Historisch verlässlichster Windzeitraum“ und direkt „X von Y Jahren“ ergänzen.

**Suggested command:** `$impeccable clarify`

### P1 – Die Wochen sind nicht vollständig vergleichbar und Unsicherheit fehlt

**Warum es zählt:** Zwei Acht-Tage-Buckets haben einen strukturellen Vorteil. Rohwerte aus 15–20 Jahren springen in 5–6,7-Prozentpunkten, werden aber wie präzise Wahrscheinlichkeiten dargestellt. Eine einzelne Woche unter 50 % kann die Saison hart zerschneiden.

**Fix:** Gleich lange, rollierende Sieben-Tage-Fenster verwenden; für 7- und 14-Tage-Reisen getrennte Trefferquoten berechnen; ganze Prozent bzw. „X/Y Jahre“ priorisieren; Konfidenz-/Unsicherheitsband oder mindestens eine verbale Stufe zeigen; Schwellen gegen kleine Stichproben robust machen.

**Suggested command:** `$impeccable harden`

### P1 – Diagrammachse und mobile Zentrierung verfälschen den Jahresvergleich

**Warum es zählt:** Balkenhöhe kodiert Prozent vertikal, 0/25/50/75/100 stehen aber horizontal unter der Zeitachse. Farbsprünge bei 30/50/70 % haben keine Legende. Mobil zentriert die Ansicht „heute“ und versteckt große Teile des Jahres; Wochenziele sind nur 10–12 px breit.

**Fix:** Echte vertikale Prozentachse mit Gitternetz, Monate ausschließlich horizontal, Farbskala erklären oder reduzieren. Auf Mobil zuerst einen 12-Monats-Ganzjahresüberblick zeigen und Wochen erst nach Auswahl öffnen.

**Suggested command:** `$impeccable layout`

### P1 – Der stille V3→V2-Fallback zerstört Vergleichbarkeit

**Warum es zählt:** V3 zeigt Erfolgsjahre für zusammenhängende Sessions; V2 zeigt Anteil der Tageslichtstunden bzw. Stunden/Tag, ignoriert Richtung und skaliert pro Auswahl/Spot. Nutzer können zwei optisch ähnliche Kurven für dieselbe Kennzahl halten. Im Code ist V3 öffentlich standardmäßig deaktiviert, sofern das Deployment es nicht explizit einschaltet.

**Fix:** Einen sichtbaren gemeinsamen Datenvertrag schaffen. Falls V2 bleiben muss, klar als „Basis-Klimatologie“ mit anderer Metrik kennzeichnen und Spotvergleich sperren oder erklären. Mittelfristig V3 flächendeckend rechnen und V2 aus der Entscheidungsansicht entfernen.

**Suggested command:** `$impeccable shape`

### P2 – Die Oberfläche beantwortet Analysefragen, aber führt nicht zur Entscheidung

**Warum es zählt:** Für „beobachten“ fehlt Alarm/Merken und die Vorschau auf kommende Wochen; für „Urlaub“ fehlen Reisedauer, Alternativzeitraum und Spotvergleich. Das 14-zeilige Wochendetail überlädt beide Jobs.

**Fix:** Zwei Modi anbieten: „Jetzt beobachten“ mit nächster Saisonphase, 10-Tage-Forecast und Watch-CTA; „Urlaub planen“ mit 7/14-Tage-Erfolgsquote, Top-Monaten, Alternativen und Vergleich. Im Detail zuerst nur Trefferjahre, erwartbare Windtage/Sessionstunden und Unsicherheit zeigen; Rest aufklappen.

**Suggested command:** `$impeccable distill`

## Persona Red Flags

**Jordan (First-Timer):** „kt“, Windfenster, Sessionstunden, Perzentil und Zuverlässigkeit sind nicht ausreichend übersetzt. Jordan liest den orangefarbenen Zeitraum wahrscheinlich als Buchungsempfehlung und sieht die 50-%-Schwelle nicht.

**Casey (mobiler Nutzer):** Nach Auto-Zentrierung ist das Jahr nicht vollständig sichtbar. Sehr schmale Wochenbalken und ein langes Detail erschweren eine schnelle Reiseentscheidung mit einer Hand.

**Alex (Power User):** Parameter und URLs sind effizient, aber Spots lassen sich nicht nebeneinander vergleichen, Zeiträume nicht speichern und keine Forecast-Wache anlegen. V2/V3 kann beim Spotwechsel unbemerkt wechseln.

## Minor Observations

- Der Heute-Punkt ist nicht erklärt.
- Die global gelieferte `data_quality` wird im V3-Header nicht genutzt; die Detailbezeichnung „Datenqualität“ meint im Wesentlichen nur historische Abdeckung, nicht lokale Modellgüte.
- Der V3-Fehlerzustand bietet keinen Retry und hängt die technische Fehlermeldung an.
- Die lange Methodik ist fachlich verantwortungsvoll, kommt aber erst nach der starken Empfehlung.
- Der vorhandene V3-E2E-Test ist teilweise veraltet: 4 von 8 Desktop-Fällen scheiterten an eingeklapptem Richtungsfilter, mehrdeutigem Selektor und alter V2-Copy; die Kern-Unit-/Backend-Tests bestanden.

## Questions to Consider

- Soll das Produkt primär sagen „Wann lohnt sich Forecast-Beobachtung?“ oder „Wie riskant ist eine Reisebuchung?“
- Darf eine 50-%-Historienquote überhaupt „beste Planungszeit“ heißen?
- Soll ein Nutzer standardmäßig „ab 15 kt“ sehen oder ein sport-/equipmentabhängiges nutzbares Band?
- Welcher einzelne Wert soll einen vernünftigen Nutzer vom Buchen abhalten – und warum steht er nicht direkt neben der Empfehlung?
