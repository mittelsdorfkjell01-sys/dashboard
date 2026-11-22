import type { TranslationKey } from "./i18n";
import {
  CONTACT_TOPICS_ANCHOR,
  DATENSCHUTZ_SECTIONS,
  HELP_JUMP,
  IMPRESSUM_SECTIONS,
  TERMS_ACCESSIBILITY_ANCHOR,
  TERMS_SECTIONS,
} from "./infoSections";

/**
 * The burger menu's search: a small, static index of where a visitor can go,
 * built in the browser, with no request involved.
 *
 * It covers the features (account areas, the wind map) and the sections of
 * the five info and legal pages, which left the menu and are otherwise only
 * linked from the footer. Spots and regions are deliberately not in it: that
 * is the main search's job, and a second spot search in the menu would only
 * compete with it.
 */

export interface MenuSearchEntry {
  /** Stable React key. */
  id: string;
  /** What the result row says. */
  label: string;
  /** Where it is, shown under the label ("Datenschutz", "Funktion"). */
  context: string;
  /** Route, with `#anchor` for a section. */
  to: string;
  /** Extra words that should find this entry but are not in its label. */
  keywords?: string;
}

/** One feature the search finds. Kept here rather than imported from the menu
 *  so the menu component stays the only owner of its own row list. */
const FEATURES: { key: TranslationKey; to: string; keywords?: TranslationKey }[] = [
  { key: "accountNav.profile", to: "/konto/profil", keywords: "menu.search.keywords.profile" },
  { key: "accountNav.setup", to: "/konto/setup", keywords: "menu.search.keywords.setup" },
  { key: "accountNav.saved", to: "/konto/favoriten", keywords: "menu.search.keywords.saved" },
  { key: "accountNav.visited", to: "/konto/besucht" },
  { key: "accountNav.trips", to: "/konto/reisen", keywords: "menu.search.keywords.trips" },
  { key: "accountNav.addSpots", to: "/konto/spots", keywords: "menu.search.keywords.addSpots" },
  { key: "accountNav.settings", to: "/konto/einstellungen", keywords: "menu.search.keywords.settings" },
  { key: "menu.search.map", to: "/map", keywords: "menu.search.keywords.map" },
];

export function buildMenuSearchIndex(t: (key: TranslationKey) => string): MenuSearchEntry[] {
  const feature = t("menu.search.feature");
  const help = t("siteLinks.faq");
  const contact = t("siteLinks.contact");
  const terms = t("siteLinks.terms");
  const imprint = t("siteLinks.imprint");
  const privacy = t("siteLinks.privacy");
  const page = t("menu.search.page");

  const entries: MenuSearchEntry[] = FEATURES.map((f) => ({
    id: `f:${f.to}`,
    label: t(f.key),
    context: feature,
    to: f.to,
    keywords: f.keywords ? t(f.keywords) : undefined,
  }));

  // The pages themselves, so "Impressum" finds the page, not only its parts.
  entries.push(
    { id: "p:/fragen", label: help, context: page, to: "/fragen" },
    { id: "p:/kontakt", label: contact, context: page, to: "/kontakt", keywords: t("menu.search.keywords.contact") },
    { id: "p:/nutzungsbedingungen", label: terms, context: page, to: "/nutzungsbedingungen", keywords: "AGB" },
    { id: "p:/impressum", label: imprint, context: page, to: "/impressum" },
    { id: "p:/datenschutz", label: privacy, context: page, to: "/datenschutz", keywords: "DSGVO" },
  );

  for (const s of HELP_JUMP) {
    entries.push({ id: `h:${s.id}`, label: t(s.title), context: help, to: `/fragen#${s.id}`, keywords: t(s.key) });
  }
  entries.push({
    id: "c:topics",
    label: t("help.contact.topicsTitle"),
    context: contact,
    to: `/kontakt#${CONTACT_TOPICS_ANCHOR}`,
  });
  for (const s of IMPRESSUM_SECTIONS) {
    entries.push({ id: `i:${s.id}`, label: s.title, context: imprint, to: `/impressum#${s.id}` });
  }
  for (const s of TERMS_SECTIONS) {
    entries.push({ id: `t:${s.id}`, label: stripNumber(s.title), context: terms, to: `/nutzungsbedingungen#${s.id}` });
  }
  entries.push({
    id: "t:accessibility",
    label: t("terms.accessibility.q"),
    context: terms,
    to: `/nutzungsbedingungen#${TERMS_ACCESSIBILITY_ANCHOR}`,
  });
  for (const s of DATENSCHUTZ_SECTIONS) {
    entries.push({ id: `d:${s.id}`, label: stripNumber(s.title), context: privacy, to: `/datenschutz#${s.id}` });
  }
  return entries;
}

/** "8. Cookies und lokale Speicherung" → "Cookies und lokale Speicherung": the
 *  number orders the page, it means nothing in a result list. */
function stripNumber(title: string): string {
  return title.replace(/^\d+\.\s*/, "");
}

/** Case-, accent- and ß-insensitive, so "Datenschutz" and "datenschütz" or
 *  "strasse" and "Straße" meet. */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ß/g, "ss");
}

/**
 * Every word of the query must appear somewhere in the entry. Hits in the
 * label rank above hits only in the context or keywords, and a label that
 * starts with the query ranks first.
 */
export function searchMenu(index: MenuSearchEntry[], query: string, limit = 8): MenuSearchEntry[] {
  const words = normalize(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const scored: { entry: MenuSearchEntry; score: number; order: number }[] = [];
  index.forEach((entry, order) => {
    const label = normalize(entry.label);
    const hay = `${label} ${normalize(entry.context)} ${normalize(entry.keywords ?? "")}`;
    if (!words.every((w) => hay.includes(w))) return;
    const first = words[0];
    const score = label.startsWith(first) ? 0 : words.every((w) => label.includes(w)) ? 1 : 2;
    scored.push({ entry, score, order });
  });
  scored.sort((a, b) => a.score - b.score || a.order - b.order);
  return scored.slice(0, limit).map((s) => s.entry);
}
