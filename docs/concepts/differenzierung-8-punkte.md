# Konzept: Acht Differenzierungspunkte in App und UI

Stand: 11. Oktober 2026. Grundlage ist die Konkurrenzanalyse (Surfr, Windfinder,
Windguru, Windy, Windy.app, KiteReady, Windmate, Surfline). Dieses Dokument ist
ein Produkt- und UI-Konzept, keine Implementierung. Es gilt nur für die
öffentliche Seite (surfwinddata), nicht für das Admin-Dashboard.

---

## 0. Leitplanken

### 0.1 Positionierung in einem Satz

> **Die Konkurrenz zeigt Wetter. surfwinddata sagt, was das Wetter an diesem Spot bedeutet, und meldet sich, wenn es passt.**

Rohdaten (Modelle, Karten, Messstationen) gewinnen wir nicht gegen Windy oder
Windfinder. Wir gewinnen auf der Ebene darüber: Spotwissen, Einordnung,
Reiseplanung, Ruhe.

### 0.2 Designregeln für alle acht Punkte

Alle neuen Elemente folgen dem bestehenden System (siehe Token-Entscheidungen):

| Regel | Umsetzung |
|---|---|
| **Ein neues Element ersetzt Lärm, statt ihn zu ergänzen** | Kein Punkt bekommt eine eigene Navigationsebene. Alles hängt an bestehenden Orten: Spot-Info, Daten-Tab, Burger-Menü, Einstellungen, Landing-Reihen. |
| **Editoriale Grammatik** | Überschriften in Satzform (`text-title`/`text-heading`), Labels in Versalien `text-caption uppercase tracking-caps text-muted`, Haarlinien `border-line` statt Karten mit Schatten, `SectionBand` für Rhythmus. |
| **Informieren, nicht vorschreiben** | Wir greifen nie in die Entscheidung ein, sondern liefern gute Daten und Infos. Kein Ampelsystem, keine Badges, keine Scores, kein Ausgrauen „schlechter“ Stunden. Die Produktentscheidung E1 (`personalized-scoring.md`) gilt weiter: **Fakten über den Spot** und **Fakten über die Vorhersage**, nie ein Urteil über „gut für dich“. |
| **Hinweis = Icon + ein Satz** | Wo eine Sicherheitsinfo nötig ist (ablandiger Wind, Gefahrenstellen, Sperrzeiten), steht ein **rotes Ausrufezeichen-Icon** (`danger`-Token, 16 px, `aria-hidden`) vor **einem sachlichen Satz** in normaler Textfarbe. Keine farbigen Flächen, keine roten Texte, keine Rahmen. Das ist das einzige Warnmuster der App. |
| **Eine Akzentfarbe** | `--sw-teal` nur für den aktiven Zustand. Rot ausschließlich im Ausrufezeichen-Icon, nie als Dekoration. |
| **Ehrlich statt gefüllt** | Fehlt eine Info, wird der Block ausgeblendet oder als `PlannedBox` „Geplant“ markiert, wie schon im Konto. Nie Platzhalterdaten. |
| **Mobile zuerst** | Jeder Wireframe unten ist für 390 px gedacht. Desktop ist dieselbe Struktur in breiterem Raster. |
| **Keine Pop-ups** | Kein Installations-Banner, kein Push-Permission-Dialog beim ersten Besuch, kein Cookie-ähnliches Overlay. Fragen kommen nur nach einer bewussten Nutzeraktion. |

### 0.3 Wo heute was steht (Ausgangsbestand)

| Ort | Heute | Relevant für |
|---|---|---|
| Spot · Info (`SpotDetail.tsx`) | Hero, Beschreibung, Aktionsreihe (Favorit, Teilen, Besucht, Bearbeiten), Galerie, `SpotMetaGrid`, `Facilities`, Lagekarte, Community, ähnliche Spots | 2, 4, 7, 8 |
| Spot · Daten (`DatenPage.tsx`, dunkel) | Tagesleiste, Meteogramm, `TodaySummary`, 8-Tage-Raster, Windmonate | 2, 3, 5 |
| Landing | Hero, Suche, drei `RecommendationRow`s (jetzt, nächste Woche, nächste Zeit), Katalog | 1, 5 |
| Konto · Einstellungen | Abschnitt „Benachrichtigungen“ mit `PlannedNote` | 1 |
| Burger-Menü (`AccountMenu`) | Saved, Spots besucht, Spots hinzufügen, Darkmode, Rechtliches | 1, 6 |
| FAQ / Über uns | statisch | 3, 6 |
| Backend | `watches` und `notifications` (Sprint-1-Schema, ungenutzt), `session_checkin`-Event mit `outcome`, `variant_conditions` mit `local_rules`/`hazards`/`entry`/`tide` (öffentlich ausgeliefert, aber nicht angezeigt), Wetterverifikation, Windklimatologie | alle |

---

## 1. Spot-Wecker (Wetteralarme für Favoriten)

**Problem der Nutzer:** ständiges Nachschauen. Windfinder hat Alarme nur im Abo, Windy.app kassiert dafür.
**Unser Hebel:** kostenlos, ruhig, spotbezogen.

### 1.1 Zweistufiges Modell

Das bestehende Bereitschaftsdokument (`notification-readiness.md`) verlangt für
Empfehlungs-Benachrichtigungen aus der Engine acht Wochen Daten und 70 %
Präzision. Darauf warten wir nicht. Stattdessen zwei Stufen:

| Stufe | Auslöser | Verstößt gegen E1? | Freigabe |
|---|---|---|---|
| **A · Eigene Regel** | Nutzer legt selbst fest: Wind von X bis Y kn, Richtung aus den nutzbaren Sektoren, Tageslicht, mindestens N Stunden am Stück | Nein. Der Nutzer setzt die Schwelle, wir rechnen nur nach. | sofort baubar |
| **B · „Für dich“** | Die personalisierte Engine erkennt ein gutes Fenster | Nein, solange die Nachricht nur sagt, *dass* es passt, nicht *warum* | erst nach bestandener Bereitschaftsprüfung |

Stufe A ist das, was Windfinder Plus verkauft, nur ohne Abo. Stufe B ist das,
was niemand hat. Die Check-ins aus Punkt 7 liefern genau die Wahrheitssignale,
die Stufe B freischalten.

### 1.2 Einstieg im UI

Kein neuer Menüpunkt. Der Wecker hängt am **Favorit**:

```
Spot · Info, Aktionsreihe (heute)
( ♡ )  ( ↗ )  ( ⌖ )  ( ✎ )

Nach Tap auf ♡ (gespeichert), einmalig darunter:
─────────────────────────────────────────
Gespeichert.
Soll dich Laboe melden, wenn es geht?
[ Spot-Wecker einrichten ]    nicht jetzt
─────────────────────────────────────────
```

- Erscheint nur direkt nach dem Speichern, als ruhige Inline-Zeile (kein Modal, kein Toast).
- „nicht jetzt“ blendet aus und fragt bei diesem Spot nie wieder.
- Zusätzlich eine Glocke in der Aktionsreihe, **nur** wenn der Spot gespeichert ist: `( 🔔 )` im selben Rundknopf-Chassis wie `VisitedButton`, gefüllt, wenn ein Wecker aktiv ist.

### 1.3 Wecker-Sheet

Bottom-Sheet auf dem Handy (gleiche Mechanik wie `MobileSearchSheet`), Modal auf dem Desktop.

```
─────────────────────────────────────────
                                       ✕
Spot-Wecker
Laboe

WIND                                 kn
12 ━━━━━━━━●━━━━━━━━━━━●━━━━ 28
         von 15        bis 25

RICHTUNG
        N
   ╱ ▓▓▓▓ ╲         vorausgewählt:
  W  ▓▓▓▓   O       die nutzbaren
   ╲    ! ╱         Richtungen des Spots
        S

MINDESTENS          [ 2 h | 3 h | 4 h ]

TAGE                [ Alle | Wochenende ]

─────────────────────────────────────────
Du hörst höchstens einmal am Tag von uns,
nie zwischen 21 und 8 Uhr.

[        Wecker speichern        ]
─────────────────────────────────────────
```

- **Vorbelegung statt Leerformular:** Windfenster aus „Mein Setup“ (Personal Band), sonst aus dem Level des Spots. Richtung ist die nutzbare Richtung des Spots, vorausgewählt.
- **Richtungswähler** ist eine reduzierte Variante von `CompassDial` mit tippbaren 45°-Sektoren. **Alle Sektoren sind wählbar**; wir schränken nicht ein. Ablandige Sektoren tragen nur das rote Ausrufezeichen. Wählt der Nutzer einen davon, erscheint darunter ein Satz: „! Bei Westwind ist Laboe ablandig.“ Kein Sperren, kein Dialog.
- **Kanal:** nur Push. E-Mail kommt später (siehe 1.6). Ohne erteilte Push-Berechtigung fragt der Speichern-Knopf erst jetzt, also nach einer bewussten Aktion, nach der Berechtigung.
- Primitive: `Segmented`, `Button`. Keine neuen Controls.
- Einheit kommt aus `PrefsContext` (kn/bft/m/s).

### 1.4 Die Nachricht selbst

Ton: wie ein Freund am Strand, nicht wie ein Wetterdienst.

```
Push:
  Laboe: deine Bedingungen morgen
  Sa 11–16 Uhr · 17–21 kn aus West
```

Die Nachricht nennt nur, dass **die vom Nutzer gesetzte Regel** erfüllt ist, und
die Zahlen. Kein „perfekt“, kein „geh raus“. Tap öffnet den Daten-Tab mit Anker
auf den Tag. Ist eine der Stunden ablandig, steht das als zweiter Satz in der
Nachricht, nicht als Warnung formuliert: „Ab 15 Uhr ablandig.“

**Versandregeln** (aus `notification-readiness.md` übernommen):
höchstens 1 Nachricht pro Spot in 72 h, höchstens 2 pro Woche über alle Spots,
Ruhezeit 21–8 Uhr, keine Nachricht bei schwächer werdendem Signal, Versand am
Vorabend um 18 Uhr bzw. morgens um 8 Uhr für „heute“.

### 1.5 Verwaltung

- **Einstellungen › Benachrichtigungen**: Die `PlannedNote` wird ersetzt durch eine Liste der Wecker (Spotname, Kurzregel, Schalter `Switch`, „Bearbeiten“). Darunter global: Ruhezeit, „Alle pausieren“, „Rückfragen nach Sessions“ (Punkt 7.2).
- **Saved** (`/konto/favoriten`): kleine Glocke an jeder Kachel mit aktivem Wecker. Kein Badge mit Zahl.

### 1.6 Daten und Backend

| Was | Bestand | Neu |
|---|---|---|
| Regelspeicher | `watches` (Sprint-1-Schema, `user_ref` als String) | Neue Migration: `user_id` als FK auf `app_users`, `rule` JSONB versioniert (`kind: "manual"`, `wind_min/max`, `sectors`, `min_hours`, `days`), `quiet_hours`, `tz`, `last_sent_at` |
| Auswertung | Forecast pro Spot liegt stündlich vor | Cron-Job (nur auf der Admin-Instanz, `RUN_MAINTENANCE_CRONS`) nach jedem Forecast-Refresh; Dedupe-Schlüssel Nutzer×Spot×Fenster |
| Versand Push | fehlt | Tabelle `push_subscriptions` mit `platform: web | ios | android`. Jetzt Web-Push (VAPID) über die PWA (6b), später APNs/FCM über die native App. Der Dispatcher kennt nur „Nachricht an Gerät“, der Kanal ist austauschbar. |
| Versand E-Mail | `app/account/email.py`, aktuell `mailAvailable=false` | **Bewusst später.** Kein Mail-Provider in dieser Phase. |
| Events | `notification_sent/opened/dismissed` reserviert | jetzt verwenden |

### 1.7 Ausblick: native App und Widgets

Geplant ist eine eigene App. Das Konzept ist darauf zugeschnitten:

- **Push** läuft schon über eine kanalneutrale Tabelle; die App registriert ihr Gerät dort.
- **Widgets** (iOS/Android) zeigen pro Lieblingsspot **nur Daten**: Spotname, Wind jetzt, Böe, Richtungspfeil, eine Mini-Windleiste der nächsten 12 Stunden in der `windScale`-Farbe, bei ablandig das rote Ausrufezeichen. Kein Score, keine Bewertung. Größen: klein (1 Spot), mittel (1 Spot + 12 h), groß (3 Spots).
- Dafür braucht die API einen schlanken Endpunkt `GET /widgets/spots?ids=…` mit genau diesen Feldern, stark cachebar. Den kann die PWA schon vorher nutzen (Offline-Fallback, 6b).

**Akzeptanz:** Ein Nutzer richtet in unter 30 s einen Wecker ein, ohne ein Feld leer
zu sehen; keine Nachricht verletzt Frequenz- oder Ruhezeitregeln (Unit-Tests).

---

## 2. Was der Wind an diesem Spot bedeutet

**Problem:** „18 kn aus NW“ sagt nicht, ob NW hier auflandig, ablandig oder
überhaupt fahrbar ist (Hauptschmerz laut KiteReady). Dazu Ebbe.

### 2.1 Grundsatz (entschieden)

Kein Ampelsystem. Wir zeigen, was eine **Eigenschaft des Spots** ist und für jeden
Nutzer gleich gilt: Lage der Küste, nutzbare Richtungen, Tide. Das Urteil trifft
der Nutzer.

Die einzige Hervorhebung ist **ablandiger Wind**: ein rotes Ausrufezeichen-Icon
und ein sachlicher Satz. Das ist eine Sicherheitsinfo, keine Bewertung, und
verträgt sich mit E1.

```
!  Ablandig. Der Wind weht vom Strand aufs Wasser.
```

### 2.2 Kompass mit Spotsektoren (Daten-Tab)

Der bestehende `CompassDial` bekommt eine zweite, ruhige Ebene:

```
            N
       ·  ·  ·  ·
    ·  ░░░░░░░░░   ·        ░  nutzbar an diesem Spot
   ·  ░░░░░░        ·       ▒  ablandig (schraffiert)
  W   ░░░░  ↗        O
   ·          ▒▒▒   ·       ↗  Wind jetzt / gewählte Stunde
    ·       ▒▒▒▒▒  ·
       ·  ·  ·  ·
            S
  ─────────────────────────
  Aus SW · 225°
  Seitlich auflandig
```

- Sektoren als feine Ringsegmente innerhalb des Tick-Rings, `--sw-line`-Ton, nicht farbig. Der ablandige Bereich ist fein schraffiert, ebenfalls ohne Farbe.
- Die Bildunterschrift unter dem Kompass (heute „Aus SW“) bekommt eine zweite Zeile mit der **Lage zur Küste**: auflandig, seitlich auflandig, sideshore, seitlich ablandig, ablandig. Berechnet aus `facing` und Windrichtung. Normale Textfarbe.
- Nur bei „ablandig“ (und „seitlich ablandig“) steht davor das **rote Ausrufezeichen**, und die Zeile wird zum Satz: „! Ablandig. Der Wind weht vom Strand aufs Wasser.“ Sonst keine Farbe.

### 2.3 Meteogramm: Richtungszeile mit Kontext

Die RICHT-Zeile in `MeteoChart` zeigt heute Pfeile. Ergänzung: Über ablandigen
Stunden steht ein kleines rotes Ausrufezeichen (10 px) statt des Pfeils bzw. darüber.
**Keine Stunde wird gedimmt oder ausgegraut**, auch nicht außerhalb der nutzbaren
Sektoren; das wäre ein Eingriff in die Entscheidung. Beim Antippen einer
ablandigen Stunde erscheint der Satz aus 2.1 in der Auswahl-Caption. Ein Satz im
`sr-only`-Text beschreibt es für Screenreader.

### 2.4 Tide kommt zurück (entschieden)

`TidePanel` wurde beim Figma-Umbau entfernt. Die Tide kommt zurück, und zwar
**für alle Spots mit Tidedaten**, nicht nur für tideabhängige. Form: eine
zusätzliche schmale Zeile im Meteogramm, damit sie mit Wind und Welle in
derselben Zeitachse steht:

```
WELLE   ▂▃▃▄▄▅▅▄▃
WIND    ▃▄▆▇▇▆▅▄▃
RICHT   ↗↗↗→→→↘↘↘
TIDE    ‾‾╲__╱‾‾‾╲_      ← Spots mit Tidedaten
ZEIT    09 10 11 12 13
```

Eine Kurve, keine Zahlen in der Zeile; Hoch- und Niedrigwasserzeit als
Caption beim Antippen (gleiche Auswahl-Logik wie die übrigen Zeilen).
Zusätzlich in `TodaySummary` unter Wind/Böe/Welle eine vierte Zeile
„Hochwasser 14:12 · Niedrigwasser 20:31“ für den gewählten Tag. Ist der Spot
tideabhängig, steht die Spotinfo als Satz darunter, z. B. „Hier meist erst ab
halber Tide genug Wasser.“ (aus `variant_conditions.tide`). Keine Bewertung der
einzelnen Stunden. Datenquelle: der vorhandene Tide-Worker (`docs/tides.md`).

### 2.5 Backend

`facing` wird öffentlich ausgeliefert. Die **nutzbaren Richtungen** liegen nur im
Wetterprofil (`SpotWeatherProfile`) und sind nicht öffentlich. Neu: im öffentlichen
Spot-Schema ein Feld `usable_sectors: [[from, to], …]` (nur Geometrie, kein Score).
Frontend-Typ in `lib/api.ts` synchron halten.

---

## 3. Vorhersage-Sicherheit

**Problem:** Erfahrene Nutzer vergleichen Modelle bei Windguru, alle anderen wissen
nicht, welcher Zahl sie trauen sollen.

### 3.1 Darstellung

Ein Satz, kein Balken, keine Prozentzahl. Steht im Daten-Tab direkt unter der
Tagesleiste, für den gewählten Tag:

```
SA 12.10.
Sicher. Die Modelle sind sich einig.

SO 13.10.
Unsicher. Wind zwischen 12 und 22 kn möglich.
```

Drei Stufen, als Sprache formuliert:

| Stufe | Text | Grundlage |
|---|---|---|
| sicher | „Die Modelle sind sich einig.“ | geringe Modellspreizung, kurze Vorlaufzeit |
| mittel | „Kleine Abweichungen zwischen den Modellen.“ | — |
| unsicher | „Wind zwischen X und Y kn möglich.“ | große Spreizung oder lange Vorlaufzeit |

Zusätzlich, wo die Kalibrierung an Messstationen vorliegt (WP6), in der Fußzeile des Tages:
„Hier verglichen mit der Station Kiel-Leuchtturm.“ Das ist ein Vertrauenssignal, das
keiner der Konkurrenten so zeigt.

### 3.2 Visuelle Spreizung im Meteogramm (optional)

Bei „unsicher“ bekommt der Windbalken einen feinen hellen Schatten nach oben bis
zum oberen Ende der Spanne. Keine eigene Farbe, nur Opazität. Erst bauen, wenn der
Satz allein nicht reicht.

### 3.3 E1 und Backend

Die Sicherheit beschreibt die **Vorhersage**, nicht den Spot oder die Passung zum
Nutzer. Sie ist zwar ein Bestandteil des internen Nutzwerts (Confidence), wird aber
hier unabhängig davon aus der Modellspreizung berechnet.

> **Entscheidung nötig (E1):** Gilt ein Satz über die Vorhersage-Sicherheit als
> erlaubt? Vorschlag: ja.

Backend: Forecast-Response um `days[].confidence: "high" | "medium" | "low"`
und `days[].wind_range_kt: [lo, hi]` erweitern. Quelle: Modellspreizung,
Vorlaufzeit, Verifikationsfehler des Spots (`weather_verification`). Vor dem Bau
prüfen, ob die Spreizung je Spot und Tag heute schon berechnet wird oder ob dafür
mehrere Modelle parallel abgefragt werden müssen.

---

## 4. Vor Ort: Regeln, Zonen, Einstieg

**Problem:** „Eine Pin auf der Karte erzählt nicht die ganze Geschichte.“ An der
deutschen Küste kommen Befahrensverordnungen, Kite-Vorrangzonen,
Naturschutzgebiete und Lizenzpflicht dazu. Das bietet kein internationaler
Anbieter sauber.

### 4.1 Platzierung

Neuer Abschnitt im **Info-Tab**, zwischen `SpotMetaGrid`/`Facilities` und der
Lagekarte. Überschrift in derselben Grammatik wie die übrigen Info-Blöcke.

```
─────────────────────────────────────────
VOR ORT

Regeln
  Der Spot liegt im Nationalpark
  Niedersächsisches Wattenmeer.
  Kiten ist hier nur in ausgewiesenen
  Bereichen erlaubt.
  Quelle: NordSBefV, Stand 27.04.2023 ↗

Einstieg
  Über die Wiese hinter dem Deich.

  !  Buhnen in der Nähe des Einstiegs.
─────────────────────────────────────────
```

- Zwei feste Unterpunkte, **jeder nur sichtbar, wenn befüllt**: Regeln, Einstieg.
- Gefahren bekommen keinen eigenen farbigen Block, sondern das einheitliche Muster: **rotes Ausrufezeichen + ein Satz**, eingereiht unter dem passenden Unterpunkt.
- „Regeln“ trägt immer **Quelle und Stand** (Link nach außen). Ohne Quelle wird nichts veröffentlicht. Das ist rechtlich und für das Vertrauen wichtig.
- Formulierung immer beschreibend („liegt im …“, „gilt …“), nie anweisend („fahr hier nicht“).
- Auf der Windkarte: Spots mit saisonaler Sperre zeigen im Spot-Info-Sheet eine Zeile „Saisonal eingeschränkt bis 31.10.“ Keine Zonen-Polygone in Phase 1 (Datenpflege zu teuer, Haftungsrisiko).

### 4.2 Datenmodell

`variant_conditions` enthält bereits `local_rules`, `hazards`, `entry` je Variante.
Für sportübergreifende Regeln (Badezone, Naturschutz) ein neues Spot-Feld:

```json
"rules": [
  {
    "kind": "zone | seasonal | license | nature | other",
    "text": "Kiten nur in der ausgewiesenen Zone …",
    "valid_from": "04-01", "valid_to": "10-31",
    "sports": ["kitesurf", "wingfoil"],
    "source_name": "Gemeinde Dornum",
    "source_url": "https://…",
    "checked_at": "2026-04-27"
  }
]
```

Zusätzliches Feld `origin: "auto" | "community" | "admin"` und bei automatischen
Einträgen `source_key` + `source_version` (wie im Geodaten-Register).

### 4.3 Automatisierung (entschieden)

Die Regeln werden **automatisch** erzeugt und aktuell gehalten. Vorbild ist die
bestehende Geodaten-Pipeline (`app/forecast/geodata_catalog.py`,
`docs/geodata-phase1.md`): versioniertes Quellenregister, Cache, Preflight,
erst Schattenbetrieb, dann Aktivierung.

**Ablauf je Spot**

1. **Verschneiden:** Spotpunkt und die vorhandene Start-/Wassergeometrie werden mit
   den Schutzgebiets- und Befahrensgeometrien verschnitten (PostGIS).
2. **Satz erzeugen:** Aus jedem Treffer entsteht ein Regeleintrag aus festen
   Textbausteinen je Gebietsart, z. B. „Der Spot liegt im Naturschutzgebiet
   {name}. Hier gelten Befahrensregeln.“ plus Link auf die Verordnung. Keine
   freie Textgenerierung, damit nichts Falsches behauptet wird.
3. **Saisonale Sperren:** Wo die Quelle Zeiträume strukturiert liefert
   (Befahrensverordnungen mit Anlagen), werden `valid_from`/`valid_to` übernommen.
   Liefert die Quelle nur Fließtext, bleibt es beim Hinweis mit Link.
4. **Gefahren aus OSM:** Buhnen (`man_made=groyne`), Hafeneinfahrten,
   Fahrwasser (`seamark:type=fairway`) im Umkreis von 300 m um den Einstieg
   ergeben je einen Satz mit Ausrufezeichen.
5. **Aktualität:** wöchentlicher Abruf je Quelle, Vergleich per Hash. Ändert sich
   eine Quelle, wird neu verschnitten; der „Stand“ im UI folgt automatisch.
   Fällt eine Quelle aus, bleibt der letzte Stand mit Datum sichtbar.
6. **Admin nur für Ausnahmen:** Das Dashboard zeigt neue oder geänderte
   automatische Einträge in einer Liste zum Durchsehen, blockiert die
   Veröffentlichung aber nicht. Ein Admin kann einen Eintrag ausblenden
   (`hidden_reason`), wenn die Verschneidung offensichtlich falsch ist.

**Quellen**

| Quelle | Inhalt | Lizenz / Hinweis |
|---|---|---|
| Befahrensverordnungen (NordSBefV, Ostsee-Verordnungen für Schleswig-Holstein und Mecklenburg-Vorpommern) über gesetze-im-internet.de | Kitezonen, Sperrgebiete, Zeiträume | Amtliche Werke, gemeinfrei (§ 5 UrhG). Zonen aus den Anlagen einmalig als Geometrie erfassen, danach automatischer Änderungsabgleich |
| Schutzgebiete der Länder (WFS, gebündelt über BfN/GDI-DE) | NSG, Nationalparks, LSG | Meist Datenlizenz Deutschland; **je Land prüfen**, weil die Länder unterschiedlich lizenzieren |
| Natura 2000 (EEA) | FFH- und Vogelschutzgebiete europaweit | Lizenz vor Einbindung prüfen |
| OpenStreetMap | Schutzgebiete als Rückfall, Buhnen, Seezeichen | ODbL, Namensnennung |
| ~~WDPA / Protected Planet~~ | — | **Nicht nutzbar:** Nutzung durch kommerzielle Anbieter nur mit schriftlicher Genehmigung |

**Was nicht automatisierbar ist:** Gemeinderegeln, die nur als PDF vorliegen (etwa
das Kite-Regelwerk von Dornum). Diese kommen über Community-Vorschläge
(`SuggestEditButton`, neue Kategorie „Regel“, Pflichtfeld Quelle) und durchlaufen
die bestehende Moderation. Der wöchentliche Link-Check aus 4.3 Schritt 5 gilt
auch für sie.

**Startumfang:** deutsche Nord- und Ostseeküste, danach Europa über Natura 2000 und OSM.

---

## 5. Reiseplanung: „Wo geht es wann?“

**Problem:** Niemand beantwortet gut, wohin man im März fahren sollte.
**Bestand:** Windmonate (Klimatologie), `best_months`, WANN-Achse in der Suche,
Landing-Reihe „Topspots in der nächsten Zeit“.

Die Bausteine sind da, sie sind nur nicht als Reise-Erlebnis verbunden. Alles
in diesem Abschnitt wird **automatisch** aus der Klimatologie berechnet;
redaktionelle Pflege ist nicht nötig. `best_months` wird nach jedem
Klimatologie-Lauf neu berechnet (`aggregate_spot_best_months`), Regionsbänder
aggregieren automatisch, die Monatszeile der Landing startet immer beim
nächsten Monat.

### 5.1 Monatsband auf Spot und Region

Im Info-Tab ersetzt ein kleines **Monatsband** die heutige Textzeile „Beste Saison“
in `SpotMetaGrid`:

```
SAISON
J  F  M  A  M  J  J  A  S  O  N  D
·  ·  ▪  ▪  ▪  ▪  ▪  ·  ▪  ▪  ·  ·
                       → Windmonate
```

- Zwölf Kästchen, gefüllte = beste Monate (`best_months`). Kein Farbverlauf, kein Prozent.
- Tap führt in den Daten-Tab zum Windmonate-Modul.
- Gleiches Band auf `RegionTile` und der Regionsseite (aggregiert).

### 5.2 Monatssuche als Einstieg

Auf der Landing unter der Suche eine leise Zeile mit Monatsnamen, horizontal scrollbar:

```
WOHIN IM …
Nov   Dez   Jan   Feb   Mär   Apr   →
```

Tap auf einen Monat führt auf `/search` mit gesetzter WANN-Achse. Kein neuer
Screen nötig, nur ein neuer, schnellerer Einstieg. Vor dem Bau prüfen, ob die
Ergebnisseite bei reiner WANN-Suche über die Klimatologie rankt (wie die Surface
`season`); falls nicht, dort angleichen.

### 5.3 Reise-Kontext in der Ergebnisliste

Bei aktiver WANN-Suche zeigt `SpotCard` statt der Live-Windzahl die Zeile
„Im März meist 4–5 Bft“ (Median aus Klimatologie). Fakt, kein Score.

---

## 6. Vertrauen und Zugang

### 6a. Haltung sichtbar machen

**Problem:** Werbung und Bezahlschranken-Creep machen zusammen 42 % der
Beschwerden über Wetter-Apps aus. Surfline hat Magicseaweed abgeschaltet.

- **Über uns** bekommt einen kurzen editorialen Block mit drei Sätzen:
  „Keine Werbung. Kein Abo für Vorhersage, Spots und Wecker. Wir sagen dir, woher unsere Daten kommen.“
- **Footer:** dieselbe Haltung in einer Zeile, `text-caption text-muted`.
- **Neue Seite „Wie wir vorhersagen“** (`/methode`), verlinkt aus FAQ, Daten-Tab-Fuß und Über uns:
  Modelle, Kalibrierung an Stationen, was „sicher/unsicher“ bedeutet, was wir bewusst nicht tun (keine erfundenen Foil-Schwellen, keine Scores). Editoriales Layout `max-w-measure`, keine Grafik außer einem Beispiel-Meteogramm.
- **Kein „Pro“-Schriftzug, kein Schloss-Symbol** irgendwo im öffentlichen UI.

### 6b. Installierbar machen (PWA)

Voraussetzung für Push (Punkt 1) und für die Nutzung am Strand.

- `manifest.webmanifest`: Name „surfwinddata“, `display: standalone`, `theme_color` = Seitenfläche `#F8F6F2`, Icon aus dem Wordmark/Favicon (maskable 512 px).
- Service Worker: **nur** Push-Empfang und ein Offline-Fallback für die zuletzt angesehenen Spots (Vorhersage aus dem Cache mit Hinweis „Stand 07:00“). Kein aggressives Caching der App-Shell, damit Deploys sofort ankommen.
- Installations-Hinweis **nur im Burger-Menü**, als letzte Zeile über dem Rechtlichen: „Auf den Homescreen“, mit kurzer Anleitung für iOS (Teilen › Zum Home-Bildschirm). Kein Banner.
- iOS-Hinweis im Wecker-Sheet: Push auf dem iPhone geht nur, wenn die Seite installiert ist (iOS ≥ 16.4). Ist sie nicht installiert, zeigt das Sheet statt des Speichern-Knopfs die kurze Installationsanleitung.
- Die PWA ist die **Brücke zur nativen App**: gleiche Push-Tabelle, gleicher Widget-Endpunkt (1.7). Sobald die App erscheint, verweist der Menüeintrag „Auf den Homescreen“ auf die App-Stores.

---

## 7. „Wie war's?“ nach der Session

**Problem:** Wir brauchen Wahrheitssignale (Stufe B der Wecker, Kalibrierung des
persönlichen Scorings). Surfr misst Sprünge, wir messen, ob die Vorhersage
gestimmt hat.

**Bestand:** `VisitedButton` sendet `session_checkin` **ohne** `outcome`. Das
Backend akzeptiert `worthwhile` / `not_worthwhile` bereits.

### 7.1 Ablauf

Nach Tap auf „Besucht“ klappt unter der Aktionsreihe eine einzige Zeile auf:

```
( ♡ )  ( ↗ )  (●⌖)  ( ✎ )
─────────────────────────────────────────
Hat es sich gelohnt?
[ Ja ]  [ Nein ]
─────────────────────────────────────────

nach „Nein“, optional:
Der Wind war …
[ schwächer ]  [ wie angesagt ]  [ stärker ]
─────────────────────────────────────────
Danke. Das macht die Vorhersage hier besser.
```

- Zwei Taps maximal, alles optional, kein Freitext (Freitext gehört in die Community-Tipps).
- Die Dankeszeile verschwindet nach 3 s. Kein Konfetti.
- Daten: `context.outcome` (bestehend) plus neu `context.wind_vs_forecast: "weaker" | "as_forecast" | "stronger"` (Validator in `app/api/events.py` erweitern).

### 7.2 Rückfrage per Push (entschieden: standardmäßig an)

Wurde ein Wecker ausgelöst und der Nutzer hat den Daten-Tab des Spots geöffnet,
kommt am Folgetag um 19 Uhr einmalig eine Push-Nachricht mit drei Aktionen:

```
Warst du gestern in Laboe?
[ Ja, hat sich gelohnt ]  [ Nein ]  [ Nicht mehr fragen ]
```

- Die Antwort lässt sich direkt in der Benachrichtigung geben (Notification Actions), ohne die App zu öffnen.
- **„Nicht mehr fragen“** schaltet Rückfragen dauerhaft ab, für alle Spots, und setzt den Schalter in Einstellungen › Benachrichtigungen auf aus. Dort lässt er sich wieder einschalten.
- Dieselbe Rückfrage erscheint auch in der Web-Oberfläche, wenn der Nutzer den Spot am Folgetag öffnet: als Inline-Zeile über der Aktionsreihe mit denselben drei Knöpfen, statt der Push-Nachricht, falls diese nicht beantwortet wurde. Nie beides am selben Tag.
- Keine Rückfrage ohne vorher ausgelösten Wecker. Höchstens eine Rückfrage pro Tag.

### 7.3 Was der Nutzer davon hat

Im Konto unter **Spots besucht** (heute „kommt bald“) erscheint die Liste der
Check-ins: Spot, Datum, „gelohnt“. Damit bekommt die Seite endlich Inhalt.
Keine Statistiken, keine Ranglisten.

---

## 8. Webcams

**Problem:** Webcams sind bei Surfr und Surfline ein Hauptgrund für die Nutzung.

### 8.1 Darstellung

Verlinken, **nicht einbetten** (Lizenz, Performance, Fremd-Tracking).

Info-Tab, im Abschnitt „Vor Ort“ (Punkt 4) als letzter Unterpunkt, oder bei
Spots ohne Regeln direkt unter der Galerie:

```
WEBCAMS
Strand Laboe, Blick nach Norden      ↗
Hafen Laboe                          ↗
```

Daten-Tab: neben dem bestehenden „Karte“-Link im Kopf ein zweiter Link
„Webcam ↗“, wenn genau eine Kamera hinterlegt ist; sonst Sprung zum Info-Block.

### 8.2 Daten

Spot-Feld `webcams: [{label, url, source_name, direction?}]`, im Admin pflegbar.
Ein wöchentlicher Link-Check (HEAD-Request) markiert tote Links im Admin; tote
Links werden öffentlich ausgeblendet. Community-Vorschläge über den bestehenden
„Bearbeiten“-Flow (`SuggestEditButton`) mit neuer Kategorie „Webcam“.

---

## 9. Was bewusst nicht gebaut wird

| Nicht bauen | Warum |
|---|---|
| GPS- oder Sprung-Tracking | Surfr, Woo und Waterspeed besetzen das; hoher Akkuverbrauch ist dort Hauptkritik |
| Eigener Modellvergleich als Tabelle | Windguru macht das besser; wir übersetzen ihn in einen Satz (Punkt 3) |
| Spot-Chat | Moderationsaufwand; Community-Tipps reichen |
| Zonen-Polygone auf der Karte | Pflegeaufwand und Haftung; zuerst Text mit Quelle (Punkt 4) |
| Score, Ampel, „Match 87 %“ | Produktentscheidung E1 |
| Installations- oder Push-Banner | widerspricht der ruhigen Haltung |

---

## 10. Reihenfolge und Aufwand

Abhängigkeiten bestimmen die Reihenfolge: PWA vor Push, Check-ins vor Stufe B.

| Phase | Inhalt | Aufwand (grob) | Warum jetzt |
|---|---|---|---|
| **1 · Fundament** | 7.1 Check-in mit Outcome · 6a Haltung + `/methode` · 8 Webcams · 5.1 Monatsband · 2.4 Tide zurück | S–M | wenig Risiko, sofort sichtbar, startet die Datensammlung für Stufe B |
| **2 · Spotwissen** | 2.2/2.3 Kompass-Sektoren, Lage zur Küste, rotes Ausrufezeichen bei ablandig · 4 Vor Ort mit automatischer Regel-Pipeline (Schatten, dann aktiv; deutsche Küste) | M–L | Alleinstellungsmerkmal; die Pipeline folgt dem Geodaten-Muster |
| **3 · Wecker A** | 6b PWA · 1 Spot-Wecker (eigene Regel), nur Web-Push · 7.2 Rückfrage mit „Nicht mehr fragen“ · Widget-Endpunkt | L | größter Nutzerhebel; kein Mail-Provider nötig |
| **4 · Einordnung** | 3 Vorhersage-Sicherheit · 5.2/5.3 Monatssuche | M | baut auf Multi-Model-Daten auf |
| **5 · App** | native App mit Push (APNs/FCM) und Widgets auf derselben API | L | eigenes Projekt |
| **6 · Wecker B** | „Für dich“-Benachrichtigungen aus der Engine | M | erst nach bestandener Bereitschaftsprüfung (8 Wochen, 200 Check-ins) |
| später | E-Mail-Kanal | S | erst wenn ein Mail-Provider gewählt ist |

---

## 11. Entscheidungen

| # | Thema | Entscheidung (12.10.2026) |
|---|---|---|
| 1 | Ablandig (Punkt 2) | Kein Ampelsystem. Rotes Ausrufezeichen-Icon + ein sachlicher Satz. Nie vorschreiben, nur informieren. Gilt als einziges Warnmuster der ganzen App. |
| 2 | Vorhersage-Sicherheit (Punkt 3) | **offen** – Vorschlag: ein Satz pro Tag, verträgt sich mit E1 |
| 3 | Mail-Provider (Punkt 1) | Später. Zuerst Push über die PWA, danach native App mit Push und Widgets. |
| 4 | Tide (Punkt 2.4) | Kommt zurück: Meteogramm-Zeile + Hoch-/Niedrigwasser in `TodaySummary`, für alle Spots mit Tidedaten. |
| 5 | Pflege der Regeln (Punkt 4) | Automatisiert über eine Geodaten-Pipeline (4.3). Admin nur für Ausnahmen, Community für Gemeinderegeln aus PDFs. |
| 6 | Rückfrage am Folgetag (Punkt 7.2) | Standardmäßig an, mit Knopf „Nicht mehr fragen“. |
