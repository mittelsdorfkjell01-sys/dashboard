# Frontend guidance

- React/Vite entry point: `src/main.tsx`; API contracts: `src/lib/api.ts`; backend-to-view adaptation: `src/lib/adapt.ts`.
- Pages coordinate data and layout; reusable display behavior belongs in `src/components/`; pure transformations belong in `src/lib/`.
- Preserve loading, empty, error, keyboard, reduced-motion, and responsive states.
- When backend response fields change, update `src/lib/api.ts`, adapters, fixtures, and focused tests together.
- Do not commit `tsconfig.tsbuildinfo` or build output.
- Run focused Vitest tests first, then `npm --prefix frontend run build` for cross-cutting TypeScript/UI changes.
- Use the `impeccable` skill only when the task is genuinely visual or UX-related.

## Three design systems, not one

This app renders three visually distinct registers. That split is intentional
— do not "fix" one to look like another, and do not treat a difference
between them as drift.

1. **Public editorial** (Landing, Suche, Spot-Info-Tab, Region, Karte). Token
   source: `:root`/`html[data-theme="dark"]` in `src/index.css`, wired into
   Tailwind via `tailwind.config.js` (`ink`/`muted`/`line`/`surface`/`band`/
   `teal`/`orange`/`green`/`danger`/`success`). Two shadows only:
   `shadow-float`, `shadow-card`. Type scale: `caption`/`label`/`ui`/`body`/
   `title`/`display-*`/`editorial-*` plus the numeric `sz-N` holding scale
   (see below) — never a raw `text-[Npx]`.
2. **Spot-Daten tab** (`SpotDataHeader`, `Meteogram`, `WindClimatologyModule`).
   Same colour tokens as public editorial (it's still the public site), but a
   deliberately denser "weather instrument" type register: small uppercase
   `data-label`/`data-value`/`data-caption`, dense grids, pill toggles,
   segmented controls. Do not loosen it to match the Info tab's airy
   travel-magazine spacing — the two tabs are documented in
   `tailwind.config.js` as "two different products sharing one brand."
3. **Admin back office** (`src/pages/Admin*`, `src/components/admin/**`).
   A fully independent, dark-only, monochrome token set — `--a-*` variables
   in `src/components/admin/ui/admin-theme.css`, exposed to Tailwind as
   `admin-*` (`admin-bg`/`admin-surface`/`admin-fg`/`admin-primary`/
   `admin-danger`/…) and `shadow-admin-pop`/`shadow-admin-dialog`. UI
   primitives live in `src/components/admin/ui/index.tsx` (`Button`,
   `ButtonLink`, `Input`, `Textarea`, `SearchInput`, `Badge`,
   `adminFieldClass`). **Never import from `src/components/ui/*` (the public
   atoms) inside `src/pages/Admin*` or `src/components/admin/**`** — the
   public `Input`/`Button` carry a teal focus ring and light-mode colours
   that break in the dark admin scope.

### Enforcement

`eslint.config.js` blocks the two most common ways these systems leak into
each other:

- Raw Tailwind `text-red-*`/`bg-red-*`/`text-green-*`/etc. — use
  `text-danger`/`bg-danger-bg`/`text-success` (public) or `text-admin-danger`/
  `bg-admin-danger-bg` (admin).
- Raw `shadow-sm/md/lg/xl/2xl/inner` — use `shadow-float`/`shadow-card`
  (public) or `shadow-admin-pop`/`shadow-admin-dialog` (admin).
- Arbitrary `text-[Npx]` — extend `fontSize` in `tailwind.config.js` instead
  (either a named role, or a numeric `sz-N` holding value if the role hasn't
  been identified yet).

Nothing currently lints the `components/ui` → `components/admin/**` import
boundary itself — check for that manually when reviewing admin-page changes.
