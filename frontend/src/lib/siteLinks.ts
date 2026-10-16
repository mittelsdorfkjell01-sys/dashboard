/**
 * The six info and legal links, in the order they are shown.
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
  { to: "/faq", key: "siteLinks.faq" },
  { to: "/kontakt", key: "siteLinks.contact" },
  { to: "/ueber-uns", key: "siteLinks.about" },
  { to: "/nutzungsbedingungen", key: "siteLinks.terms" },
  { to: "/impressum", key: "siteLinks.imprint" },
  { to: "/datenschutz", key: "siteLinks.privacy" },
] as const;
