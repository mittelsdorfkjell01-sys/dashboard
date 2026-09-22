import { expect, test } from "@playwright/test";

test("Sportarten und Bedingungen werden validiert und im Konto gespeichert", async ({ page }, testInfo) => {
  let account = {
    id: "04c5fb5b-44c2-494b-b5bf-4817517339ef",
    email: "surfer@example.com",
    displayName: "Surfer",
    createdAt: "2026-01-01T10:00:00+00:00",
    emailVerified: true,
    pendingEmail: null,
    mailAvailable: false,
    preferences: {} as Record<string, unknown>,
  };
  let saved: Record<string, unknown> | null = null;
  const cors = {
    "access-control-allow-origin": "http://127.0.0.1:4173",
    "access-control-allow-credentials": "true",
    "access-control-allow-methods": "GET, PATCH, OPTIONS",
    "access-control-allow-headers": "content-type,x-csrf-token",
  };

  await page.route("http://127.0.0.1:8000/account/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: cors });
    } else if (path === "/account/me") {
      await route.fulfill({ json: account, headers: cors });
    } else if (path === "/account/favorites" || path === "/account/submissions") {
      await route.fulfill({ json: { items: [], hasMore: false }, headers: cors });
    } else if (path === "/account/preferences" && request.method() === "PATCH") {
      saved = request.postDataJSON() as Record<string, unknown>;
      account = { ...account, preferences: { ...account.preferences, ...saved } };
      await route.fulfill({ json: account, headers: cors });
    } else {
      await route.fulfill({ status: 404, headers: cors });
    }
  });

  await page.goto("/konto/einstellungen");
  await expect(page.getByRole("heading", { name: "Sportarten & Bedingungen" })).toBeVisible();
  await page.getByRole("checkbox", { name: "Kitesurfen" }).check();
  await page.getByRole("checkbox", { name: "Wingfoilen" }).check();

  const wind = page.getByRole("group", { name: "Wind · kn" });
  await wind.getByLabel("Ab").fill("30");
  await wind.getByLabel("Bis").fill("12");
  await expect(page.getByText("Bei Kitesurfen ist der minimale Wind höher als der maximale Wind.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Bedingungen speichern" })).toBeDisabled();

  await wind.getByLabel("Ab").fill("12");
  await wind.getByLabel("Bis").fill("28");
  await page.getByRole("button", { name: "Wingfoilen" }).click();
  await page.getByRole("group", { name: "Wellen · m" }).getByLabel("Bis").fill("1.5");
  await page.getByRole("button", { name: "Bedingungen speichern" }).click();
  await expect(page.getByText("Sportarten und Bedingungen gespeichert.")).toBeVisible();
  expect(saved).toEqual({
    sports: ["kitesurf", "wing"],
    conditions: { kitesurf: { windMinKn: 12, windMaxKn: 28 }, wing: { waveMaxM: 1.5 } },
  });

  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Kitesurfen" })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Wingfoilen" })).toBeChecked();
  await expect(page.getByRole("group", { name: "Wind · kn" }).getByLabel("Ab")).toHaveValue("12");
  if (process.env.CAPTURE_ACCOUNT_CONDITIONS) {
    await page.screenshot({ path: testInfo.outputPath("settings.png"), fullPage: true });
  }
  await page.getByRole("group", { name: "Wind · kn" }).getByLabel("Ab").fill("");
  await page.getByRole("button", { name: "Bedingungen speichern" }).click();
  expect(saved).toEqual({
    sports: ["kitesurf", "wing"],
    conditions: { kitesurf: { windMaxKn: 28 }, wing: { waveMaxM: 1.5 } },
  });
});
