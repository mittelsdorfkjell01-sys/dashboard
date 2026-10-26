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

Die oeffentliche Vollbildkarte ist eine begruendete Ausnahme: Sie bleibt als funktionale, helle Kartenarbeitsflaeche theme-unabhaengig, waehrend Panels und Controls die gemeinsamen Komponentenregeln verwenden. Kartenfarben werden nicht als allgemeine Produkttokens wiederverwendet.

Touch-Ziele sind mindestens `44px` hoch oder breit. Bewegliche Browserleisten und Safe Areas werden auf mobilen Vollbildansichten beruecksichtigt. Horizontales Scrollen ist nur in klar erkennbaren Rails, Tabellen und Diagrammen erlaubt.

**The Shared Edge Rule.** Oeffentliche Seiten erfinden keine eigenen Containerbreiten; sie verwenden `page`, `content` oder `measure`.

**The Image Breathing Rule.** Bildraster erhalten mehr vertikalen als horizontalen Abstand, damit das Stoebern ruhig und nicht katalogartig dicht wirkt.

## Elevation & Depth

Surfwinddata ist flach als Standard. Tiefe entsteht zuerst durch Tonwechsel, Fotografie, Ueberlagerung und feine Hairlines. Schatten markieren nur Elemente, die sich tatsaechlich ueber den Inhalt legen oder als schwebende Arbeitsflaeche verstanden werden muessen.

### Shadow Vocabulary

- **Card:** `0 12px 34px -18px rgba(36, 28, 23, 0.20)` fuer wenige leicht angehobene Eingaben, Auth-Dialoge und Kommentarboxen.
- **Float:** `0 24px 32px -16px rgba(36, 28, 23, 0.24), 0 48px 80px -24px rgba(36, 28, 23, 0.30)` fuer Modals, offene Suche und wirklich schwebende mobile Controls.

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
- **Informationskarten:** Surface oder Band, Hairline nur wenn fuer Trennung erforderlich.
- **Empty States:** gestrichelte Hairline, dezente Icon-Tafel und kurze naechste Handlung.
- **Interactive State:** gesamter Kartenlink erhaelt einen klaren Focus-Visible-Ring; Bildzoom oder Opazitaet bleibt subtil.

### Inputs / Fields

- **Style:** Surface, neutrale Hairline, gemeinsamer Radius und mindestens `44px` Hoehe.
- **Focus:** klarer Ink-Ring oder bewusstes neutrales Border-Shift; nie gleichzeitig Ring, Border und Glow.
- **Search:** darf als groessere, schwebende Spezialkomponente auftreten. Einzelne Suchfelder bleiben stroke-frei und markieren Fokus durch eine kurze Ink-Unterstreichung.
- **Error / Disabled:** semantischer Text plus Icon oder konkrete Erklaerung; Farbe allein reicht nicht. Disabled bleibt lesbar und verliert Interaktionscursor.

### Notice Panels

- **Structure:** kleines, ruhiges Icon; kurze Ueberschrift; ein bis drei Saetze; optionale Textaktion.
- **Tone:** `band` fuer neutrale Hinweise, semantisch getoente helle Flaechen nur fuer Warnung, Fehler oder Erfolg.
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
