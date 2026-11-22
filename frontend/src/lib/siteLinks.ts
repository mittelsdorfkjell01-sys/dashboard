/**
 * The five info and legal links, in the order they are shown.
 *
 * Rendered by the footer only. The burger menu dropped them as rows (Nov
 * 2026); its search reaches the pages and their sections instead, through
 * lib/menuSearch.ts and the section lists in lib/infoSections.ts.
 *
 * Labels live in the i18n catalogue under `siteLinks.*`, not here, so this
 * stays a pure route list.
 */
export const SITE_LINKS = [
  { to: "/fragen", key: "siteLinks.faq" },
  // Contact is its own page (pages/Kontakt.tsx) — it is what a visitor comes
  // to do, so it is a destination, not an anchor inside the help page. The
  // project background has no entry of its own: it is one of that page's
  // sections, not a sibling of it.
  { to: "/kontakt", key: "siteLinks.contact" },
  { to: "/nutzungsbedingungen", key: "siteLinks.terms" },
  { to: "/impressum", key: "siteLinks.imprint" },
  { to: "/datenschutz", key: "siteLinks.privacy" },
] as const;
