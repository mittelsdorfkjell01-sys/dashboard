import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const API = /^http:\/\/(?:localhost|127\.0\.0\.1):8000\//;

async function failPublicData(page: Page) {
  await page.route(API, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/account/me") {
      await route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
      return;
    }
    await route.fulfill({
      status: 503,
      headers: { "Retry-After": "30" },
      json: { detail: "Datendienst vorübergehend nicht verfügbar.", retryable: true },
    });
  });
}

test.beforeEach(async ({ page }) => {
  await failPublicData(page);
});

test("landing, discovery and map expose recoverable data outages", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Die Spots sind gerade nicht erreichbar.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Erneut versuchen" }).first()).toBeVisible();

  await page.goto("/search");
  await expect(page.getByRole("heading", { name: "Entdecken" })).toBeVisible();
  await expect(page.getByText(/Aktive Suche: überall · alle Sportarten · jederzeit/)).toBeVisible();
  await expect(page.getByText("Die Suche ist gerade nicht verfügbar.")).toBeVisible();

  await page.goto("/map");
  await expect(page.getByText("Spots konnten nicht geladen werden.")).toBeVisible();
  await expect(page.locator('[aria-label="Surfspot-Karte"]')).toHaveAttribute("aria-describedby", "public-map-help");
});

test("mobile search keeps choices manageable and touch targets usable", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes("mobile"), "Mobile interaction check");
  await page.goto("/");
  await page.getByRole("button", { name: "Jetzt suchen" }).click();
  const dialog = page.getByRole("dialog", { name: "Suche" });
  await dialog.getByRole("button", { name: /Wann/ }).click();

  const dayButtons = dialog.getByRole("button", { name: /^\d+\. / });
  await expect(dayButtons.first()).toBeVisible();
  expect(await dayButtons.count()).toBeLessThanOrEqual(31);

  const smallTargets = await dialog.locator("button:visible").evaluateAll((buttons) =>
    buttons
      .map((button) => ({ label: button.getAttribute("aria-label") || button.textContent?.trim(), rect: button.getBoundingClientRect() }))
      .filter(({ rect }) => rect.width < 44 || rect.height < 44)
      .map(({ label, rect }) => ({ label, width: rect.width, height: rect.height })),
  );
  expect(smallTargets).toEqual([]);

  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});
