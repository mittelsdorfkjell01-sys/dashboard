import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/auth/me", (route) =>
    route.fulfill({
      json: {
        id: "admin-1",
        email: "admin@example.com",
        display_name: "Admin",
        role: "admin",
        mfa_enabled: false,
      },
    })
  );
  await page.route("**/admin/notifications/unread-count", (route) =>
    route.fulfill({ json: { count: 0 } })
  );
  await page.route("**/admin/board/tasks", (route) => route.fulfill({ json: [] }));
  await page.route("**/admin/overview", (route) =>
    route.fulfill({
      json: {
        spots: { draft: 0, published: 0, archived: 0, total: 0 },
        regions: 0,
        readiness_open: 0,
        not_live: [],
        finish: [],
        finish_open: 0,
        no_region: [],
        drafts: [],
        recent: [],
        review: {},
        team_notes: [],
        era5_queued: 0,
      },
    })
  );
});

test("admin overview is accessible and protects a dirty task dialog", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 1, name: "Übersicht" })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
  expect(overflow).toBeLessThanOrEqual(1);

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))
  ).toEqual([]);

  await page.getByRole("button", { name: "Neue Aufgabe" }).click();
  await page.getByLabel("Titel").fill("Forecast prüfen");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Aufgabe verwerfen?" })).toBeVisible();
  await page.getByRole("button", { name: "Verwerfen" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("spot filters preserve recent edits and recent searches", async ({ page }) => {
  const requestedUrls: string[] = [];
  await page.route("**/admin/regions", (route) => route.fulfill({ json: [] }));
  await page.route("**/admin/spots?**", (route) => {
    requestedUrls.push(route.request().url());
    return route.fulfill({ json: { items: [], total: 0, limit: 25, offset: 0 } });
  });

  await page.goto("/admin/spots");
  await page.getByLabel("Sortierung").selectOption("-updated");
  await expect.poll(() => requestedUrls.some((url) => url.includes("sort=-updated"))).toBe(true);

  await page.getByLabel("Suche").fill("Laboe");
  await expect.poll(() => requestedUrls.some((url) => url.includes("q=Laboe"))).toBe(true);
  await expect(page.getByLabel("Zuletzt gesucht")).toBeEnabled();
  await expect(page.getByLabel("Zuletzt gesucht").locator('option[value="Laboe"]')).toHaveCount(1);
});
