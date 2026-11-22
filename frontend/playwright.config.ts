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
    { name: "firefox-desktop", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit-desktop", use: { ...devices["Desktop Safari"] } },
    { name: "chromium-mobile", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "npm run build:e2e && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173/impressum",
    reuseExistingServer: !process.env.CI,
  },
});
