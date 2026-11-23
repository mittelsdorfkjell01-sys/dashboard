import type { TranslationKey } from "./i18n";

/**
 * The sections of the five info and legal pages, as data.
 *
 * Two readers: the pages render their headings (and anchors) from these lists,
 * and the burger menu's search indexes them. One list, so a renamed or added
 * section cannot leave the search pointing at a heading that no longer exists.
 *
 * Anchors are part of the URL contract — identical in every language. The
 * legal pages are German-only prose, so their titles are plain strings; the
 * help and contact pages are translated, so theirs are catalogue keys.
 */

// --- /fragen ---------------------------------------------------------------

export const HELP_ANCHOR = {
  safety: "sicherheit",
  project: "projekt",
  spots: "spots",
  weather: "wetter",
  season: "saison",
  map: "karte",
  account: "konto",
  contribute: "mitmachen",
  /** Entry-level anchors, linked from outside the page or from other answers. */
  regionUnknown: "regionale-windverfuegbarkeit",
  spotSuggest: "spot-vorschlagen",
  community: "community-beitraege",
} as const;

/**
 * Navigation order of the help page: every section, including the
 * hand-laid-out ones.
 *
 * `key` is the one-word keyword the sticky column shows (it has 13.5rem to
 * work with); `title` is the section's own heading, which the bottom jump menu
 * shows because it has the width for it. Both are what the filters match, so
 * "Gezeiten" finds "Wetter, Wellen & Gezeiten".
 */
export const HELP_JUMP: { id: string; key: TranslationKey; title: TranslationKey }[] = [
  { id: HELP_ANCHOR.safety, key: "help.jump.safety", title: "help.section.safety" },
  { id: HELP_ANCHOR.project, key: "help.jump.project", title: "help.section.project" },
  { id: HELP_ANCHOR.spots, key: "help.jump.spots", title: "help.section.spots" },
  { id: HELP_ANCHOR.weather, key: "help.jump.weather", title: "help.section.weather" },
  { id: HELP_ANCHOR.season, key: "help.jump.season", title: "help.section.season" },
  { id: HELP_ANCHOR.map, key: "help.jump.map", title: "help.section.map" },
  { id: HELP_ANCHOR.account, key: "help.jump.account", title: "help.section.account" },
  { id: HELP_ANCHOR.contribute, key: "help.jump.contribute", title: "help.section.contribute" },
];

// --- /kontakt --------------------------------------------------------------

export const CONTACT_TOPICS_ANCHOR = "themen";

// --- legal pages -----------------------------------------------------------

export interface LegalSection {
  id: string;
  title: string;
}

export const IMPRESSUM_SECTIONS = [
  { id: "angaben", title: "Angaben gemäß § 5 DDG" },
  { id: "kontakt", title: "Kontakt" },
  { id: "verantwortlich", title: "Verantwortlich für den Inhalt" },
] as const satisfies readonly LegalSection[];

export const DATENSCHUTZ_SECTIONS = [
  { id: "verantwortlicher", title: "1. Verantwortlicher und Datenschutzkontakt" },
  { id: "websiteaufruf", title: "2. Websiteaufruf, Server-Protokolle und Missbrauchsschutz" },
  { id: "konto", title: "3. Konto, Bestätigung, Anmeldung und Passwortwiederherstellung" },
  { id: "einstellungen", title: "4. Favoriten, Sportarten, Einheiten und persönliche Einstellungen" },
  { id: "setup", title: "5. Rider- und Kite-Setup (Personalisierung)" },
  { id: "beitraege", title: "6. Spotvorschläge und Community-Beiträge" },
  { id: "reichweite", title: "7. Nutzungsereignisse und Reichweitenmessung" },
  { id: "cookies", title: "8. Cookies und lokale Speicherung" },
  { id: "dienste", title: "9. Dienste und Empfänger (Auftragsverarbeiter)" },
  { id: "drittlaender", title: "10. Übermittlung in Drittländer" },
  { id: "speicherdauer", title: "11. Speicherdauer, Kontolöschung und Backups" },
  { id: "rechtsgrundlagen", title: "12. Rechtsgrundlagen im Überblick" },
  { id: "rechte", title: "13. Ihre Rechte und zuständige Aufsichtsbehörde" },
] as const satisfies readonly LegalSection[];

export const TERMS_SECTIONS = [
  { id: "anbieter", title: "1. Anbieter und Angebot" },
  { id: "verfuegbarkeit", title: "2. Leistung und Verfügbarkeit" },
  { id: "konto", title: "3. Konto und Mindestalter" },
  { id: "nutzerinhalte", title: "4. Nutzerinhalte und Regeln" },
  { id: "rechte", title: "5. Rechte an Inhalten" },
  { id: "moderation", title: "6. Moderation und Entfernung" },
  { id: "meldung", title: "7. Meldung rechtswidriger Inhalte (Notice-and-Action)" },
  { id: "haftung", title: "8. Haftung und Hinweise" },
  { id: "beendigung", title: "9. Beendigung" },
  { id: "aenderungen", title: "10. Änderungen dieser Bedingungen" },
  { id: "recht", title: "11. Anwendbares Recht" },
] as const satisfies readonly LegalSection[];

/** The terms' last section is the translated accessibility statement, so its
 *  title is a catalogue key (`terms.accessibility.q`), not a string here. */
export const TERMS_ACCESSIBILITY_ANCHOR = "barrierefreiheit";

export type ImpressumSectionId = (typeof IMPRESSUM_SECTIONS)[number]["id"];
export type DatenschutzSectionId = (typeof DATENSCHUTZ_SECTIONS)[number]["id"];
export type TermsSectionId = (typeof TERMS_SECTIONS)[number]["id"];

/** Title of a legal section by id — the page renders through this, so it can
 *  only ever show a heading the search index also knows. */
export function legalTitle(list: readonly LegalSection[], id: string): string {
  const found = list.find((s) => s.id === id);
  if (!found) throw new Error(`Unknown legal section: ${id}`);
  return found.title;
}
