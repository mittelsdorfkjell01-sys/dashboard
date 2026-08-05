import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, ".", "");
  const adminBuild = env.VITE_INCLUDE_ADMIN === "true";
  return {
    plugins: [react()],
    define: {
      __INCLUDE_ADMIN__: JSON.stringify(command === "serve" || adminBuild),
      __ADMIN_DEPLOY__: JSON.stringify(command === "build" && adminBuild),
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
