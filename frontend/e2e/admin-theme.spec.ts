// The admin back office ships two themes (light by default, dark on the top-bar
// toggle). admin-workflow.spec.ts only ever exercises the default one, so a
// token that is legible on white but not on the dark canvas — or the other way
// round — would ship unnoticed. This spec pins both.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const THEME_KEY = "swd:admin-theme";

const overview = {
  spots: { draft: 7, published: 42, archived: 3, total: 52 },
  regions: 9,
  readiness_open: 0,
  not_live: [],
  finish: [
    { id: "s1", name: "Laboe", rank: "red", gaps: ["image"] },
    { id: "s2", name: "Heidkate", rank: "yellow", gaps: ["climatology"] },
  ],
  finish_open: 2,
  no_region: [{ id: "s9", name: "Hvide Sande" }],
  drafts: [{ id: "s1", name: "Laboe", ready: true }],
  recent: [],
  review: { reported_images: 2, submissions_pending: 5, flagged_tips: 1 },
  team_notes: [],
  era5_queued: 0,
  climatology_missing: 3,
  climatology_stale: 1,
  climatology_current: 40,
  climatology_failed: 0,
};

async function mockAdmin(page: import("@playwright/test").Page) {
  // Scoped to the API origin: a bare "**/admin/**" also swallows the SPA
  // document request and leaves a blank page.
  await page.route("**127.0.0.1:8000/**", (route) =>
    route.fulfill({ json: { items: [], total: 0 } })
  );
  await page.route("**127.0.0.1:8000/admin/notifications/unread-count", (route) =>
    route.fulfill({ json: { count: 3 } })
  );
  await page.route("**127.0.0.1:8000/admin/board/tasks", (route) => route.fulfill({ json: [] }));
  await page.route("**127.0.0.1:8000/admin/overview", (route) => route.fulfill({ json: overview }));
  await page.route("**127.0.0.1:8000/auth/me", (route) =>
    route.fulfill({
      json: { id: "admin-1", email: "admin@example.com", display_name: "Admin", role: "admin" },
    })
  );
}

for (const theme of ["light", "dark"] as const) {
  test(`admin overview meets AA contrast in the ${theme} theme`, async ({ page }) => {
    await page.addInitScript(
      ([key, value]) => {
        try {
          window.localStorage.setItem(key, value);
        } catch {
          // Blocked site data only costs the preset; the default (light) stands.
        }
      },
      [THEME_KEY, theme] as const
    );
    await mockAdmin(page);
    await page.goto("/admin");

    await expect(page.getByRole("heading", { name: "Übersicht", level: 1 })).toBeVisible();
    await expect(page.locator("body")).toHaveAttribute("data-admin-theme", theme);

    const axe = await new AxeBuilder({ page }).analyze();
    const serious = axe.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? "")
    );
    expect(
      serious.map((item) => ({
        id: item.id,
        nodes: item.nodes.map((node) => node.failureSummary),
      }))
    ).toEqual([]);
  });
}

test("the top-bar toggle switches the theme and remembers it", async ({ page }) => {
  await mockAdmin(page);
  await page.goto("/admin");

  // Light is the default for a browser that has never touched the toggle.
  await expect(page.locator("body")).toHaveAttribute("data-admin-theme", "light");

  await page.getByRole("button", { name: "Zu dunklem Design wechseln" }).click();
  await expect(page.locator("body")).toHaveAttribute("data-admin-theme", "dark");

  // The choice survives a reload.
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-admin-theme", "dark");

  await page.getByRole("button", { name: "Zu hellem Design wechseln" }).click();
  await expect(page.locator("body")).toHaveAttribute("data-admin-theme", "light");
});

// A focused text control in the back office shows ONE stroke: the border it
// already has, turned to the primary colour, plus the caret. index.css forces a
// 2px outline on every field for keyboard focus, which inside the admin scope
// rendered as a thick near-white frame OUTSIDE the field's own border. The rule
// lives in admin-theme.css; this pins it in both themes.
for (const theme of ["light", "dark"] as const) {
  test(`a focused admin field draws no second ring in the ${theme} theme`, async ({ page }) => {
    await page.addInitScript(
      ([key, value]) => {
        try {
          window.localStorage.setItem(key, value);
        } catch {
          // Blocked site data only costs the preset.
        }
      },
      [THEME_KEY, theme] as const
    );
    await mockAdmin(page);
    await page.route("**127.0.0.1:8000/admin/spots**", (route) =>
      route.fulfill({ json: { items: [], total: 0, limit: 25, offset: 0 } })
    );
    await page.goto("/admin/spots");

    const search = page.getByPlaceholder(/suchen/i).first();
    await expect(search).toBeVisible();

    const before = await search.evaluate((el) => getComputedStyle(el).borderColor);
    await search.click();
    await expect(search).toBeFocused();
    // The field token animates its border (transition-colors, 150ms). Reading
    // straight after the click returns the pre-focus value mid-transition, so
    // wait for the settled colour before asserting on it.
    await expect
      .poll(() => search.evaluate((el) => getComputedStyle(el).borderColor))
      .not.toBe(before);

    const focused = await search.evaluate((el) => {
      const cs = getComputedStyle(el);
      return {
        outlineStyle: cs.outlineStyle,
        outlineWidth: cs.outlineWidth,
        boxShadow: cs.boxShadow,
        borderColor: cs.borderColor,
      };
    });

    // No second shape around the field…
    expect(focused.outlineStyle === "none" || focused.outlineWidth === "0px").toBe(true);
    expect(focused.boxShadow === "none" || focused.boxShadow === "").toBe(true);
    // …and the existing stroke is what changed.
    expect(focused.borderColor).not.toBe(before);
  });
}
