import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const spotId = "11111111-1111-4111-8111-111111111111";

test.beforeEach(async ({ page }) => {
  await page.route("**/auth/me", (route) => route.fulfill({ json: {
    id: "admin-1", email: "admin@example.com", display_name: "Admin", role: "admin",
  } }));
  await page.route("**/admin/notifications/unread-count", (route) => route.fulfill({ json: { count: 0 } }));
  await page.route("**/admin/board/tasks", (route) => route.fulfill({ json: [] }));
  await page.route("**/admin/spots/tide/queue", (route) => route.fulfill({ json: {
    total: 1,
    summary: { anchor_review: 1 },
    items: [{
      spot_id: spotId,
      spot_name: "Baleal Norte",
      region_name: "Peniche",
      country: "PT",
      status: "anchor_review",
      enabled: true,
      public_enabled: false,
      anchor_status: "auto_selected",
      anchor_distance_m: 820,
      anchor_warnings: ["Modellpunkt liegt im extrapolierten Küstenraster."],
      calculation_status: "ready",
      calculation_error: null,
      last_calculated_at: "2026-11-11T10:00:00Z",
      latest_run_status: "succeeded",
    }],
  } }));
  await page.route(`**/admin/spots/${spotId}/tide`, (route) => route.fulfill({ json: {
    id: "profile-1",
    spot_id: spotId,
    enabled: true,
    public_enabled: false,
    timezone: "Europe/Lisbon",
    model_name: "FES2022b",
    model_version: "2022b",
    automatic_anchor: { lat: 39.37, lon: -9.35 },
    manual_anchor: null,
    effective_anchor: { lat: 39.37, lon: -9.35 },
    anchor_distance_m: 820,
    anchor_kind: "extrapolated",
    anchor_status: "auto_selected",
    anchor_warnings: ["Modellpunkt liegt im extrapolierten Küstenraster."],
    global_offset_minutes: 0,
    high_offset_minutes: 0,
    low_offset_minutes: 0,
    manual_uncertainty_minutes: null,
    estimated_uncertainty_minutes: null,
    uncertainty_source: null,
    quality_status: "model_only",
    note: null,
    correction_reason: null,
    correction_source: null,
    version: 1,
    last_calculated_at: "2026-11-11T10:00:00Z",
    calculation_status: "ready",
    calculation_error: null,
    updated_at: "2026-11-11T10:00:00Z",
    events: [],
    overrides: [],
    latest_run: { status: "succeeded" },
    limits: { soft_offset_minutes: 90, hard_offset_minutes: 360, reason_required_minutes: 30 },
  } }));
});

test("FES-Review-Queue erklärt den privaten Anker-Schritt", async ({ page }) => {
  await page.goto("/admin/tides");
  await expect(page.getByRole("heading", { level: 1, name: "FES-Tide Europa" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Zu prüfen · 1" })).toBeVisible();
  await page.getByRole("button", { name: /Baleal Norte/ }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Automatisch gewählt · Prüfung nötig")).toBeVisible();
  await expect(dialog.getByText("820 m")).toBeVisible();
  await expect(dialog.getByText("Modellpunkt liegt im extrapolierten Küstenraster.")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Modellanker bestätigen" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Astronomische Tide veröffentlichen" })).toHaveCount(0);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});
