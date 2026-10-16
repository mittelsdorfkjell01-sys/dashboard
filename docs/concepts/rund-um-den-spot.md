# Konzept: Rund um den Spot

Stand: 15. Oktober 2026. Dieses Dokument ist ein Produkt-, UI- und Datenkonzept,
keine Implementierung. Es gilt nur für die öffentliche Seite (surfwinddata),
nicht für das Admin-Dashboard. Es baut auf `docs/concepts/differenzierung-8-punkte.md`
auf und übernimmt dessen Leitplanken (Abschnitt 0.2) unverändert.

---

## 0. Worum es geht

### 0.1 Vision in einem Satz

> **surfwinddata sagt dir, wann der Spot läuft, und was du dort machst, wenn du nicht auf dem Wasser bist.**

Heute endet das Tool an der Wasserkante: Wind, Welle, Tide, Spotwissen,
Ausstattung am Strand. Eine Surf-, Kite- oder Wingreise besteht aber zu mehr
als der Hälfte aus Land: Wo schlafe ich, wo gibt es Frühstück nach der Session,
wo ist der Surfshop, wenn die Finne bricht, was mache ich am Flautentag, wo
trifft man abends die anderen?

Ziel ist ein **Rundum-Paket pro Spot**, ohne dass surfwinddata zu einem
Buchungsportal, einer Bewertungsplattform oder einem Reiseführer mit tausend
Einträgen wird.

### 0.2 Was das Feature ist und was nicht

| Ist | Ist nicht |
|---|---|
| Ausgewählte Orte rund um einen Spot, aus Sicht von Wassersportlern | Ein vollständiges Branchenbuch („alle 214 Restaurants in Westerland“) |
| Fakten: Entfernung, Art, Öffnungszeiten, was der Ort für Surfer bietet (Boardraum, Van-Stellplatz, Verleih) | Sterne, Scores, „Top 10“, „Match 92 %“ (Produktentscheidung E1 gilt) |
| Community-Tipps mit einem Satz, warum der Ort gut für Surfer ist | Freitext-Bewertungen von Unternehmen (Haftung, Moderation) |
| Links nach außen zum Buchen oder zur Route | Eigene Buchungsstrecke, Preisvergleich, Verfügbarkeitskalender (erst Phase 5, und nur als Link) |
| Ehrlich: Was wir nicht wissen, zeigen wir nicht | Lückenfüller mit generischen Stockfotos oder KI-Texten |

### 0.3 Warum das zu surfwinddata passt

1. **Es ist Spotwissen.** „Der Kiosk am Einstieg öffnet um 8 Uhr“ ist dieselbe
   Art Wissen wie „Einstieg über die Wiese hinter dem Deich“ (Konzept 8 Punkte,
   Abschnitt 4). Die Konkurrenz (Windfinder, Windguru, Windy) hat das gar nicht;
   Surfline nur am Rand; Booking/Airbnb kennen keine Spots.
2. **Es verbindet sich mit den Daten, die nur wir haben.** Eine Unterkunft wird
   für Wassersportler erst durch Fragen wie „Welche Spots erreiche ich von hier
   in 20 Minuten?“ und „Läuft im März überhaupt etwas?“ interessant. Beides kann
   nur surfwinddata beantworten (Spotkatalog + Windklimatologie + `best_months`).
3. **Es nutzt vorhandene Bausteine:** `Facilities`, Community-Tipps mit Upvotes,
   Moderation, `SuggestEditButton`, Bildlizenz-Pipeline, Geodaten-Pipeline mit
   Quellenregister, `PrefsContext`-Einheiten, `SectionBand`-Grammatik.

---

## 1. Ausgangsbestand im Code

| Ort | Heute | Relevanz |
|---|---|---|
| `SpotDetail.tsx` · Info | Dreispalter: Identität + Beschreibung + Aktionsreihe · Galerie · `SpotMetaGrid` + `Facilities` (`variant="list"`); darunter Lagekarte (`LocatorMap`, Esri-Luftbild), `SpotCommentBox`, `SimilarSpots` | Hauptort für das neue Modul |
| `Facilities.tsx` | Fünf feste Arten: `parking`, `school`, `shower`, `food`, `camping`, drei Zustände (vorhanden, nicht vorhanden, keine Angabe) | Bleibt „Am Spot“; neue Orte sind „In der Nähe“ |
| `spots.facilities` (JSONB) | `{kind: {available, note}}` | Kann künftig auf einen verknüpften Ort zeigen |
| `RegionDetail.tsx` | Hero, Lede, „Top in {Region}“, „Wann hinfahren“, „Auf der Karte“ | Natürlicher Ort für Unterkünfte (man schläft in einem Ort, fährt aber mehrere Spots) |
| `/map` (`SpotExplorer` ⟷ `WindExplorer`) | Genau **eine** öffentliche Wetterkarte | Kein neuer Kartentyp; höchstens eine zusätzliche Ebene in `SpotExplorer` |
| `LocatorMap` | Einzige zweite Karte: Luftbild mit Spot-Pin, Klick-zum-Aktivieren | Optional ein zweiter Pin-Typ (Phase 4) |
| Community (`LocalTip`, `SpotRating`, `CommunityUpvote`, `SpotSubmission`) | Tipps mit Titel/Text, Upvotes, Moderation, Vorschläge | Ort-Tipps und Ort-Vorschläge sind eine Erweiterung, kein Neubau |
| Konto | Saved (Spots), Spots besucht, Spots hinzufügen | „Saved“ kann Orte aufnehmen |
| `lib/units.ts` | `distanceValue(km, unit)` km/mi | Entfernungen sofort in der richtigen Einheit |
| i18n | react-i18next, Tranchen, Lint-Guard pro Datei | Neues Modul startet direkt mit Katalog-Keys |
| Geodaten-Pipeline | Quellenregister, Cache, Preflight, Schatten → Aktivierung | Vorbild für den POI-Import |

---

## 2. Die Kategorien

Wenige, feste Kategorien in der Sprache von Wassersportlern. Jede Kategorie hat
eine feste Reihenfolge, ein Icon in `lib/icons.tsx` und eine Liste von Quell-Tags.
Mehr Kategorien = mehr Rauschen; die Liste ist bewusst kurz.

| Kategorie (UI) | Key | Unterarten | Typische Quell-Tags (OSM) | Was Surfer daran interessiert |
|---|---|---|---|---|
| **Schlafen** | `stay` | Hostel, Surfcamp, Camping, Van-Stellplatz, Ferienwohnung, Hotel | `tourism=hostel|camp_site|caravan_site|guest_house|apartment|hotel` | Boardraum, Waschplatz für Neopren, Van-tauglich, Entfernung zum Einstieg |
| **Essen & Trinken** | `eat` | Frühstück/Café, Strandbar, Restaurant, Imbiss | `amenity=cafe|restaurant|fast_food|bar|pub|biergarten` | Früh offen (vor der Morgensession), nach der Session warmes Essen, Terrasse mit Blick aufs Wasser |
| **Abends** | `night` | Bar, Strandbar, Live-Musik, Club | `amenity=bar|pub|nightclub`, `live_music=yes` | Wo sich die Szene trifft |
| **Gear & Service** | `gear` | Surfshop, Verleih, Reparatur, Schule | `shop=surf|water_sports|sports`, `sport=surfing|kitesurfing` + `office`/`shop` | Finne gebrochen, Leash vergessen, Wing leihen, Kurs |
| **Ohne Wind und Welle** | `flat` | Yoga, Skatepark, Wandern, Sauna/Bad, Kultur, SUP-/Kajaktour, Kletterhalle | `leisure=sports_centre|fitness_centre|sauna`, `sport=yoga|skateboard|climbing`, `tourism=attraction|museum|viewpoint` | Der Flautentag |
| **Praktisch** | `basics` | Supermarkt, Bäcker, Tankstelle, Entsorgung (Wohnmobil), Apotheke, Wasserstelle | `shop=supermarket|bakery`, `amenity=fuel|sanitary_dump_station|pharmacy|drinking_water` | Van-Leben, Proviant, Notfall |

**Merkmale (Attribute) statt Bewertungen.** Statt „4,6 Sterne“ zeigt ein Ort
Fakten, die für Surfer relevant sind. Feste Liste, jedes Merkmal ein Wort:

| Merkmal | Key | Herkunft |
|---|---|---|
| Boardraum | `board_storage` | Community, Partner |
| Neopren-Dusche/Waschplatz | `rinse` | Community, Partner |
| Van-tauglich | `van_ok` | OSM (`caravans=yes`, `motorhome=yes`), Community |
| Früh offen | `early` | abgeleitet aus `opening_hours` (öffnet ≤ 8 Uhr) |
| Verleih | `rental` | OSM (`rental=*`), Community |
| Blick aufs Wasser | `sea_view` | Community |
| WLAN | `wifi` | OSM (`internet_access=wlan`) |
| Hunde willkommen | `dogs` | OSM (`dog=yes`) |
| Barrierearm | `wheelchair` | OSM (`wheelchair=yes`) |

Ein Merkmal erscheint nur, wenn es belegt ist. Unbekannt wird nicht angezeigt,
„nein“ nur, wenn es explizit so in der Quelle steht. Das ist dieselbe Logik wie
heute bei `Facilities` (vorhanden / nicht vorhanden / keine Angabe), nur
umgekehrt gewichtet: bei Orten zeigen wir Unbekanntes gar nicht, weil sonst jede
Zeile voller „Keine Angabe“ stünde.

---

## 3. Zwei Ebenen: kuratiert und automatisch

Das ist die wichtigste Konzeptentscheidung. Offene Datenquellen liefern Masse,
aber keinen Surf-Bezug. Community und Redaktion liefern Surf-Bezug, aber keine
Masse. Beides wird getrennt dargestellt, damit nie ein Branchenbuch-Gefühl
entsteht.

| | **Tipps** (kuratiert) | **In der Nähe** (automatisch) |
|---|---|---|
| Herkunft | Community-Tipp mit Ortsbezug, Redaktion, verifizierter Partner | OpenStreetMap, Overture Places |
| Darstellung | Editorial im Abschnitt selbst: **eine Leitgeschichte + drei Geschichten**, jede mit Foto, Schlagzeile, kurzem Text, Fakten und dem Tipp-Satz (Abschnitt 4.2) | Kompakte Liste hinter „Alle Orte in der Nähe“: Name, Art, Entfernung, ggf. „offen bis 22 Uhr“ |
| Sortierung | Auswahlregel (Abschnitt 3.1) | Entfernung, gruppiert nach Kategorie |
| Menge | **höchstens vier** im Abschnitt | alle, aber nur im Sheet |
| Sichtbarkeit | sofort nach Moderation | sofort nach Import (Schattenphase vorher), Admin blendet nur Ausnahmen aus |
| Quelle sichtbar | „Tipp von Lena · 12 hilfreich“ | „Daten: OpenStreetMap“ in der Fußzeile des Moduls |

Ein Ort kann in beiden Ebenen vorkommen: Hat die Community einen OSM-Ort als
Tipp markiert, wandert er aus „In der Nähe“ nach „Tipps“ und erscheint nicht
doppelt.

Qualität vor Menge: Im Abschnitt selbst steht **nie eine Liste**, sondern nur
die kuratierte Auswahl. Die automatische Ebene bleibt vollständig erreichbar,
aber einen Klick tiefer.

### 3.1 Auswahlregel für die vier Orte

Die Auswahl ist automatisch und nachvollziehbar, damit sie ohne Redaktion für
ganz Europa funktioniert und nie käuflich wirkt:

1. **Ein Ort pro Moment.** Vier feste Momente: *Draußen schlafen* (Surfcamp,
   Camping, Van-Stellplatz), *Drinnen schlafen* (Hostel, Ferienwohnung, Hotel),
   *Morgens* (Café, Bäckerei, Frühstück), *Abends* (Strandbar, Bar, Restaurant).
   Gibt es für einen Moment keinen geeigneten Ort, bleibt der Platz leer; es
   wird nicht aufgefüllt.
2. **Die meisten „hilfreich“-Stimmen gewinnen**, bei Gleichstand der nähere Ort.
   Der Ort mit den meisten Stimmen insgesamt wird die Leitgeschichte.
3. **Geeignet ist nur**, wer ein Foto aus der Community (mit Lizenzannahme) und
   einen freigegebenen Tipp aus den letzten 12 Monaten hat.
4. **Nicht käuflich:** Partner und Werbelinks haben keinen Einfluss.
5. **Wöchentliche Neuberechnung** (Cron hinter `RUN_MAINTENANCE_CRONS`), damit
   die Auswahl nicht bei jeder Stimme springt.

Die Regel steht öffentlich unter „So werden die Orte ausgewählt“ am Ende des
Abschnitts, zusammen mit den Kandidaten der Woche und dem Grund, warum sie
nicht gewählt wurden („weniger Stimmen“, „noch kein Foto“).

Weitere Momente (*Ohne Wind und Welle*, *Gear & Service*) können später als
fünfter Platz dazukommen; der Abschnitt bleibt aber bei höchstens vier Orten.

Der Startzustand eines Spots ohne Tipps ist **nicht leer**, sondern zeigt die
automatische Ebene plus eine leise Einladung „Kennst du einen Ort, der hier
fehlt? Tipp hinzufügen.“ Damit funktioniert das Feature vom ersten Tag an in
ganz Europa und wird mit der Community besser.

---

## 4. UI: Wo und wie es auftaucht

Alle Wireframes sind für 390 px gedacht. Desktop ist dieselbe Struktur im
breiteren Raster. Neue Oberflächen nutzen ausschließlich vorhandene Tokens
(`text-title`, `text-ui`, `text-caption uppercase tracking-caps text-muted`,
`border-line`, `bg-band`, Radius 14 px). Teal nur für den aktiven Zustand.

### 4.1 Überblick der Einstiege

| Ort | Was | Phase |
|---|---|---|
| Spot · Info | Neuer Abschnitt **„Rund um den Spot“** | 1 |
| Spot · Info · `Facilities` | Zeile „Am Spot“ kann einen verknüpften Ort nennen („Kiosk Strandgut“) | 1 |
| Ort-Sheet | Detailansicht eines Orts als Bottom-Sheet (mobil) / Seitenpanel (Desktop) | 1 |
| Regionsseite | Neuer Abschnitt **„Leben in {Region}“** mit Basislagern | 3 |
| Spot · Daten | Ein leiser Link „Ohne Wind und Welle →“ am Tagesende der Tagesleiste (Entscheidung offen, siehe 11) | 4 |
| `/map` · `SpotExplorer` | Orte als kleine Glyphen ab Zoom 13, nur wenn ein Spot ausgewählt ist | 4 |
| Konto · Saved | Gespeicherte Orte als zweite Gruppe unter den Spots | 2 |
| Suche | Filter „Unterkunft in Gehweite“ und „Van-Stellplatz in der Nähe“ | 3 |

### 4.2 Spot · Info: Abschnitt „Rund um den Spot“

**Platzierung:** nach der Gruppe Lagekarte/Community, vor `SimilarSpots`, als
eigenes `SectionBand tone="band"`. Damit bleibt der obere Dreispalter
(Identität, Galerie, Steckbrief) unverändert der Spot, und das Land darum
herum beginnt sichtbar dort, wo das Wasser endet. Erscheinen die Punkte „Vor
Ort“ und „Webcams“ aus dem 8-Punkte-Konzept, stehen sie *oben* bei der
Ausstattung (sie gehören zum Spot), „Rund um den Spot“ bleibt *unten* (es gehört
zur Umgebung).

Referenz-Entwurf: Artefakt „Rund um den Spot“
(https://claude.ai/artifact/LuzZXdhpa5aEfwPHBF1rqY), Version 3.

```
─────────────────────────────────────────
RUND UM DEN SPOT
Vor und nach der Session
Vier Orte rund um Fehmarn Gold, ausgesucht
aus den Tipps von Leuten, die hier fahren.

┌───────────────────────────────────────┐
│ [Foto 4:3 · „Draußen schlafen“]       │
└───────────────────────────────────────┘
DRAUSSEN SCHLAFEN · SURFCAMP
Vom Bulli aus sehen, ob es schon läuft
Kitecamp Nordhaken
Zwanzig Stellplätze hinter der Düne, …
ZUM EINSTIEG   SAISON       FÜR
0,4 km         Apr–Okt      Vans, Zelte
(J) „Boardraum, Frühstück ab 7 …“
    Jonas · August 2026 · 14 hilfreich
Mehr über den Ort ›

┌────────────┐ ┌────────────┐ ┌──────
│ Foto 4:5   │ │ Foto 4:5   │ │ Foto
│ Drinnen    │ │ Morgens    │ │ Abends
└────────────┘ └────────────┘ └──────
HOSTEL         CAFÉ           STRANDBAR
Hostel         Café           Bar
Möwennest      Brandungs-     Treibholz
Ein Satz.      läufer …
5,8 km · Aylin 1,1 km · Mia
          ● ━ ●   (mobil: wischen)

Alle 26 Orte in der Nähe ›   + Ort vorschlagen
ⓘ So werden die Orte ausgewählt
Orte: © OpenStreetMap · Texte und Fotos aus der Community
─────────────────────────────────────────
```

**Regeln für das Modul**

- **Keine Liste im Abschnitt.** Eine Leitgeschichte (Desktop: Foto 7/12, Text
  5/12; mobil: Foto oben) und drei Geschichten (Desktop: drei Spalten, leicht
  versetzt für editorialen Rhythmus; mobil: horizontales Wischen mit
  Scroll-Snap und Punkten). Höchstens vier Orte, Auswahl nach 3.1.
- **Fotos sind Pflicht** für die Auswahl (Community-Upload mit Lizenz, später
  Partner mit Lizenznachweis). Das Foto trägt den Moment als kleines Label
  oben links („Morgens“). Keine Logos, keine Fremd- oder KI-Bilder.
- **Text:** Schlagzeile in Satzform (nur Leitgeschichte), Name, zwei bis drei
  Sätze Beschreibung, bei den Karten ein Satz. Die Schlagzeile kommt aus dem
  Tipp bzw. der Moderation, nie aus freier Textgenerierung.
- **Fakten statt Urteil:** Entfernung, Saison/Öffnungstage, „Für“ (Vans,
  Gruppen …), Merkmale nur im Sheet. Der Tipp-Satz steht mit Kürzel, Monat und
  „hilfreich“-Zahl. Kein Ranking-Wort („Top“, „Beste“, „Empfohlen“).
- **Alle anderen Orte** liegen hinter „Alle Orte in der Nähe“ im Sheet, gruppiert
  nach Kategorie und nach Entfernung sortiert (automatische Ebene).
- **Entfernung** über `distanceValue` aus `PrefsContext` (km/mi). Bis Phase 3
  als **Luftlinie** gekennzeichnet; danach „6 Min zu Fuß / 9 Min Auto“.
- **Öffnungszeiten** nur, wenn die Quelle sie strukturiert liefert
  (`opening_hours`), als Fakt formuliert, mit Zeitzone des Spots. Kein grünes
  „Jetzt offen“.
- **Zu wenig Kandidaten:** Unter zwei geeigneten Orten erscheint statt der
  Geschichten nur die Zeile „Alle Orte in der Nähe“ plus „Ort vorschlagen“ mit
  dem Hinweis, dass Tipps mit Foto hier erscheinen. Ganz ohne Orte bleibt nur die
  Einladung stehen.
- **Radius:** automatisch 3 km, für `stay` 10 km, für `flat` 15 km. Bei Spots in
  Städten wird der Radius halbiert, wenn eine Kategorie mehr als 30 Treffer hat.
- **Performance:** wie die Lagekarte lazy über `IntersectionObserver`
  (`rootMargin: 500px`); Fotos über die bestehende Bildauslieferung
  (`SpotImage`, responsive Größen), `loading="lazy"`. Der Spot lädt nie
  langsamer wegen der Orte.

### 4.3 Ort-Sheet (Detail)

Tippt man eine Geschichte, öffnet sich ein Bottom-Sheet (mobil, gleiche Technik wie
das Such-Sheet: native CSS-Transition + imperatives Ziehen, **nicht** Framer)
bzw. ein rechtes Panel auf Desktop. Keine eigene Route in Phase 1; ab Phase 2
eine teilbare URL `/spot/{slug}/ort/{place-slug}` (Sheet über der Info-Seite).

Das Sheet beginnt mit dem Foto (16:11, randlos, Schließen-Knopf auf dem Bild).

```
─────────────────────────────────────────
[Foto]
DRAUSSEN SCHLAFEN · SURFCAMP
Kitecamp Nordhaken
Zwei bis drei Sätze Beschreibung.

ZUM EINSTIEG   GEÖFFNET        FÜR
0,4 km         Rezeption 8–20  Vans, Zelte

Boardraum · Neo-Dusche · Van-tauglich

AUS DER COMMUNITY
„Boardraum, Frühstück ab 7, zwei
Minuten zum Einstieg.“
Jonas · August 2026 · 14 hilfreich  ▲

Auch nah an
Fehmarn Wulfener Hals    2,1 km
Fehmarn Lemkenhafen      3,4 km

[ Website ↗ ]  [ Route ↗ ]  [ ☐ Saved ]

ⓘ Daten von OpenStreetMap, Stand 02.10.2026.
  Stimmt etwas nicht? Melden.
─────────────────────────────────────────
```

- **„Auch nah an“** ist der Hebel, den nur wir haben: andere Spots aus dem
  Katalog im Umkreis des Orts. Fakt, keine Empfehlung.
- **Route ↗** über das vorhandene `mapLinkProps(lat, lng)` (externe Karten-App),
  **Website ↗** nur, wenn die Quelle eine liefert. Beide als Links, nichts
  eingebettet, kein Fremd-Tracking.
- **„Melden“** öffnet den vorhandenen Vorschlags-Flow mit Vorauswahl
  „Gibt es nicht mehr / Angaben falsch“. Das ist der wichtigste Mechanismus
  gegen veraltete Einträge.
- Das rote Ausrufezeichen ist hier **nicht** zu verwenden (es ist für Gefahren
  reserviert); die Quellzeile steht mit neutralem Info-Icon in `text-caption text-muted`.

### 4.4 Facilities „Am Spot“ verknüpfen

Die fünf `Facilities` bleiben, wie sie sind (vorhanden/nicht vorhanden/keine
Angabe). Neu: Liegt ein Ort mit Beziehung `at_spot` (≤ 150 m vom Einstieg) in
der passenden Kategorie vor, wird die Notiz daraus gespeist:

| Facility | Heute | Mit verknüpftem Ort |
|---|---|---|
| Essen | „Vorhanden“ | „Kiosk Strandgut · offen bis 18 Uhr“ (Tipp öffnet das Ort-Sheet) |
| Schule | „Vorhanden“ | „Kiteschule Gold“ |
| Camping | „Keine Angabe“ | „Campingplatz Wulfener Hals · 2,3 km“ (nur, wenn ≤ 1 km; sonst bleibt „Keine Angabe“, damit „Am Spot“ ehrlich bleibt) |

Die Verknüpfung setzt nie automatisch `available: true`; dafür bleibt der
Admin- bzw. Vorschlagsweg zuständig. Sie liefert nur die Notiz.

### 4.5 Regionsseite: „Leben in {Region}“ und Basislager

Unterkünfte gehören oft eher zur Region als zum Spot: Wer eine Woche nach Fehmarn
fährt, schläft an einem Ort und fährt je nach Wind an fünf verschiedene Spots.
Dafür gibt es das Konzept **Basislager**:

> Ein Basislager ist ein Ort (meist ein Dorf oder eine Unterkunft), von dem aus
> man viele Spots der Region schnell erreicht, und zwar Spots für **verschiedene
> Windrichtungen**.

Das ist ein reiner Fakt aus Spotkatalog + Spotsektoren und keine Bewertung.
Neuer Abschnitt auf `RegionDetail.tsx`, zwischen „Wann hinfahren“ und „Auf der Karte“:

```
─────────────────────────────────────────
Leben auf Fehmarn

BASISLAGER
Burg auf Fehmarn
  7 Spots in 20 Min · Wind aus allen
  Richtungen abgedeckt
  12 Unterkünfte · 3 Surfshops

Wulfen
  4 Spots in 10 Min · Ost bis Süd
  4 Unterkünfte · Van-Stellplätze

DIE SZENE
„Abends trifft man sich im …“
  Tipp von Mia · 21 hilfreich
─────────────────────────────────────────
```

- „Wind aus allen Richtungen abgedeckt“ heißt: Die Vereinigung der nutzbaren
  Windrichtungs-Sektoren der erreichbaren Spots (`variant_conditions.wind_directions`,
  Logik in `app/weather/usable_directions.py`) überdeckt alle 8 Sektoren.
  Sonst wird der abgedeckte Bereich genannt („Ost bis Süd“). Formulierung
  beschreibend.
- Basislager werden **automatisch** bestimmt: Ortschaften (`place=town|village`)
  und Unterkunfts-Cluster in der Region, für jede wird die Zahl der Spots in
  Fahrzeit X berechnet; die drei mit der größten Abdeckung erscheinen. Admin kann
  einen Ort ausblenden oder umbenennen, nicht ranken.
- Tap auf ein Basislager → Ergebnisseite `/search` mit Ort als Mittelpunkt
  (existierender „Spots in der Nähe von X“-Pfad) plus Orte-Liste.

### 4.6 Daten-Tab: der Flautentag (Phase 4, Entscheidung offen)

Der Daten-Tab ist das dunkle Instrument und bleibt frei von Lifestyle-Inhalten.
Es gibt genau eine mögliche Brücke:

```
Do 17.  ▁▁▁▁▂▁▁  max 2 Bft
        Ohne Wind und Welle →
```

- Erscheint nur an Tagen, an denen die Vorhersage über den ganzen Tag unter
  der *niedrigsten* in den Spotdaten hinterlegten Nutzschwelle bleibt
  (keine neu erfundene Schwelle; ohne Schwelle erscheint der Link nie).
- Der Link öffnet im Info-Tab das Sheet „Alle Orte“ bei der Gruppe „Ohne Wind und Welle“.
- Er sagt nicht „Heute lieber Yoga“, sondern nur, wo die Alternativen stehen.
  Das ist die Grenze zu „vorschreiben“. Weil sie schmal ist, ist das als
  Entscheidung markiert (Abschnitt 11, Nr. 4).

### 4.7 Karte (Phase 4)

Die Regel „genau eine öffentliche Wetterkarte“ bleibt. Orte kommen in die
bestehende `SpotExplorer`-Ebene, nicht in eine neue Karte:

- Nur wenn ein Spot ausgewählt ist und ab Zoom 13 (Zoom-Cap ist 13, also nur auf der höchsten Stufe).
- Kleine Glyphen in `ink-soft` (Kategorie-Icon, 16 px), keine Cluster-Zahlen, keine Farben pro Kategorie.
- Toggle im bestehenden Overlay-Sheet: „Orte in der Nähe“, Standard **aus**.
- `LocatorMap` (Luftbild) bekommt **keine** dauerhaften Ort-Pins. Ausnahme: Aus
  dem Ort-Sheet „Auf Luftbild zeigen“ setzt einen zweiten, neutralen Pin, damit
  man sieht, wo das Hostel relativ zum Einstieg liegt.

### 4.8 Konto · Saved

Saved bekommt eine zweite Gruppe „Orte“ unter den Spots, gruppiert nach Spot.
Das ist die Keimzelle für einen späteren Trip (Abschnitt 8).

### 4.9 Suche (Phase 3)

Zwei Lifestyle-Filter in der bestehenden Filterleiste, beide als reine
Fakten-Filter:

- **Unterkunft in Gehweite** (≤ 1 km, mindestens ein `stay`-Ort)
- **Van-Stellplatz in der Nähe** (≤ 5 km, `caravan_site` oder `van_ok`)

`SpotCard` zeigt bei aktivem Filter eine Zeile „Hostel 0,4 km“. Kein Score,
keine Hervorhebung, gleichwertige Treffer (Ergebnisseiten-Regel).

---

## 5. Daten: Quellen, Lizenzen, Pipeline

### 5.1 Quellen

| Quelle | Inhalt | Lizenz / Bedingung | Rolle |
|---|---|---|---|
| **OpenStreetMap** (Overpass oder regionaler PBF-Extrakt) | Unterkünfte, Gastronomie, Shops, Freizeit, Öffnungszeiten, Merkmale | ODbL 1.0, Namensnennung, Share-Alike für abgeleitete *Datenbanken* | Primärquelle |
| **Overture Maps Places** | Geschäfte mit Kategorie und Konfidenz; besser bei Gastronomie und Unterkünften | Pro Datensatz: CDLA-Permissive-2.0, Foursquare-Datensätze Apache 2.0 (NOTICE beibehalten, Änderungen kennzeichnen) | Ergänzung, Dublettenabgleich mit OSM |
| **Community** | Tipps, Merkmale, „Gibt es nicht mehr“ | Nutzungsbedingungen (bestehende Lizenzannahme wie bei Fotos) | Kuratierte Ebene |
| **Redaktion/Admin** | Startkuratierung für Pilot-Spots | eigen | Kuratierte Ebene |
| **Partner** (Phase 5) | Eigene Angaben verifizierter Betriebe | Partnervertrag | Merkmale, Fotos mit Lizenz |
| ~~Google Places~~ | — | **Nicht als Quelle nutzbar:** Inhalte (Name, Adresse, Bewertung, Fotos) dürfen nicht gespeichert werden; nur `place_id` | höchstens „In Google Maps öffnen“ als Link über Koordinaten |
| ~~Airbnb~~ | — | Kein offenes Partnerprogramm und keine offene API; Zugang nur auf Einladung für Channel-Manager | höchstens ein neutraler Such-Link „Ferienwohnungen auf Airbnb suchen ↗“ um die Koordinaten, ohne Listings |
| ~~Scraping~~ (Booking, Tripadvisor, Instagram) | — | AGB-Verstoß, Urheber-/Datenbankrecht | nie |

**ODbL-Hinweis:** Werden OSM-Daten mit eigenen Daten zu *einer* Datenbank
verschmolzen und veröffentlicht, greift Share-Alike für diese abgeleitete
Datenbank. Deshalb liegen OSM-Felder in eigenen Spalten mit `source = 'osm'`
und werden nicht mit Community-Feldern vermischt (Community-Merkmale in einer
eigenen Tabelle, siehe 6.1). Vor dem Livegang ist eine juristische Prüfung
nötig, ob die Darstellung als „Collective Database“ trägt. Das ist dasselbe
Muster wie im Regel-Konzept (Abschnitt 4.3 der 8 Punkte), das OSM ebenfalls nutzt.

**Bilder:** keine Fremdfotos von Unternehmen, keine gescrapten Bilder,
keine KI-Bilder (Grundsatz wie beim Gear-Katalog). Fotos kommen nur über den
bestehenden Upload mit Lizenzannahme (`SpotImage`-Pipeline, neu mit
`place_id`) oder von Partnern mit Lizenznachweis. Ohne Foto kann ein Ort nicht
in die kuratierte Auswahl (3.1); in der Liste „Alle Orte“ stehen Orte ohne Foto.
Für den Start fotografiert die Redaktion die Pilot-Spots selbst oder bittet
die Betriebe um lizenzierte Fotos.

### 5.2 Import-Pipeline

Vorbild ist die Geodaten-Pipeline (`app/forecast/geodata_catalog.py`,
`docs/geodata-phase1.md`): versioniertes Quellenregister, Budget, Preflight,
erst Schatten, dann Aktivierung.

```
Quellenregister (osm-europe@2026-10-01, overture-places@2026-09-24.0)
  -> Extrakt je Region (Bounding Box der Region + 15 km)
  -> Normalisierung: Kategorie-Mapping (Abschnitt 2), Merkmale, opening_hours parsen
  -> Dublettenabgleich OSM ↔ Overture (Distanz ≤ 50 m + normalisierter Name, Trigramm)
  -> places (upsert über source + source_id, Hash pro Datensatz)
  -> spot_places (PostGIS ST_DWithin je Kategorie-Radius, distance_m)
  -> Schattenphase: nur Admin-Ansicht, Abdeckungsbericht
  -> Aktivierung je Region
  -> wöchentlich: Abruf, Hash-Vergleich, Diff-Liste im Admin
```

- **Verschwundene Orte** (nicht mehr in der Quelle): `status = 'gone'`, nach
  zwei Läufen öffentlich ausgeblendet. Community-Tipps zu diesem Ort bleiben im
  Archiv, erscheinen aber nicht mehr.
- **Qualitätsfilter:** Overture-Datensätze unter Konfidenz 0,7 werden nicht
  übernommen. OSM-Orte ohne Namen werden nicht angezeigt (außer `basics` wie
  Wasserstelle, Entsorgung).
- **Startumfang:** die Pilot-Spots aus `config/weather-pilot-spots.json`
  (DE/NL/DK), dann alle veröffentlichten Regionen.
- **Admin nur für Ausnahmen:** Ausblenden mit `hidden_reason`, Kategorie
  korrigieren, Ort als `at_spot` markieren. Admin rankt nicht.

### 5.3 Routing (Phase 3)

Für Gehzeit/Fahrzeit und Basislager: selbst gehostetes OSRM oder
openrouteservice auf OSM-Basis, nur offline im Worker (Matrix Spot ↔ Orte und
Ort ↔ Spots der Region), Ergebnisse in `spot_places.walk_s` / `drive_s`. Keine
Routing-Anfrage zur Laufzeit. Bis dahin: Luftlinie, klar beschriftet.

---

## 6. Datenmodell und API

### 6.1 Tabellen (neue Alembic-Revisionen, keine bestehende ändern)

```text
places
  id uuid pk
  slug varchar(160) unique
  name varchar(200), normalized_name (Trigramm-Index)
  category varchar(20)      -- stay | eat | night | gear | flat | basics
  subcategory varchar(40)   -- hostel | surfcamp | camp_site | cafe | surf_shop ...
  location geography(point) (GiST)
  region_id uuid fk regions null
  address jsonb null
  website varchar(500) null
  opening_hours text null   -- Rohwert der Quelle, Parsing im Backend
  source_attrs jsonb        -- Merkmale aus der Quelle (osm/overture), unvermischt
  source varchar(20)        -- osm | overture | community | admin | partner
  source_id varchar(200), source_version varchar(40), source_hash char(64)
  license varchar(40), retrieved_at timestamptz
  confidence real null
  status varchar(20)        -- shadow | published | hidden | gone
  hidden_reason text null
  unique (source, source_id)

spot_places
  spot_id fk spots, place_id fk places, pk (spot_id, place_id)
  relation varchar(10)      -- at_spot | nearby
  distance_m int
  walk_s int null, drive_s int null     -- Phase 3
  origin varchar(10)        -- auto | admin

place_attributes            -- Community-/Partner-Merkmale, getrennt von OSM
  place_id, key, value bool, origin (community | partner | admin),
  confirmations int, app_user_id null, status (pending | published)

local_tips.place_id uuid null fk places   -- Ort-Tipp = Tipp am Spot mit Ortsbezug
favorite_places (app_user_id, place_id, spot_id null, created_at)
spot_place_picks            -- Ergebnis der Auswahlregel 3.1, wöchentlich
  spot_id, slot (outdoor | indoor | morning | evening), place_id,
  tip_id, image_id, votes, is_lead bool, computed_at
spot_images.place_id uuid null fk places  -- Ortsfoto über die bestehende Bildpipeline
```

Bewusst **nicht**: eigene Bewertungstabelle, Preisfelder, Verfügbarkeiten.

### 6.2 Endpunkte

| Methode | Pfad | Zweck | Cache |
|---|---|---|---|
| GET | `/spots/{id}/places?category=&limit=` | Modul „Rund um den Spot“: Auswahl (aus `spot_place_picks`) + alle Orte, gruppiert | versioniert wie `/spots?catalog_version` (Edge-Cache), eigene `places_version` |
| GET | `/places/{id}` | Ort-Sheet inkl. „Auch nah an“ | Edge-Cache kurz |
| GET | `/regions/{slug}/life` | Basislager + Szene-Tipps | versioniert |
| POST | `/community/submissions` (bestehend) mit `kind: "place_suggestion"` bzw. `"place_report"` | Ort vorschlagen / melden | – |
| POST | bestehender Tipp-Endpunkt mit optionalem `place_id` | Ort-Tipp | – |
| PUT/DELETE | `/community/comments/tip/{id}/upvote` (bestehend) | „hilfreich“ | – |
| PUT/DELETE | `/account/favorites/places/{id}` | Saved | – |

Schemas in `app/schemas/place.py`, Frontend-Typen in `lib/types.ts` und Adapter
in `lib/adapt.ts` werden synchron gehalten (Projektregel).

### 6.3 Frontend-Bausteine

```text
components/places/
  AroundSpot.tsx         -- SectionBand-Modul im Info-Tab (lazy)
  PlaceLeadStory.tsx     -- Leitgeschichte: Foto, Schlagzeile, Fakten, Tipp
  PlaceStoryCard.tsx     -- Geschichte 4:5, im Wisch-Rail bzw. Dreier-Raster
  PlaceStoryRail.tsx     -- Scroll-Snap-Rail mit Punkten (mobil), Raster (Desktop)
  PlaceSelectionNote.tsx -- „So werden die Orte ausgewählt“ + Kandidaten
  PlaceSheet.tsx         -- Bottom-Sheet / Panel (Ort-Detail und „Alle Orte“)
  PlaceRow.tsx           -- kompakte Zeile, nur in „Alle Orte“
  placeIcons.ts          -- Kategorie → Icon aus lib/icons.tsx
lib/places.ts            -- Gruppierung, Radiuslogik, opening_hours-Formatierung
app/places/selection.py  -- Auswahlregel 3.1, wöchentlich, Ergebnis in spot_place_picks
lib/hooks.ts             -- usePlacesAround(spotId), usePlace(id), useRegionLife(slug)
```

- Alle Texte direkt im i18n-Katalog (`locales/de.ts`, Namensraum `places.*`),
  die neuen Dateien von Anfang an in die Lint-Guard-Liste. Kategorie- und
  Merkmalsnamen als `labelKey`, nie als `label` (Lehre aus der i18n-Tranche).
- Entfernungen nur über `useOptionalUnits()` + `distanceValue`.
- E2E: ein Spec „spot info shows places around the spot“ mit gemockter Antwort,
  plus i18n-Spec deckt das Modul automatisch ab.

---

## 7. Community: aus Tipps werden Ortswissen

Die Community-Infrastruktur (Tipps, Upvotes, Moderation, Vorschläge) existiert.
Neu ist nur der Ortsbezug.

### 7.1 Tipp mit Ort

Im bestehenden Tipp-Composer (`InlineTipComposer`, `SpotCommunity`) eine
optionale Zeile „Ort verknüpfen“: Suche über die Orte des Spots (Name). Wählt man
einen Ort, wird der Tipp zum Ort-Tipp und erscheint in „Rund um den Spot“ unter
„Tipps“ **und** wie bisher im Spot-Feed.

Pflichtfeld bei Ort-Tipps: **ein Satz, warum der Ort für Surfer gut ist**
(max. 140 Zeichen). Das ist der Kern des kuratierten Werts. Zusätzlich können
bis zu drei Merkmale angehakt werden (Boardraum, Waschplatz, Van-tauglich …);
jedes Merkmal braucht zwei unabhängige Bestätigungen, bevor es öffentlich ist.

### 7.2 Ort vorschlagen und melden

`SuggestEditButton`-Flow mit zwei neuen Arten:

- **Ort vorschlagen:** Name, Kategorie, Pin (vorhandener `SubmissionMapPicker`-Ansatz
  nur im Admin; öffentlich reicht „Am Spot / Adresse / Link“), ein Satz.
- **Melden:** „Gibt es nicht mehr“, „Falsche Kategorie“, „Falscher Ort“. Drei
  unabhängige Meldungen „Gibt es nicht mehr“ blenden einen automatischen Ort
  vorläufig aus, bis der nächste Quellabgleich ihn bestätigt oder entfernt.

### 7.3 Moderation

Läuft über die bestehende Moderationsliste (`admin_moderation`). Neue
Prüfregel: Ort-Tipps mit Link oder Telefonnummer im Text gehen immer in die
manuelle Prüfung (Schutz vor Eigenwerbung). Ein Betreiber, der über sich
selbst schreibt, ist kein Community-Tipp, sondern ein Partner (Abschnitt 9).

---

## 8. Das Rundum-Paket: Trips (Phase 4)

Das Ziel „Rundum-Paket für den Spot“ entsteht, wenn die Teile zusammenkommen:

```
Spot (Saved)  +  Monat (Windmonate/best_months)  +  Basislager/Unterkunft (Saved)
       └──────────── Trip „Fehmarn im Mai“ ────────────┘
```

- **Trip-Seite** im Konto: Titel, Zeitraum, gesparte Spots, gesparte Orte,
  für den Zeitraum die Windmonate-Zeile je Spot („Im Mai meist 4–5 Bft“,
  aus 5.3 der 8 Punkte), Entfernungen Ort ↔ Spots.
- **Teilen** über `ShareButton` als Link (nur lesend). Für Surfgruppen, die
  zusammen fahren.
- Rückkopplung mit dem Spot-Wecker (Punkt 1 der 8 Punkte): Ein Trip kann die
  Wecker seiner Spots für den Zeitraum gesammelt einschalten.
- Kein Buchen, keine Preise. Der Trip ist ein Plan, kein Warenkorb.

---

## 9. Partner und Geld (Phase 5, Entscheidung offen)

Lifestyle-Inhalte sind der naheliegendste Weg zu Einnahmen. Gerade deshalb
braucht es Regeln, bevor der erste Euro fließt, sonst verliert das Tool das
Vertrauen, auf dem alles andere aufbaut („Haltung sichtbar machen“, 6a).

### 9.1 Unverhandelbare Regeln

1. **Reihenfolge ist nie käuflich.** Sortierung bleibt Upvotes/Entfernung.
   Ein Partner steht nicht weiter oben.
2. **Kennzeichnung:** Partner-Orte tragen „Partner“ in `text-caption text-muted`,
   Affiliate-Links „Werbelink“ mit Erklärung auf `/methode` (geplant, Punkt 6a der 8 Punkte). Links mit
   `rel="sponsored noopener"`.
3. **Keine Einbettungen:** keine Buchungs-Widgets, keine Tracking-Pixel.
   Ein Klick führt nach außen, sonst nichts.
4. **Community vor Partner:** Ein Partner kann Merkmale, Öffnungszeiten, Fotos
   (mit Lizenz) und einen Satz über sich ergänzen, aber keine Community-Tipps
   ausblenden oder kommentieren.

### 9.2 Mögliche Modelle

| Modell | Beschreibung | Aufwand | Risiko |
|---|---|---|---|
| **Affiliate-Links** (Booking.com, Hostelworld, Campingplatz-Portale) | Deep-Link „Bei X ansehen ↗“ am Ort-Sheet, sofern der Ort dort gelistet ist (Abgleich über Name + Koordinate über die Partner-API) | M | AGB je Programm prüfen; Impressum/Datenschutz anpassen |
| **Verifizierter Betrieb** (kostenlos) | Betrieb beansprucht seinen Eintrag, pflegt Fakten | M | Verifikation (Telefon/Website-Token) |
| **Partner-Profil** (bezahlt) | Fotos, Angebote „Kurs ab 89 €“, Saisonzeiten; **kein** Ranking | L | Abgrenzung zu Werbung, UWG |
| **Surfschulen-Kurse** | Link zur Buchung beim Betrieb | S | gering |

Airbnb ist hier bewusst nicht dabei: Es gibt kein offenes Affiliate-Programm
und keine offene API. Ein neutraler Such-Link ist möglich, bringt aber keine
Daten und kein Geld.

---

## 10. Passt das zum Tool? Prüfung gegen alle bestehenden Regeln

| Regel / Entscheidung | Erfüllt durch | Status |
|---|---|---|
| Informieren, nicht vorschreiben (E1, keine Ampel/Scores) | Keine Sterne, keine „Top“, nur Fakten (Entfernung, Merkmale, Öffnungszeiten). Basislager = Abdeckungsfakt. Flautentag-Link nur als Verweis, als Entscheidung markiert | ✓ (4.6 offen) |
| Einziges Warnmuster rotes „!“ | Im Modul nicht verwendet; Quellhinweise neutral | ✓ |
| Genau eine öffentliche Wetterkarte | Orte als Ebene in `SpotExplorer` (Phase 4), keine neue Karte; `LocatorMap` nur temporärer Zweit-Pin | ✓ |
| Ehrlich statt gefüllt | Unbekannte Merkmale ausgeblendet, Luftlinie beschriftet, Quelle + Stand sichtbar, kein leerer Platzhalter-Content | ✓ |
| Keine gescrapten/KI-Bilder | Fotos nur mit Lizenz (Community/Partner); ohne Foto keine Aufnahme in die Auswahl | ✓ |
| Kein Punkt bekommt eine eigene Navigationsebene | Section im Info-Tab, Sheet statt Seite; dritter Tab nur als offene Option | ✓ (11 Nr. 1) |
| Editoriale Grammatik, Tokens, ein Radius, Teal nur aktiv | `SectionBand`, Leitgeschichte + Geschichten wie Landing/Region, Haarlinien, teal nur für aktive Punkte und Hauptknopf | ✓ |
| Kein Ranking-Wort, nicht käuflich | Auswahlregel 3.1 öffentlich erklärt, Kandidaten sichtbar | ✓ |
| Mobile zuerst, keine Pop-ups | Bottom-Sheet nur auf Tap; keine Banner | ✓ |
| Landing-Smoothness (Sheets ohne Framer) | Ort-Sheet nutzt dieselbe native Technik wie das Such-Sheet | ✓ |
| Einheiten app-weit über `PrefsContext` | `distanceValue` | ✓ |
| i18n-Tranchen, Admin bleibt Deutsch | Neues Modul startet mit Katalog-Keys; Admin-Ansichten hardcoded Deutsch, eigene Komponenten (`SearchInput`/`ButtonLink`), kein öffentlicher Teal-Input | ✓ |
| Kein Admin-Chunk im Public-Bundle | Admin-Review der Orte in `pages/Admin*`, getrennt geladen | ✓ |
| API-Schemas und Frontend-Typen synchron | `app/schemas/place.py` ↔ `lib/types.ts` | ✓ |
| Keine bestehende Migration ändern | nur neue Revisionen | ✓ |
| Prod-Migrationen manuell (Neon) | Betriebsschritt im Rollout vermerken | ✓ |
| Kosten (Vercel Hobby, Neon) | Import nur im Worker/Cron mit Budget, keine Laufzeit-Abfragen an Fremd-APIs, Edge-Cache | ✓, Cron hinter `RUN_MAINTENANCE_CRONS` |
| Datenschutz | Nur Links nach außen, keine Drittinhalte geladen; Datenschutzseite um Affiliate-Links ergänzen (Phase 5) | ✓ |

**Ergebnis:** Das Konzept fügt sich ohne Bruch ein. Die einzigen Stellen, an
denen es eine bestehende Haltung berührt, sind der Flautentag-Link im Daten-Tab
(4.6) und Geld (9). Beide sind als Entscheidungen markiert und nicht Teil der
ersten Phasen.

---

## 11. Offene Entscheidungen

| # | Frage | Vorschlag |
|---|---|---|
| 1 | Abschnitt im Info-Tab oder dritter Tab „Umgebung“ (`/spot/{slug}/umgebung`)? | **Abschnitt** in Phase 1–2. Dritter Tab erst, wenn Spots im Schnitt > 15 Orte und > 3 Tipps haben; dann gibt er Raum und eine eigene, gut auffindbare URL |
| 2 | Wie viel Automatik: nur kuratiert, oder automatische Ebene von Tag 1? | **Beides**, getrennt dargestellt (Abschnitt 3). Nur kuratiert wäre zum Start überall leer |
| 3 | Welche Kategorien zum Start? | Alle sechs, aber „Abends“ nur aus Tipps (automatisch wären es zu viele Kneipen ohne Surf-Bezug) |
| 4 | Flautentag-Link im Daten-Tab? | Ja, aber erst Phase 4 und nur mit hinterlegter Spot-Schwelle |
| 5 | Geld: wann und wie? | Erst nach Phase 3, beginnend mit Affiliate-Links und kostenlosen verifizierten Betrieben; Regeln aus 9.1 vorher auf `/methode` veröffentlichen |
| 6 | Airbnb-Such-Link ohne Daten? | Nein in Phase 1–3 (bringt dem Nutzer wenig, wirkt wie Werbung ohne Kennzeichnung) |
| 7 | Orte auf `SpotExplorer` und Zweit-Pin im Luftbild? | Ja, Phase 4, Standard aus |
| 8 | Fotos von Orten? | **Entschieden:** Pflicht für die kuratierte Auswahl, nur mit Lizenz (Community, Partner, Redaktion) |
| 9 | Auswahlregel (3.1) | **Entschieden:** ein Ort pro Moment, meiste „hilfreich“-Stimmen, nur mit Foto und frischem Tipp, wöchentlich |

---

## 12. Reihenfolge und Aufwand

| Phase | Inhalt | Aufwand (grob) | Ergebnis |
|---|---|---|---|
| **0 · Probe** | Overpass + Overture für die Pilot-Spots ziehen, Kategorie-Mapping testen, Abdeckungsbericht je Kategorie (wie viele Orte, wie viele mit Öffnungszeiten, Dublettenquote). ODbL-Prüfung | S | Entscheidungsgrundlage, ob die automatische Ebene trägt |
| **1 · Rund um den Spot** | `places`/`spot_places`, Import-Worker (Schatten → aktiv), `/spots/{id}/places`, Sheet „Alle Orte“, Ort-Sheet, Facilities-Notiz, Admin-Ausblenden; Redaktion kuratiert die Pilot-Spots mit eigenen Fotos | M | Jeder Pilot-Spot hat ein Umfeld und eine erste Auswahl |
| **2 · Kuratierung** | Ort-Tipps mit Foto im Composer, „hilfreich“, Auswahlregel 3.1 als Wochenjob, Leitgeschichte + Geschichten, „So werden die Orte ausgewählt“, Merkmale mit Bestätigung, Ort vorschlagen/melden, Saved-Orte, teilbare Ort-URL | M | Die Auswahl pflegt sich selbst |
| **3 · Region & Wege** | Routing-Matrix offline, Gehzeit/Fahrzeit, Basislager auf der Regionsseite, Suchfilter „Unterkunft in Gehweite“/„Van-Stellplatz“ | M–L | Das Feature, das nur surfwinddata kann |
| **4 · Verknüpfung** | Orte-Ebene in `SpotExplorer`, Zweit-Pin im Luftbild, Flautentag-Link, Trips | M | Rundum-Paket |
| **5 · Partner** | Verifizierte Betriebe, Affiliate-Links, Partner-Profile, `/methode`-Ergänzung, Datenschutz | L | Einnahmen ohne Vertrauensverlust |

Abhängigkeiten: Phase 1 setzt nur die Probe voraus. Phase 2 nutzt die
bestehende Community. Phase 3 profitiert von den Spotsektoren aus Punkt 2.2 der
8 Punkte (für „Wind aus allen Richtungen“). Phase 4 setzt Saved-Orte und
Windmonate-Zeile (5.3 der 8 Punkte) voraus.

---

## 13. Woran wir merken, dass es funktioniert

| Messgröße | Ziel nach 3 Monaten Phase 2 |
|---|---|
| Anteil veröffentlichter Spots mit ≥ 1 Ort in `stay` und `eat` | ≥ 80 % |
| Anteil Spots mit ≥ 1 Ort-Tipp | ≥ 25 % der Pilot-Spots |
| Klicks auf „Route“/„Website“ je 100 Info-Aufrufe | Basiswert erheben, dann beobachten |
| Meldungen „Gibt es nicht mehr“ je 1000 angezeigte Orte | < 5 (sonst Quelle/Filter nachschärfen) |
| Gespeicherte Orte je aktivem Konto | Basiswert erheben |

Gemessen über die bestehende Event-Infrastruktur (`app/api/events.py`), ohne
Drittanbieter-Analytics.

---

## 14. Was bewusst nicht gebaut wird

| Nicht bauen | Warum |
|---|---|
| Sterne-Bewertungen für Betriebe | Haftung, Moderationsaufwand, widerspricht E1 |
| Eigene Buchung, Preise, Verfügbarkeit | Kein Kerngeschäft, hoher Pflegeaufwand, Booking macht das besser |
| Vollständiges Branchenbuch | Rauschen; Wert entsteht durch Surf-Bezug |
| KI-generierte Ortsbeschreibungen | Erfundene Fakten über reale Betriebe; rechtlich und fürs Vertrauen riskant |
| Google-Places- oder Airbnb-Daten speichern | Nach deren Bedingungen nicht zulässig bzw. nicht zugänglich |
| Gescrapte Fotos | Urheberrecht, Gear-Katalog-Grundsatz |
| Eigene Lifestyle-Karte | Regel „eine öffentliche Wetterkarte“ |
| Event-Kalender (Contests, Partys) | Pflegeaufwand; später ggf. als Community-Tipp mit Datum |
