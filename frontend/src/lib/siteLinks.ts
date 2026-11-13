/**
 * The five info and legal links, in the order they are shown.
 *
 * One list, two surfaces: the footer and the account menu (both its desktop
 * dropdown and its mobile sheet) render exactly these, and they drifted into
 * two hand-kept copies before — same routes, same labels, maintained twice.
 * Adding or renaming a legal page is the kind of change that must not depend
 * on remembering the second place.
 *
 * Labels live in the i18n catalogue under `siteLinks.*`, not here, so this
 * stays a pure route list.
 */
export const SITE_LINKS = [
  { to: "/fragen", key: "siteLinks.faq" },
  // Contact is a section of the same page now, reachable as its own entry in
  // that page's side navigation; the old standalone route redirects to this
  // very anchor (see main.tsx). The project background has no entry of its
  // own any more — it is one of the page's sections, not a sibling of it.
  { to: "/fragen#kontakt", key: "siteLinks.contact" },
  { to: "/nutzungsbedingungen", key: "siteLinks.terms" },
  { to: "/impressum", key: "siteLinks.imprint" },
  { to: "/datenschutz", key: "siteLinks.privacy" },
] as const;
