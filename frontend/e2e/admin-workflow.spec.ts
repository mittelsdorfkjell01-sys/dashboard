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
        climatology_missing: 0,
        climatology_stale: 0,
        climatology_current: 0,
        climatology_failed: 0,
      },
    })
  );
});

test("admin login only asks for email and password", async ({ page }) => {
  let authRequestUrl = "";
  await page.unroute("**/auth/me");
  await page.route("**/auth/me", (route) => {
    authRequestUrl = route.request().url();
    return route.fulfill({ status: 401, json: { detail: "Nicht angemeldet." } });
  });

  await page.goto("/admin/login");

  await expect.poll(() => authRequestUrl).not.toBe("");
  expect(new URL(authRequestUrl).hostname).toBe("127.0.0.1");
  await expect(page.getByLabel("E-Mail")).toBeVisible();
  await expect(page.getByLabel("Passwort")).toBeVisible();
  await expect(page.getByText(/Zwei-Faktor|2FA/i)).toHaveCount(0);
});

test("admin overview is accessible and protects a dirty task dialog", async ({ page }) => {
  let failCreate = false;
  await page.unroute("**/admin/board/tasks");
  await page.route("**/admin/board/tasks", (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: [] });
    if (failCreate) return route.fulfill({ status: 500, json: { detail: "Fehler" } });
    return route.fulfill({ json: { id: "task-1", title: "Gespeichert", status: "open" } });
  });
  await page.route("**/admin/regions", (route) => route.fulfill({ json: [] }));
  await page.route("**/admin/spots?**", (route) =>
    route.fulfill({ json: { items: [], total: 0, limit: 25, offset: 0 } })
  );
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/admin/spots");
  // At this width the sidebar collapses behind the dashboard menu, so open it
  // before reaching for the "Übersicht" entry.
  await page.getByRole("button", { name: "Dashboard-Menü öffnen" }).click();
  await page
    .getByRole("navigation", { name: "Dashboard-Navigation" })
    .getByRole("link", { name: "Übersicht" })
    .click();
  await expect(page.getByRole("heading", { level: 1, name: "Übersicht" })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
  expect(overflow).toBeLessThanOrEqual(1);

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))
  ).toEqual([]);

  // Unchanged and reverted forms close without a second dialog.
  await page.getByRole("button", { name: "Neue Aufgabe" }).click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Neue Aufgabe" }).click();
  await page.getByLabel("Titel").fill("Kurz geändert");
  await page.getByLabel("Titel").fill("");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // A successful save closes cleanly.
  await page.getByRole("button", { name: "Neue Aufgabe" }).click();
  await page.getByLabel("Titel").fill("Gespeichert");
  await page.getByRole("button", { name: "Anlegen" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // A failed save keeps the changed state until it is explicitly discarded.
  failCreate = true;
  await page.getByRole("button", { name: "Neue Aufgabe" }).click();
  await page.getByLabel("Titel").fill("Forecast prüfen");
  await page.getByRole("button", { name: "Anlegen" }).click();
  await expect(page.getByRole("heading", { name: "Neue Aufgabe" })).toBeVisible();
  expect(await page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  })).toBe(true);
  await page.goBack();
  const unsavedDialog = page.getByRole("dialog", { name: "Ungespeicherte Änderungen" });
  await expect(unsavedDialog).toBeVisible();
  await unsavedDialog.getByRole("button", { name: "Abbrechen" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await page.keyboard.press("Escape");
  const discardDialog = page.getByRole("dialog", { name: "Aufgabe verwerfen?" });
  await expect(discardDialog).toBeVisible();
  await discardDialog.getByRole("button", { name: "Verwerfen" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("overview reports climatology maintenance without a manual batch button", async ({ page }) => {
  await page.unroute("**/admin/overview");
  await page.route("**/admin/overview", (route) =>
    route.fulfill({
      json: {
        spots: { draft: 0, published: 2, archived: 0, total: 2 },
        regions: 1,
        readiness_open: 0,
        not_live: [],
        finish: [],
        finish_open: 0,
        no_region: [],
        drafts: [],
        recent: [],
        review: {},
        team_notes: [],
        era5_queued: 2,
        climatology_missing: 2,
        climatology_stale: 1,
        climatology_current: 0,
        climatology_failed: 1,
      },
    })
  );

  await page.goto("/admin");
  await expect(
    page.getByText("Klimatologie: 2 fehlend, 1 veraltet, 1 fehlgeschlagen")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Jetzt berechnen" })).toHaveCount(0);
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
