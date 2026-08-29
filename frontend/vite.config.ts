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
    plugins: [react()],
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
    },
  };
});
