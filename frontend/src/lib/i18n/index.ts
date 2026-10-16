/**
 * i18next setup for the public site.
 *
 * Deliberately minimal for now: one bundled language, no detector, no HTTP
 * backend. The site is German-only, and the point of this layer at this stage
 * is *extraction* — getting user-facing copy out of 129 component files and
 * behind keys — not shipping a second language. Translation comes later, and
 * when it does only this file changes:
 *
 *   1. add `locales/en.ts` (same shape as `de`; TypeScript enforces that),
 *   2. register it under `resources`,
 *   3. drive `lng` from PrefsContext, which already owns the persisted display
 *      preferences (units) and syncs them to `app_users.preferences`.
 *
 * Until step 3 exists there is no language switcher, so no Suspense boundary
 * and no `initAsync` dance is needed — `initReactI18next` resolves synchronously
 * with a bundled catalogue, which keeps the existing render tree untouched.
 */
import i18next, { type ParseKeys } from "i18next";
import { initReactI18next } from "react-i18next";

import { de } from "./locales/de";

export const DEFAULT_LOCALE = "de" as const;

export const resources = { de: { translation: de } } as const;

void i18next.use(initReactI18next).init({
  resources,
  lng: DEFAULT_LOCALE,
  fallbackLng: DEFAULT_LOCALE,
  defaultNS: "translation",
  // German is the source language, so a missing key is a bug in our catalogue,
  // not a missing translation. Surfacing the key itself makes that obvious in
  // development instead of rendering an empty element.
  returnEmptyString: false,
  interpolation: {
    // React escapes interpolated values already; letting i18next escape them
    // too turns "Über uns" into "&#220;ber uns" at render time.
    escapeValue: false,
  },
});

/**
 * Every key the catalogue defines, as a union of string literals.
 *
 * Needed wherever a key is carried in a data structure instead of written at
 * the `t()` call site — a nav table, a shared link list. Typing such a field
 * `string` would quietly switch the compile-time key checking back off for
 * exactly those entries, which are the ones nobody re-reads.
 */
export type TranslationKey = ParseKeys;

export default i18next;
