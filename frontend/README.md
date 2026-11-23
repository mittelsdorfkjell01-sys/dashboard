# Surfwinddata frontend

React, Vite, TypeScript and Tailwind frontend for the public Surfwinddata site
and the separately deployed administration dashboard. The UI consumes the
FastAPI routes from this repository; catalogue, search and map data are not
local placeholders.

## Applications and routes

- Public: landing page, search, spot and region details, maps, community and
  account routes.
- Admin: editorial workflows and operational tools below `/admin`.
- The public production bundle excludes admin code unless
  `VITE_INCLUDE_ADMIN=true`; see `../DEPLOY-VERCEL.md`.

Wind, wave and tide forecast surfaces are under active development. Preserve
their source, units, timestamps and uncertainty states when changing adjacent
UI code.

## Commands

```bash
npm install
npm run dev
npm run lint
npm run test
npm run build
```

The development server defaults to `http://localhost:5173` and proxies API
requests to the local FastAPI service. Build and test scripts are defined in
`package.json`.

## Main entry points

```
src/main.tsx              public/admin router bootstrap
src/pages/                route-level screens
src/components/           reusable public and admin UI
src/lib/api.ts            typed API client contracts
src/weather-map/          forecast map and overlays
e2e/                      Playwright user-flow checks
```

Reuse the design tokens in `tailwind.config.js` and `src/index.css` instead of
introducing route-local colors or spacing scales.
