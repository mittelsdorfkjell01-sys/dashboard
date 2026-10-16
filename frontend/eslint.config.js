import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

/**
 * Design-token enforcement selectors, shared by every config block below.
 *
 * These live in a constant rather than inline because flat config *replaces*
 * a rule's options when a later block names the same rule. A block that adds
 * its own no-restricted-syntax entries (the i18n guard) therefore has to
 * spread these back in, or it would silently switch the token rules off for
 * exactly the files it covers.
 */
const designTokenSelectors = [
    {
      selector: "Literal[value=/(?:^|[\\s`])(?:text|bg|border)-(?:red|green)-\\d{2,3}(?:$|[\\s\\/])/]",
      message: "Use text-danger/bg-danger-bg/border-danger-border (or the admin-danger/admin-success equivalents in admin/*) instead of raw Tailwind red/green utilities.",
    },
    {
      selector: "TemplateElement[value.raw=/(?:^|[\\s`])(?:text|bg|border)-(?:red|green)-\\d{2,3}(?:$|[\\s\\/])/]",
      message: "Use text-danger/bg-danger-bg/border-danger-border (or the admin-danger/admin-success equivalents in admin/*) instead of raw Tailwind red/green utilities.",
    },
    // Only shadow-float/shadow-card (public) and shadow-admin-pop/
    // shadow-admin-dialog (admin) are allowed — see tailwind.config.js.
    {
      selector: "Literal[value=/(?:^|\\s)shadow-(?:sm|md|lg|xl|2xl|inner)(?:$|\\s)/]",
      message: "Use shadow-float/shadow-card (public) or shadow-admin-pop/shadow-admin-dialog (admin) instead of the generic Tailwind shadow-* scale.",
    },
    {
      selector: "TemplateElement[value.raw=/(?:^|\\s)shadow-(?:sm|md|lg|xl|2xl|inner)(?:$|\\s)/]",
      message: "Use shadow-float/shadow-card (public) or shadow-admin-pop/shadow-admin-dialog (admin) instead of the generic Tailwind shadow-* scale.",
    },
    // The type scale is the single source of truth for font sizes (see
    // tailwind.config.js `fontSize`) — arbitrary text-[Npx] silently
    // drifts and can't be found/rationalized later. Extend the scale
    // (name a role, or add a sz-N holding value) instead.
    {
      selector: "Literal[value=/(?:^|\\s)text-\\[\\d+px\\](?:$|\\s)/]",
      message: "Arbitrary text-[Npx] is not allowed — add/reuse a fontSize token in tailwind.config.js instead.",
    },
    {
      selector: "TemplateElement[value.raw=/(?:^|\\s)text-\\[\\d+px\\](?:$|\\s)/]",
      message: "Arbitrary text-[Npx] is not allowed — add/reuse a fontSize token in tailwind.config.js instead.",
    },
];

export default tseslint.config(
  { ignores: ["dist", "coverage"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.es2022 },
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "no-empty": ["error", { "allowEmptyCatch": true }],
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      // Design-token enforcement: error/success colour must come from the
      // sw-danger/sw-success (public) or admin-danger/admin-success (admin)
      // tokens, never raw Tailwind red/green — the raw shades don't adapt to
      // dark mode and drift silently (see frontend/AGENTS.md).
      "no-restricted-syntax": ["error", ...designTokenSelectors],
    },
  },
  {
    // i18n regression guard, scoped to the surfaces already migrated to
    // react-i18next (see src/lib/i18n/). The extraction runs in tranches, so a
    // repository-wide rule would fire in the ~125 files still holding their
    // German copy inline and make CI unusable. Instead this list grows with
    // each tranche: once a file is on it, hard-coded German cannot come back,
    // which is the part that actually decays without enforcement.
    files: [
      "src/main.tsx",
      "src/components/AccountMenu.tsx",
      "src/components/SpotCommunity.tsx",
      "src/components/Footer.tsx",
      "src/components/Header.tsx",
      "src/pages/account/AccountLayout.tsx",
      "src/pages/account/Einstellungen.tsx",
      "src/pages/account/MeinSetup.tsx",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...designTokenSelectors,
        {
          // Two or more consecutive letters as JSX child text. Punctuation- and
          // whitespace-only nodes (separators like · or —, the indentation
          // between elements) stay allowed on purpose.
          selector: "JSXText[value=/[A-Za-z\u00C0-\u024F]{2,}/]",
          message: "This file is i18n-migrated: move the text into src/lib/i18n/locales/de.ts and render it with t(\"key\").",
        },
        {
          // User-visible attributes only. className/id/role literals are never
          // shown to anyone, so they are deliberately not covered.
          selector: "JSXAttribute[name.name=/^(label|aria-label|placeholder|title|alt)$/] > Literal[value=/[A-Za-z\u00C0-\u024F]{2,}/]",
          message: "This file is i18n-migrated: move the text into src/lib/i18n/locales/de.ts and render it with t(\"key\").",
        },
      ],
    },
  }
);
