import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

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
      "no-restricted-syntax": [
        "error",
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
      ],
    },
  }
);
