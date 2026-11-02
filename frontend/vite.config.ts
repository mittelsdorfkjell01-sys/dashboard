import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, ".", "");
  // The CARTO basemap key lives in the shared root .env as CARTO_API_KEY (a
  // backend var without the VITE_ prefix, so Vite wouldn't otherwise expose it).
  // `..` resolves to the repo root relative to the frontend cwd the build runs in.
  const rootEnv = loadEnv(mode, "..", "");
  const adminBuild = env.VITE_INCLUDE_ADMIN === "true";
  // CARTO basemap key: whatever the deploy sets in the environment (e.g. Vercel)
  // wins, then the frontend's own VITE_CARTO_KEY, then the shared root .env
  // CARTO_API_KEY. Empty = keyless tiles. `process` is read via globalThis so
  // this stays typecheckable without @types/node.
  const proc = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {};
  const cartoKey =
    proc.VITE_CARTO_KEY ||
    proc.CARTO_API_KEY ||
    env.VITE_CARTO_KEY ||
    rootEnv.CARTO_API_KEY ||
    rootEnv.VITE_CARTO_KEY ||
    "";
  return {
    plugins: [
      react(),
      {
        name: "admin-deployment-noindex",
        transformIndexHtml() {
          if (command !== "build" || !adminBuild) return [];
          return [
            {
              tag: "meta",
              attrs: {
                name: "robots",
                content: "noindex, nofollow, noarchive, nosnippet",
              },
              injectTo: "head",
            },
          ];
        },
      },
    ],
    optimizeDeps: {
      // MapLibre ships its worker as a sibling ESM asset. Pre-bundling the
      // package rewrites that URL into Vite's deps cache where the worker does
      // not exist, leaving the weather map without a renderer in dev/tests.
      exclude: ["maplibre-gl"],
    },
    build: {
      rolldownOptions: {
        output: {
          // Keep the optional Wind mode's map engine out of the feature
          // chunk. Spot mode never downloads either chunk, while Wind mode
          // can cache the comparatively stable vendor payload separately.
          codeSplitting: {
            groups: [
              {
                name: "maplibre",
                test: /node_modules[\\/]maplibre-gl/,
                maxSize: 750_000,
              },
            ],
          },
        },
      },
    },
    define: {
      __INCLUDE_ADMIN__: JSON.stringify(command === "serve" || adminBuild),
      __ADMIN_DEPLOY__: JSON.stringify(command === "build" && adminBuild),
      __CARTO_KEY__: JSON.stringify(cartoKey),
    },
    server: {
      port: 5173,
      open: true,
    },
    test: {
      exclude: ["e2e/**", "node_modules/**"],
      coverage: {
        provider: "v8",
        reporter: ["text", "json-summary", "lcov"],
        thresholds: {
          lines: 50,
          statements: 46,
          branches: 42,
          functions: 35,
        },
      },
    },
  };
});
