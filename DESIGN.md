---
name: Surfwinddata
description: Bildgetriebener Spot-Explorer mit ruhiger Travel-Editorial-Anmutung und praezisen Wetterdaten.
colors:
  page-light: "#F8F6F2"
  band-light: "#EFEAE2"
  surface-light: "#FFFFFF"
  ink-light: "#241C17"
  ink-soft-light: "#3D332C"
  muted-light: "#6B625B"
  line-light: "#E6E1DA"
  line-soft-light: "#F0EDE7"
  page-dark: "#0E1114"
  band-dark: "#14181C"
  surface-dark: "#1A1F24"
  ink-dark: "#F1EDE7"
  ink-soft-dark: "#C7BFB6"
  muted-dark: "#9B928A"
  line-dark: "#2A2F34"
  line-soft-dark: "#22262A"
  ocean-action: "#1C4E63"
  ocean-action-hover: "#163E4F"
  ocean-text-dark: "#6FA8C0"
  ocean-text-dark-hover: "#8CC0D6"
  coastal-attention-light: "#B45309"
  coastal-attention-dark: "#E7883A"
  wind-data-light: "#3F7350"
  wind-data-dark: "#6BA97A"
  on-photo: "rgb(255 255 255 / 0.92)"
  on-photo-muted: "rgb(255 255 255 / 0.66)"
  danger-light: "#B91C1C"
  danger-dark: "#F87171"
  success-light: "#15803D"
  success-dark: "#4ADE80"
  warning-light: "#92400E"
  warning-dark: "#FBBF24"
typography:
  hero:
    fontFamily: "Poppins, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(2.5rem, 6vw, 5rem)"
    fontWeight: 700
    lineHeight: 1.02
    letterSpacing: "-0.02em"
  display:
    fontFamily: "Poppins, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "3rem"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Poppins, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(1.75rem, 3vw, 2.125rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Poppins, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1.4375rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.005em"
  body:
    fontFamily: "Poppins, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  ui:
    fontFamily: "Poppins, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.5
  caption:
    fontFamily: "Poppins, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.45
  figures:
    fontFamily: "SW Figures, Poppins, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
  wordmark:
    fontFamily: "MADE Mountain, Poppins, system-ui, sans-serif"
    fontWeight: 400
    lineHeight: 1
rounded:
  none: "0"
  card: "14px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  3xl: "64px"
  4xl: "80px"
components:
  text-action:
    textColor: "{colors.ink-light}"
    typography: "{typography.ui}"
    rounded: "{rounded.none}"
    padding: "8px 0"
    height: "44px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink-light}"
    typography: "{typography.ui}"
    rounded: "{rounded.card}"
    padding: "8px 16px"
    height: "44px"
  button-primary-exception:
    backgroundColor: "{colors.ink-light}"
    textColor: "{colors.surface-light}"
    typography: "{typography.ui}"
    rounded: "{rounded.card}"
    padding: "8px 16px"
    height: "44px"
  card-spot:
    backgroundColor: "transparent"
    textColor: "{colors.ink-light}"
    rounded: "{rounded.card}"
  input-default:
    backgroundColor: "{colors.surface-light}"
    textColor: "{colors.ink-light}"
    typography: "{typography.ui}"
    rounded: "{rounded.card}"
    padding: "10px 12px"
    height: "44px"
  chip-unselected:
    backgroundColor: "{colors.surface-light}"
    textColor: "{colors.ink-light}"
    typography: "{typography.ui}"
    rounded: "{rounded.full}"
    padding: "8px 14px"
  chip-selected:
    backgroundColor: "{colors.ocean-action}"
    textColor: "{colors.surface-light}"
    typography: "{typography.ui}"
    rounded: "{rounded.full}"
    padding: "8px 14px"
---

# Design System: Surfwinddata

## Vor jeder neuen Komponente

Diese zehn Punkte sind die Kurzfassung des ganzen Dokuments. Sie sind
Entscheidungen, die das System bereits getroffen hat — sie noch einmal zu
treffen, nur anders, ist der Weg, auf dem eine Seite zum Flickenteppich wird.
Alles darunter erklaert, warum.

1. **Gibt es das schon?** Erst `frontend/src/components` durchsuchen. Eine
   zweite Schreibweise eines vorhandenen Musters ist die haeufigste Ursache
   fuer Abdriften.
2. **Flaeche:** standardmaessig keine. Eine Kachel hebt sich um genau eine
   Tonstufe (`bg-tile`). Einen Rahmen bekommen nur Dinge mit echter Kante —
   Eingaben, Dialoge, Overlays, Medien.
3. **Kontur:** standardmaessig keine. Eine Hairline nur dort, wo zwei Dinge
   sonst ineinanderlaufen, nie als Dekoration um eine Gruppe.
4. **Schatten:** standardmaessig keiner. `shadow-card` / `shadow-float` nur
   fuer Dinge, die wirklich ueber dem Inhalt schweben.
5. **Radius:** `rounded-card` (14px) fuer jedes Rechteck. `rounded-full` nur
   bei wirklich runder Silhouette.
6. **Typo:** ausschliesslich die Skala (`micro` … `hero`, `data-*`). Kein
   `text-[14px]`, kein `text-sm`, keine `sz-*` im oeffentlichen Code.
7. **Farbe:** ausschliesslich semantische Tokens. Keine Tailwind-Palette
   (`bg-gray-100`), kein Hex am Call-Site.
8. **Abstand:** Tailwind-Spacing, nichts Beliebiges. Der vertikale Rhythmus
   kommt vom Band, nicht vom Margin der Komponente.
9. **Dark Mode:** jedes Token kippt mit. Eine handgeschriebene Farbe ist eine
   Light-Mode-only-Komponente.
10. **320px und Touch:** kein horizontaler Ueberlauf bei 320px, jedes
    Bedienelement mindestens 44px hoch.

Beim Arbeiten laedt der Skill `design-system` (`.claude/skills/design-system/`)
genau diese Liste plus die Named Rules; dieses Dokument bleibt die Begruendung.

## Wenn eine Entscheidung einer Regel widerspricht

Der Nutzer entscheidet — aber das Dokument darf nicht liegen bleiben. Kehrt
eine Entscheidung eine Named Rule um, dann wird die Regel **im selben Commit**
mitgeaendert, und sie vermerkt, was vorher galt. Eine Regel, der der Code
widerspricht, ist schlimmer als keine Regel: sie bringt allen bei, das Dokument
zu ignorieren.


## Overview

**Creative North Star: „Editorial Coast Explorer“**

Surfwinddata ist ein bildgetriebenes Entdeckungswerkzeug fuer Wassersportlerinnen und Wassersportler zwischen 20 und 40. Die Oberflaeche verbindet die entspannte, vertrauensvolle Stoeberqualitaet einer modernen Reiseplattform mit der Praezision eines Wetter-Dashboards. Sie soll nicht nur eine Frage beantworten, sondern Lust machen, laenger zu bleiben, Regionen zu vergleichen und neue Spots zu entdecken.

Die Landingpage ist grosszuegig, visuell und leicht zugaenglich. Spot-Info-Seiten lesen sich wie ein reduziertes Travel-Editorial, in dem Fotografie, Ort und praktische Hinweise zusammengehoeren. Erst im Datenbereich wechselt das Produkt kontrolliert in einen dichteren Instrumentenmodus. Diese drei Modi teilen dieselben Farben, Typografie, Radien und Interaktionsprinzipien; sie unterscheiden sich nur in Informationsdichte und Bildanteil.

**Key Characteristics:**

- Bild zuerst, Interface danach: starke, echte Spot-Fotografie traegt Orientierung und Atmosphaere.
- Ruhige, milde Neutraltoene in Light und Dark Mode; Akzentfarben bleiben selten und funktional.
- Kleine UI-Schrift trifft auf deutlich groessere Ueberschriften und grosszuegige Leerräume.
- Textlinks, Unterstreichungen und feine Konturen sind die bevorzugten Aktionen.
- Dashboard-Dichte ist auf Wetter-, Wind- und Wellendaten begrenzt.
- Dezente Icons unterstuetzen Hinweise; sie ersetzen weder Text noch eindeutige Labels.

**The Three-Modes Rule.** Discovery ist bildreich und leicht, Editorial ist erzaehlerisch und grosszuegig, Data ist kompakt und praezise. Eine einzelne Ansicht mischt nie alle drei Dichten gleichzeitig.

## Colors

Die Palette basiert auf warmen Off-Whites und braun getoenten Inks im Light Mode sowie milden, nicht tiefschwarzen Anthrazittoenen im Dark Mode. Beide Modi wirken ruhig, hochwertig und fotografiefreundlich.

### Primary

- **Deep Ocean Action** (`ocean-action`): einzige Flaechenfarbe fuer ausgewaehlte Filter, kleine primaere Kontrollpunkte und die Info/Daten-Markierung. Als duenne Schrift im Dark Mode wird stattdessen `ocean-text-dark` verwendet.
- **Warm Editorial Ink** (`ink-light` / `ink-dark`): Ueberschriften, primaerer Text und die seltene, hochpriorisierte Aktionsflaeche.

### Secondary

- **Coastal Attention** (`coastal-attention-light` / `coastal-attention-dark`): sparsame Aufmerksamkeit fuer Wortmarke, Kartenmarker, Live-Puls und Saison-Hervorhebung. Nie als Button-, Link- oder Fliesstextfarbe.
- **Wind Data Green** (`wind-data-light` / `wind-data-dark`): Datenvisualisierung und Windskala. Es ist kein Erfolgsstatus.

### Neutral

- **Warm Page** (`page-light` / `page-dark`): Standardhintergrund der Anwendung.
- **Sand Band** (`band-light` / `band-dark`): alternierende redaktionelle Abschnitte, ruhige Hinweisflaechen und leere Zustaende.
- **Clean Surface** (`surface-light` / `surface-dark`): Eingaben, Dialoge und angehobene Arbeitsflaechen.
- **Soft Ink** (`ink-soft-light` / `ink-soft-dark`): Fliesstext mit geringerer Hierarchie.
- **Muted Copy** (`muted-light` / `muted-dark`): Metadaten, Bildnachweise, Einheiten und erklaerende Nebeninformation.
- **Hairline** (`line-light` / `line-dark`): bevorzugte Trennung fuer Karten, Eingaben und Sektionen.

### Named Rules

**The Quiet Coast Rule.** Grosse, gesaettigte Farbflaechen sind verboten. Atmosphaere entsteht durch Fotografie, warme Neutrals, Raum und Typografie.

**The One Blue Rule.** `ocean-action` ist der einzige blaue Aktionsakzent. Neue Blautoene oder dekorative Verlaeufe werden nicht eingefuehrt.

**The Semantic Status Rule.** Gefahr, Erfolg und Warnung verwenden ausschliesslich ihre semantischen Tokens. Datenfarben duerfen keinen Status vortaeuschen.

**The Photo Contrast Rule.** Inhalte auf Bildern verwenden ausschliesslich `on-photo` und `on-photo-muted` sowie einen lokal begrenzten Scrim, wenn der Bildkontrast nicht reicht.

## Typography

**Display Font:** Poppins mit System-Fallbacks

**Body Font:** Poppins mit System-Fallbacks

**Figures Font:** SW Figures/Manrope fuer Ziffern, Poppins fuer Buchstaben

**Wordmark Font:** MADE Mountain ausschliesslich fuer „surfwind data“

**Character:** Poppins liefert eine moderne, unaufgeregte Geometrie fuer Editorial und UI. Manrope stabilisiert tabellarische Wetterwerte, ohne als zweite sichtbare Textstimme aufzutreten. MADE Mountain bleibt ein Markenzeichen und wird nie fuer Seitenueberschriften verwendet.

### Hierarchy

- **Hero:** fuer Orts- und Regionstitel auf starken Bildbuehnen; kurz, maximal zwei Zeilen.
- **Display:** fuer seltene grosse redaktionelle Aussagen, nicht fuer Standardseiten.
- **Headline:** fuer Seiten- und Sektionsueberschriften; gross genug, um die kleine UI-Typografie bewusst zu kontrastieren.
- **Title:** fuer Modul-, Karten- und Dialogtitel.
- **Body:** fuer redaktionellen Text; laengere Zeilen bleiben auf `max-w-measure` (62 Zeichen) begrenzt.
- **UI:** fuer Controls, Navigation und Hinweise. Das ist die Standardschrift der Bedienoberflaeche.
- **Caption:** fuer Metadaten, Einheiten, Bildnachweise und dichte Legenden. Nie fuer handlungsrelevante Anweisungen.
- **Figures:** fuer Wind, Boeen, Wellen, Temperaturen und tabellarische Werte; immer mit tabellarischen Ziffern.

Versale Labels verwenden ein einheitliches Tracking von `0.14em`. Gewichte 500 und 600 tragen die Hierarchie; 700 bleibt grossen Hero-Titeln vorbehalten. Fliesstext wird nicht fett gesetzt, um fehlende Struktur auszugleichen.

**The One Editorial Voice Rule.** Ausser Wortmarke und Datenziffern spricht die gesamte Anwendung mit Poppins.

**The Small UI, Large Place Rule.** Bedienelemente bleiben kompakt; Namen von Orten, Seiten und redaktionellen Kapiteln erhalten sichtbar mehr Massstab.

## Layout

Das Layout folgt einem gemeinsamen Aussenrahmen von `1570px`. Kopfzeile, Hero, Inhaltsbaender, Spot-Grids und Footer richten sich an denselben Kanten aus. Mobile Seiten verwenden in der Regel `16px` horizontalen Innenabstand, groessere Viewports `32px` bis `40px`. Einspaltige Such- und Inhaltsbereiche sind auf `760px`, laufender Text auf `62ch` begrenzt.

Die Landingpage beginnt mit einer nahezu viewport-hohen Bildbuehne und einer zentralen Suche. Darunter folgen luftige, bilddominierte Spot- und Regionsraster: zwei Spalten auf kleinen, drei auf mittleren und bis zu fuenf auf grossen Viewports. Karten zeigen zuerst das Bild; Name, Ort und wenige Live-Werte folgen kompakt darunter.

Spot-Info-Seiten kombinieren einen vollbreiten Editorial Hero mit versetzten Inhaltsbaendern. Auf Desktop entsteht eine asymmetrische Dreispalten-Komposition aus Einordnung, Galerie und Fakten; mobil wird sie zu einem nachvollziehbaren Einzelstrom. Datenansichten duerfen dichter werden, behalten aber dieselben Kanten, Typorollen und Interaktionsgroessen.

Die oeffentliche Vollbildkarte folgt seit 2026-11-20 dem Site-Theme: hell im Light Mode, im Dark Mode ein dunkler, blaugrauer Grund unterhalb der Panelflaeche (`public-map/mapStyle.ts`, `GROUND.dark`), helle Spotpunkte und Glyphen mit dunklem Halo. Bis dahin blieb sie als helle Kartenarbeitsflaeche theme-unabhaengig; ein dunkler Grund war am 2026-10-11 einen Tag lang versucht und als „Russ" verworfen worden. Der Wechsel kam auf ausdruecklichen Wunsch. Die Lage-Karte auf Spot-Info folgt dem Theme seit 2026-11-22 ebenfalls (gedaempft, siehe Standard Map Rule). Kartenfarben werden nicht als allgemeine Produkttokens wiederverwendet.

**The One Map Surface Rule.** Alle Modi der oeffentlichen Karte (Spots, Wind, Wellen) teilen ein Overlay-Vokabular. Der Grund folgt dem Theme; alles, was darauf liegt, ist das Haussystem: im Light Mode setzt `.sw-theme-light` (index.css) den vollstaendigen hellen Tokensatz auf die Kartenwurzel, im Dark Mode gelten die dunklen Haustokens, Panels verwenden `surface`, `line` und die beiden Hausschatten, Typografie kommt aus der Typo-Skala. Kartenlokal sind ausschliesslich die `--map-*`-Tokens fuer Markenfarbe, Linie und Glyphen-Halo. Ein Panel darf keine zweite Palette mitbringen: Das Vorhersage-Sheet der Windkarte lief bis 2026-11-16 in der dunklen Daten-Palette (`daten-dark`) und machte den Moduswechsel zu einem Systemwechsel mitten auf einer hellen Karte. Die dunkle Instrumentenpalette gehoert auf die dunkle Daten-Seite.

**The Standard Map Rule.** Die Lage-Karte auf Spot-Info (`LocatorMap`, MapLibre) folgt Apple Maps' Standardkarte (`locator/standardStyle.ts`, OpenFreeMap-Vektorkacheln): warmes helles Land, weiches Blau fuer Wasser, blasses Gruen, weisse Strassen, gelbe Autobahnen, graue Namen mit weissem Halo. Bis 2026-11-17 war sie fuer einen Tag eine Satellitenkarte und wurde auf ausdruecklichen Wunsch zur Standardkarte. Bedienelemente sind blosse weisse Glyphen mit dunklem Halo (Kreuz, Plus, Minus, Standort, Route), keine Flaechen. Ortssymbole sind 22-px-Scheiben wie bei Apple (Parken als abgerundetes Quadrat), der Name darunter in der Kategoriefarbe; sie werden nach Zoom gestaffelt und nie gestapelt (`locator/poiLayout.ts`). Die Ortskarte zeigt nur, was in OpenStreetMap eingetragen ist, ohne Hinweis- oder Leer-Saetze. Bewertungen gibt es bewusst nicht; Routen werden an Apple bzw. Google Maps uebergeben. Die Kacheln, die ein Tipp auf Ort, Spot oder Standort oeffnet, sind seit 2026-11-21 minimal (Variante B): Ortssymbol vor dem Namen, eine leise Zeile (Kategorie und Entfernung zum Spot, bei Parken/Camping die eingetragene Gebuehr), Oeffnungszeiten nur wenn eingetragen, dann eine Outline-Aktion ueber die volle Breite „In Apple Karten/Google Maps öffnen“, die den Ort selbst oeffnet. Vorher zeigten sie einen Faktenblock (Adresse, Angebot, WLAN, Hunde …), Website/Anrufen/Instagram und eine gefuellte „Route“-Flaeche. Fotos, Bewertungen und aktuelle Zeiten liefert die Karten-App; eigene Ortsfotos gibt es bewusst nicht (OpenStreetMap hat praktisch keine, Google Places waere kostenpflichtig und auf fremder Karte rechtlich ungeklaert). Die Wahl der App folgt dem Browser, nicht dem Geraet: nur Safari bekommt Apple Karten, alle anderen (auch Chrome auf dem iPhone) Google Maps (`lib/mapLinks.ts`, vorher jedes Apple-Geraet). Seit 2026-11-22 folgt die ganze Lage-Karte dem Seitenthema (vorher war sie in beiden Themen hell und stach auf der dunklen Spot-Info-Seite heraus; am 2026-11-21 folgten fuer einen Tag nur die Kacheln): im Dark Mode dieselbe Karte gedaempft (`standardStyle("dark")`: dunkles, entsaettigtes Land knapp ueber der Seitenflaeche, blaugraues Meer, gedimmte Strassen, helle Namen), helle Glyphen und hellere Kategorienamen. Das Land bleibt heller als die Kachel (`surface`), damit die Kachel mit Linie und Schatten abhebt. Der Spot ist seit 2026-11-22 derselbe kleine Punkt wie auf /map (`.swd-pm-dot`): 12 px in der Tinte des Themas mit Ring in ihrem Gegenteil, also im Dark Mode ein heller Punkt mit dunklem Ring, redaktionell 16 px mit Hausmarke, Community offen (`spotDotHtml` in `lib/spotPin.ts`). Vorher war er ein 32-px-oranger Punkt im Pfirsich-Halo (2026-11-18) und damit eine zweite Spot-Sprache neben /map. Weil die Kachel auf dem Handy das Quellen-„i“ verdeckt, nennt die Ortskachel „Daten © OpenStreetMap-Mitwirkende“. Seit 2026-11-22 steht rechts neben dem Namen einer Ortskachel „Geöffnet“ (success-Gruen) oder „Geschlossen“ (danger-Rot), berechnet aus dem eingetragenen `opening_hours` zur Ortszeit des Spots (`locator/openingStatus.ts`). Das ist auf ausdruecklichen Wunsch die einzige Stelle ausserhalb eines Gefahrensatzes, an der Rot erscheint; vorher behauptete die Karte bewusst nie, ob ein Ort gerade offen ist. Der Status erscheint nur, wenn er sicher ablesbar ist: ohne Zeiten, ohne Spot-Zeitzone, bei Saisons, Schulferien, „PH off“, Sonnenauf-/-untergang oder einem offenen Ende nach dessen Beginn steht nichts. Die eingetragenen Zeiten bleiben darunter sichtbar.

**The Named Field Rule.** Wenn eine Karte eine physikalische Groesse als Flaechenfarbe zeichnet, benennt sie die Skala auf der Karte — mit derselben Farbsprache, die Diagramme und Vorhersagebalken verwenden (`lib/windScale.ts`), und mit Modell und Lauf. Das Feld lief bis 2026-11-16 auf einer eigenen kontinuierlichen Rampe ohne Legende: dieselbe Windgeschwindigkeit hatte im Balken eine andere Farbe als im Feld darunter, und nichts auf der Karte sagte, was die Farben bedeuten. Die Legende ist eine Beschriftung, keine Bedienflaeche; auf schmalen Viewports tritt sie zurueck, sobald das Sheet die Werte ausschreibt.

**The Single Surface Map Rule.** Seit dem Redesign vom 2026-11-19 (`frontend/src/public-map/`) ist `/map` EINE MapLibre-Flaeche fuer Spots, Wind und Wellen; der Modus tauscht nur Ebenen, nie die Kartentechnik (vorher: Leaflet fuer Spots, MapLibre fuer Wind/Wellen). Der Grund ist ein eigener, stark zurueckgenommener heller Vektorstil (`public-map/mapStyle.ts`, OpenFreeMap) statt der Carto-Raster; Ortsnamen liegen auf einer zweiten Karte ueber dem Feld. Die drei Modi sitzen als segmentierte Pille oben in der Mitte (aktive Pille mit Wort, vorher drei lose Woerter; bis 2026-11-20 lagen sie in der unteren Insel). Rechts steht ein Glyphenstapel aus Suche, Standort, Liste („Spots im Ausschnitt", nur als Glyphe) und – in Wind/Wellen – Ebenen. Im Modus Spots ist unten nichts ausser der Spot-Leiste nach einem Tipp. Ueber den Spots stehen keine Werte. Auf der Spots-Karte oeffnet ein Tipp unten eine Leiste nur mit Name, Region und „Zum Spot →" (Info-Seite). Auf Wind und Wellen liegt unten ein reiner Zeitregler (Stundenstreifen zum Vor- und Zurueckwischen, stufenlos, ohne Abspielen); mit gewaehltem Spot steht rechts darin „Zum Spot →" direkt zum Daten-Tab. Ein Forecast im Regler und eine schwebende Spot-Pille darueber folgen in einem naechsten Schritt (Stand 2026-11-20). Wind- und Wellenkarte zeigen keine Legende (Wellen bis 2026-11-21 mit Legende). Die Zeitleiste reicht in die Vergangenheit, soweit die Veroeffentlichung sie traegt: "Jetzt" steht in der Mitte unter der Nadel, links die vergangenen, rechts die kommenden Stunden; Datum klein und regular, rechts in derselben Zeile "Zum Spot" (Daten-Tab). Die Modi ersetzen den History-Eintrag statt einen neuen anzulegen – "Zurueck" verlaesst die Karte sofort. Wellenfarbe: ruhige See im Graublau der Windkarte bei 5 kn, Farbe erst ab gut 1 m, Deckkraft hoechstens 50 %. Das Land der Wellenkarte traegt dasselbe Graublau (Windkarte bei ~8 kn), die Kuestenlinie liegt auch hier ueber dem Feld. Wellenpfeile: eigenes, dichteres Raster (32–64 px), reichen bis an die echte Kueste (Wassermaske entscheidet, Kuestenzellen nehmen den Wert der naechsten Seezellen) und zeigen, wo veroeffentlicht, die Laufrichtung der Hauptduenung; die Farbe bleibt die Gesamtwelle. Keine Hover-Pille mehr: Ein Tipp (Finger oder Maus) auf einen beliebigen Punkt oder Spot in Wind/Wellen fuellt die Zeitleiste selbst mit dem Forecast (2026-11-21, vereinfacht statt eingebettetem Meteogramm): jede Stundenspalte traegt Windbalken mit Boee, Windwert, Windrichtung, Wellenhoehe und Duenungsrichtung – bei Wind und Wellen identisch, links ein fester Zeilenschluessel (Wind-/Wellen-Icon), die Nadel bleibt die Uhr. Kachel ~180 px statt ~330 px, damit die Karte darueber antippbar bleibt. Bewusst deckend, nicht transparent: Mikro-Zahlen ueber bewegten Partikeln waeren nicht lesbar. Spot = Spot-Vorhersage (mit Stand), freier Punkt = Feld-Zeitreihen; Wind setzt sich aus Kurzfrist- und weiterreichendem Modell zusammen (feinstes Modell gewinnt), Quelle einzeilig darunter; Koordinaten als Titel, Tipp-Marke, Schliessen-Kreuz. Schrift und Glyphen tragen auf der ganzen Public-Seite keinen Schatten, keinen Halo und keinen Drop-Shadow (2026-11-21, "komplett klar"); Kartennamen ohne Text-Halo; schwebende Elemente werden per margin statt translate(-50%) zentriert, damit Text nicht auf halben Pixeln liegt. Ausnahme: der weisse Zurueck-Pfeil ueber Fotos (back-glyph-on-photo) behaelt seinen Schatten, sonst verschwindet er im hellen Himmel. Wind zeichnet die Flaeche und wahlweise Partikel ODER Pfeile (Ebenen), nie beides (vorher beides zugleich). Partikel und Pfeile sind schlicht weiss, ohne Halo und ohne Leuchten. Partikel-Schweife sind Geometrie (jeder Partikel merkt sich seine letzten Positionen, die Flaeche wird je Frame geleert) – nicht mehr per Ueberblenden ausgeblichen, weil das einen grauen Restschleier ueber der Karte hinterliess (2026-11-21); Dichte und Deckkraft von Partikeln, Pfeilraster (~42–84 px) und Farbflaechen wurden gesenkt, damit die Grundkarte lesbar bleibt. Die Moduspille hat in allen Modi dieselbe Breite. Pfeil = Schaft + gefuellte Spitze (35 %), zeigt wohin Wind/Welle laeuft, Laenge waechst mit der Wurzel des Werts (14–24 px), Flaute unter 2 kn ist ein offener Kreis, fehlende Daten zeichnen nichts. Das Pfeilraster haengt an der Welt und ist zweistufig: die groben Punkte bleiben beim Zoomen stehen, die Zwischenpunkte blenden mit dem Zoom stufenlos ein und aus – kein Neu-Verteilen. Wellen sind eine Farbflaeche, deren Deckkraft mit der Hoehe waechst, plus Pfeile in Laufrichtung; die Farbe endet exakt an der Vektor-Kuestenlinie (Wassermaske), nicht an den groben Modellzellen, und das Land behaelt dieselben Farben wie auf der Windkarte. Auf der Windkarte liegt eine feine Kuestenlinie ueber der Farbe, damit das Land lesbar bleibt; die durchgehenden Kammlinien vom 2026-11-19 sind wieder entfernt. Die Kartenflaeche malt Wind und Wellen als FLIESSENDEN Verlauf (`public-map/fieldColors.ts`), dessen Stuetzpunkte die Haus-Windstufen in der Mitte jeder Stufe sind; das weicht fuer die Karte bewusst von der Named Field Rule (diskrete Stufen, 2026-11-16) ab, auf ausdruecklichen Wunsch nach einem Referenzbild. Balken und Diagramme ausserhalb der Karte behalten die Stufen. Bewertet wird weiterhin nichts.

Touch-Ziele sind mindestens `44px` hoch oder breit. Bewegliche Browserleisten und Safe Areas werden auf mobilen Vollbildansichten beruecksichtigt. Horizontales Scrollen ist nur in klar erkennbaren Rails, Tabellen und Diagrammen erlaubt.

**The Shared Edge Rule.** Oeffentliche Seiten erfinden keine eigenen Containerbreiten; sie verwenden `page`, `content`, `measure` oder — nur fuer eine Seite mit eigener Navigationsspalte — `measure-wide` und `measure-nav`. (Die Regel nannte frueher nur `page`, `content` und `measure`; `measure-wide` stand bereits als undokumentierte vierte Breite im Code. `measure-nav` ist `measure-wide` plus Navigationsspalte und Spaltenabstand: Eine Seite mit Seitennavigation zentriert dieses Paar, sonst sitzt der Text sichtbar rechts der Fensterachse, weil nur der Rest neben der Navigation zentriert wird.)

**The Image Breathing Rule.** Bildraster erhalten mehr vertikalen als horizontalen Abstand, damit das Stoebern ruhig und nicht katalogartig dicht wirkt.

## Elevation & Depth

Surfwinddata ist flach als Standard. Tiefe entsteht zuerst durch Tonwechsel, Fotografie, Ueberlagerung und feine Hairlines. Schatten markieren nur Elemente, die sich tatsaechlich ueber den Inhalt legen oder als schwebende Arbeitsflaeche verstanden werden muessen.

### Shadow Vocabulary

- **Card:** `0 12px 34px -18px rgba(36, 28, 23, 0.20)` fuer wenige leicht angehobene Eingaben, Auth-Dialoge und Kommentarboxen.
- **Float:** `0 24px 32px -16px rgba(36, 28, 23, 0.24), 0 48px 80px -24px rgba(36, 28, 23, 0.30)` fuer Modals, offene Suche und wirklich schwebende mobile Controls.

Beide Werte stehen einmal in `index.css` als `--sw-shadow-card` und `--sw-shadow-float`; `tailwind.config.js` liest sie von dort, handgeschriebenes CSS ebenfalls. Eigene `box-shadow`-Werte in Komponenten- oder Karten-CSS sind damit kein Spielraum mehr, sondern eine Abweichung. Ausgenommen ist der Glyphen-Halo der Karte (`--map-glyph-halo`, `--map-mark-halo`): Er ist keine Hoehe, sondern Lesbarkeit einer dunklen Marke auf einem hellen Raster.

**The Flat-by-Default Rule.** Eine normale Karte, ein Inhaltsband oder eine statische Infotafel erhaelt keinen Schatten. Eine Hairline oder ein Tonwechsel reicht.

**The Functional Lift Rule.** Schatten erklaeren Ebenen und Interaktion; sie sind kein dekorativer Glanzeffekt.

## Shapes

Ein sanft gerundetes Rechteck mit `card`-Radius ist die gemeinsame Form fuer Medien, Karten, Eingaben, Dialoge und Tafeln. Die konstante Rundung erzeugt Ruhe und verhindert eine beliebige Mischung aus kleinen und grossen Ecken. Vollrunde Formen sind echten Kreisen, Statuspunkten, Avataren, Slider-Griffen und Filter-Pills vorbehalten.

Konturen sind fein und neutral. Dicke Rahmen, doppelte Einfassungen und dekorative Kartenrahmen werden vermieden. Bilder werden sauber auf den gemeinsamen Radius beschnitten; vollbreite Hero-Bilder duerfen kantenlos sein.

**The One Corner Rule.** Neue rechteckige Komponenten verwenden `card`; `full` wird nur eingesetzt, wenn die Silhouette semantisch rund oder pillenfoermig ist.

## Components

### Actions and Buttons

- **Default:** Textaktion mit mindestens `44px` Touch-Hoehe; Hover wird durch Unterstreichung und leichte Opazitaetsaenderung sichtbar.
- **Inline Link:** dauerhaft unterstrichen, wenn er innerhalb von Fliesstext oder Hinweisen steht.
- **Outline:** neutrale Hairline, transparente Flaeche und ruhiger Hover auf `band`; fuer klar abgegrenzte sekundäre Aktionen.
- **Filled Exception:** nur fuer echte Abschlussaktionen wie Formular absenden, Dialog bestaetigen oder einen blockierten Vorgang erneut starten. Die Flaeche verwendet Ink statt Akzentfarbe und darf nie mehrere gleichrangige Buttons in einer Gruppe erzeugen.
- **Danger:** Kontur und Text aus den Danger-Tokens; keine vollflächig rote Standardaktion.
- **State:** `150ms` fuer Farbe/Opacity, Press-in bis `0.98`; unter `prefers-reduced-motion` keine Skalierung.

**The No Fat Button Rule.** Navigation, Discovery und normale Sekundaeraktionen erscheinen als Text oder Kontur, nicht als grosse gefuellte Flaeche.

### Chips

- **Unselected:** Surface mit einer feinen Line-Kontur.
- **Selected:** kompakte Ocean-Action-Flaeche mit weissem Text.
- **Use:** Filter, Kategorien und kleine Zustandsauswahl; nie als Ersatz fuer Hauptnavigation oder lange Labels.

### Cards / Containers

- **Spot- und Regionskarten:** bildgefuehrt, ohne umschliessende Flaeche und ohne Ruheschatten. Text sitzt direkt unter dem Bild.
- **Informationskarten:** keine Umrandung. Der Inhalt steht auf dem Grund der Seite; eine Kachel darf sich hoechstens durch einen minimalen Tonwechsel abheben.
- **Empty States:** gestrichelte Hairline, dezente Icon-Tafel und kurze naechste Handlung.
- **Interactive State:** gesamter Kartenlink erhaelt einen klaren Focus-Visible-Ring; Bildzoom oder Opazitaet bleibt subtil.

**The Unframed Tile Rule.** Eine Kachel bekommt keinen Rahmen. Ein Stroke zeichnet ein Kaestchen, und viele Kaestchen zerlegen eine Seite in Fragmente — gerade dort, wo gleichrangige Werte nebeneinander stehen und ohnehin als Gruppe gelesen werden. Abheben darf sich eine Kachel nur durch einen **minimalen Tonwechsel**: genau eine Tonstufe weg vom Grund (`--sw-tile`, 2% der Skala — im Light-Theme dunkler, im Dark-Theme heller; bis 2026-11-17 waren es 4%, die Kachel wirkte damit zu schwer), nie eine zweite Stufe obendrauf, nie Ton und Stroke zusammen, nie ein Schatten. Der Ton traegt dann die ganze Trennung, also braucht die Kachel genug Innenraum, damit die Flaeche ruhig wirkt und nicht eng. Rahmen bleiben den Dingen vorbehalten, die wirklich eine Kante haben: Eingaben, Dialoge, Overlays, Medien.

Bis 2026-11-14 galt hier das Gegenteil (Stroke erlaubt, Flaeche verboten). Beide Fassungen verfolgen dasselbe Ziel — keine Kaestchenseite —, die aktuelle erreicht es leiser.

**The Earned Line Rule.** Trennstriche sind kein Raster. Eine Liste gleichartiger Zeilen (Ausstattung, Angaben, Fakten) trennt durch Abstand, nicht durch Linien. Eine Hairline tritt erst auf, wo ein Wechsel der Art des Inhalts sonst unsichtbar bliebe.

### Inputs / Fields

- **Style:** Surface, neutrale Hairline, gemeinsamer Radius und mindestens `44px` Hoehe.
- **Focus:** klarer Ink-Ring oder bewusstes neutrales Border-Shift; nie gleichzeitig Ring, Border und Glow.
- **Search:** darf als groessere, schwebende Spezialkomponente auftreten. Einzelne Suchfelder bleiben stroke-frei und markieren Fokus durch eine kurze Ink-Unterstreichung.
- **Error / Disabled:** semantischer Text plus Icon oder konkrete Erklaerung; Farbe allein reicht nicht. Disabled bleibt lesbar und verliert Interaktionscursor.

### Notice Panels

- **Structure:** kleines, ruhiges Icon; kurze Ueberschrift; ein bis drei Saetze; optionale Textaktion.
- **Tone:** flaechenlos auf dem Seitengrund. Ein Hinweis traegt hoechstens eine schmale semantische Markierung (Icon, kurze Regel) — eine getoente Flaeche nur dort, wo eine Warnung wirklich den Blick zuerst braucht, und nie fuer einen neutralen Hinweis.
- **Density:** kompakt, aber nicht bannerartig laut. Hinweise duerfen die Fotografie und Hauptinformation nicht optisch dominieren.

### Navigation

- **Header:** transparent ueber Bildwelten und beim Scrollen zu einer ruhigen Surface; Wortmarke zentral oder klar verankert.
- **Active State:** Unterstreichung, Textgewicht oder kurzer Akzentstrich statt gefuellter Tabs.
- **Mobile:** Icon-Aktionen bleiben mindestens `44px`, Labels werden nur ausgeblendet, wenn das Icon eindeutig und mit `aria-label` versehen ist.
- **Daten-Unterseiten:** Info/Daten-Wechsel darf Dashboard-Charakter zeigen, bleibt aber Teil derselben Navigationssprache.

### Editorial Hero

Der Hero ist die Signaturkomponente: vollbreite Fotografie mit gepflegtem Fokuspunkt, optionalem sanftem Parallax und lokaler Kontrastschicht. Fehlende Bilder werden durch ein bewusst gestaltetes, dunkles Kuestenfeld mit sehr dezenter Windbewegung ersetzt. Bildnachweise sind immer sichtbar, aber visuell nachgeordnet.

### Data Instruments

Datenmodule verwenden `figures`, tabellarische Ziffern, kurze Versal-Labels und stabile Spalten. Farbe codiert nur etablierte Skalen oder Status. Diagramme priorisieren Vergleichbarkeit vor Dekoration und bieten Text-/Tabellenalternativen, wo die Grafik allein nicht ausreicht.

### Motion

Die Hauskurve ist `cubic-bezier(0.22, 1, 0.36, 1)` mit `150ms`, `200ms` und `300ms` fuer Zustandswechsel. Redaktionelle Sektionen duerfen einmalig sanft um maximal `24px` einblenden; Hero-Parallax bleibt langsam und wird auf Touchgeraeten sowie bei reduzierter Bewegung deaktiviert. Motion erklaert Zustand oder Tiefe und konkurriert nie mit dem Bild.

Eine einzige Ausnahme von der Hauskurve: der Schalter-Thumb in `ui/Switch` laeuft auf `ease-switch` (`cubic-bezier(0.32, 1.6, 0.55, 1)`) und schwingt dabei leicht ueber, so wie ein physischer Kippschalter einrastet; gedrueckt dehnt er sich auf die Seite, zu der er wandern wuerde. Das gilt nur fuer diesen einen Baustein — Panels, Sheets und Zustandswechsel bleiben auf der Hauskurve. (Vorher: ausnahmslos Hauskurve, lineare Thumb-Fahrt; geaendert am 2026-11-15, weil der Schalter als einziges Bedienelement direkt auf den Druck antwortet.)

## Do's and Don'ts

### Do:

- **Do** beginne Discovery-Seiten mit einem starken Bild, einer klaren Ortsidee und nur einer primaeren Such- oder Stoeberhandlung.
- **Do** nutze echte Spot-Fotografie mit gepflegtem Fokuspunkt, responsivem Crop, Alt-Text und sichtbarer Attribution.
- **Do** halte Light und Dark Mode gleich mild; pruefe Text, Icons, Konturen und Bild-Overlays in beiden Modi.
- **Do** kombiniere kleine UI-Schrift mit grossen Orts- und Kapitelueberschriften.
- **Do** nutze Textaktionen und Unterstreichungen als Standard; Konturbuttons sind die naechste Eskalationsstufe.
- **Do** trenne Inhalte mit Raum, Tonbaendern und Hairlines, bevor ein Schatten eingesetzt wird.
- **Do** verwende Hinweisfelder mit dezenten Icons, klarer Aussage und einer konkreten naechsten Handlung.
- **Do** bewahre mindestens `44px` grosse Touch-Ziele und einen sichtbaren Keyboard-Fokus.
- **Do** verwende Dashboard-Dichte nur fuer Daten, Vergleiche und operative Kontrollen.

### Don't:

- **Don't** verwende knallige, neonartige oder grossflaechig gesaettigte Farben.
- **Don't** baue Reihen aus schweren, gefuellten Buttons. Eine gefuellte Aktion ist eine seltene Ausnahme fuer einen eindeutigen Abschluss.
- **Don't** packe Spotkarten in weisse Boxen mit Standardschatten; Bild und Typografie tragen die Karte.
- **Don't** verwende MADE Mountain ausserhalb der Wortmarke oder Manrope als sichtbare zweite Fliesstextschrift.
- **Don't** erfinde neue Radien, Blautoene, Schatten, Containerbreiten oder freie Schriftgroessen.
- **Don't** behandle Orange oder Datengruen als generische CTA- oder Statusfarbe.
- **Don't** ueberfrachte Editorial-Seiten mit Dashboard-Modulen oder Datenansichten mit dekorativen Travel-Layouts.
- **Don't** verstecke wichtige Bedeutung ausschliesslich in Farbe, Icon oder Bewegung.
- **Don't** lege Text direkt auf unruhige Bilder, wenn der lokale Kontrast nicht stabil lesbar ist.
- **Don't** verwende Scroll-Animationen, Parallax oder Press-Effekte ohne Reduced-Motion-Fallback.
