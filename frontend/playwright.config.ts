import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: "http://127.0.0.1:4173",
    // Public E2E assertions exercise the German source catalogue. Pin the
    // browser locale so CI runners with an English OS do not select English.
    locale: "de-DE",
    trace: "retain-on-failure",
    reducedMotion: "reduce",
  },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "firefox-desktop",
      use: { ...devices["Desktop Firefox"] },
      testMatch: [
        "**/accessibility.spec.ts",
        "**/admin-theme.spec.ts",
        "**/editorial-style.spec.ts",
        "**/help-page.spec.ts",
        "**/public-core.spec.ts",
        "**/search.spec.ts",
      ],
    },
    {
      name: "webkit-desktop",
      use: { ...devices["Desktop Safari"] },
      testMatch: [
        "**/accessibility.spec.ts",
        "**/admin-theme.spec.ts",
        "**/editorial-style.spec.ts",
        "**/help-page.spec.ts",
        "**/public-core.spec.ts",
        "**/search.spec.ts",
      ],
    },
    {
      name: "chromium-mobile",
      use: { ...devices["Pixel 5"] },
      testMatch: [
        "**/accessibility.spec.ts",
        "**/daten-page.spec.ts",
        "**/editorial-style.spec.ts",
        "**/help-page.spec.ts",
        "**/landing-loading.spec.ts",
        "**/public-core.spec.ts",
        "**/public-resilience.spec.ts",
        "**/search.spec.ts",
        "**/wind-climatology-v3-public.spec.ts",
      ],
    },
  ],
  webServer: {
    command: "npm run build:e2e && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173/impressum",
    reuseExistingServer: !process.env.CI,
  },
});
