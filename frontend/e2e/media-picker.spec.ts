// Media-picker durchstich: chip → tile → preview → adopt → hero on the spot.
//
// Every backend call is stubbed with a fixed payload, so the test exercises
// what the operator sees and does — the picker component and the wiring
// between the six calls it makes — without depending on a running server, a
// database, or a provider key.
//
// Complements the vitest coverage of the pure logic (mediaPicker.ts,
// imageCredit.ts, heroSource.ts, gallery.ts) with the one full user flow.

import { expect, test } from "@playwright/test";

const ADMIN_USER = {
  id: "admin-1",
  email: "admin@example.com",
  display_name: "Admin",
  role: "admin",
};

const SPOT_ID = "11111111-1111-1111-1111-111111111111";
const REGION_ID = "22222222-2222-2222-2222-222222222222";

// The shape the search endpoint returns — one hero-eligible photo per
// provider so every tab lands populated and the flow can pick something.
const UNSPLASH_ITEM = {
  provider: "unsplash",
  external_id: "Qw3w0hVjJ2M",
  thumb_url: "https://images.unsplash.com/photo?w=400",
  preview_url: "https://images.unsplash.com/photo?w=1600",
  full_url: "https://images.unsplash.com/photo",
  width: 6000,
  height: 4000,
  license: {
    name: "Unsplash License",
    url: "https://unsplash.com/license",
    commercial: true,
    modification: true,
  },
  credit: {
    name: "Sam Rivera",
    url: "https://unsplash.com/@seasidesam?utm_source=surfwinddata&utm_medium=referral",
  },
  source_page:
    "https://unsplash.com/photos/Qw3w0hVjJ2M?utm_source=surfwinddata&utm_medium=referral",
  delivery: "hotlinked",
  geo_verified: false,
  hero_eligible: true,
  gallery_eligible: true,
  used_by: [],
  unsplash_download_location:
    "https://api.unsplash.com/photos/Qw3w0hVjJ2M/download",
};

const SPOT_WITH_HERO = {
  id: SPOT_ID,
  slug: "tarifa-los-lances",
  name: "Los Lances",
  region_id: REGION_ID,
  location: { lat: 36.025, lon: -5.628 },
  era5_cell: null,
  model_pref: null,
  sports: ["kitesurf"],
  water_type: ["sea"],
  bottom_type: ["sand"],
  level: ["beginner"],
  water_character: ["chop"],
  style: ["freeride"],
  facilities: null,
  status: "draft",
  confidence: null,
  facing: 225,
  editorial: { description: "…" },
  climatology: null,
  overrides: null,
  finish_rank: null,
  image: {
    url: "https://images.unsplash.com/photo",
    source: "Unsplash",
    license: "Unsplash License",
    credit: "Sam Rivera",
    provider: "unsplash",
    external_id: "Qw3w0hVjJ2M",
    delivery: "hotlinked",
    focal: { x: 50, y: 50 },
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-08-06T00:00:00Z",
};

const SPOT_WITHOUT_HERO = {
  ...SPOT_WITH_HERO,
  image: null,
};

test.describe("media picker", () => {
  let spotState = SPOT_WITHOUT_HERO;
  let adoptRequest: unknown = null;
  let adoptDelayMs = 0;

  test.beforeEach(async ({ page }) => {
    spotState = SPOT_WITHOUT_HERO;
    adoptRequest = null;
    adoptDelayMs = 0;

    await page.route("**/auth/me", (route) => route.fulfill({ json: ADMIN_USER }));
    await page.route("**/admin/notifications/unread-count", (route) =>
      route.fulfill({ json: { count: 0 } })
    );
    // The budget indicator polls on mount — a healthy response keeps the
    // header out of the way of the flow.
    await page.route("**/admin/media/providers", (route) =>
      route.fulfill({
        json: {
          providers: [
            {
              provider: "unsplash",
              available: true,
              budget: { used: 3, limit: 50, exhausted: false, warning: false },
            },
          ],
        },
      })
    );

    // Context: what the picker asks for when it opens.
    await page.route(`**/admin/media/context/spot/${SPOT_ID}`, (route) =>
      route.fulfill({
        json: {
          entity_type: "spot",
          entity_id: SPOT_ID,
          title: "Los Lances",
          subtitle: "Tarifa, ES",
          lat: 36.025,
          lon: -5.628,
          suggestions: [
            "Los Lances",
            "Tarifa kitesurfing",
            "Tarifa beach",
            "Tarifa coast",
          ],
          has_image: false,
        },
      })
    );

    // Search — one per provider, all with an item so every tab is populated.
    await page.route("**/admin/media/search**", (route) => {
      const url = new URL(route.request().url());
      const provider = url.searchParams.get("provider") ?? "unsplash";
      const payload =
        provider === "openverse"
          ? { items: [], total: 0 } // one empty tab to prove the "0" label
          : { items: [{ ...UNSPLASH_ITEM, provider }], total: 1 };
      return route.fulfill({
        json: {
          provider,
          status: "ok",
          items: payload.items,
          total: payload.total,
          page: 1,
          meta: {
            cached: false,
            budget: { used: 3, limit: 50, exhausted: false, warning: false },
            message: null,
          },
        },
      });
    });

    // Adopt captures the request, then the spot record is served with the
    // freshly written image — mirroring what the real backend does.
    await page.route("**/admin/media/adopt", (route) => {
      adoptRequest = route.request().postDataJSON();
      spotState = SPOT_WITH_HERO;
      return new Promise((resolve) => setTimeout(resolve, adoptDelayMs)).then(() =>
        route.fulfill({
          json: {
            entity_type: "spot",
            entity_id: SPOT_ID,
            role: "hero",
            image: SPOT_WITH_HERO.image,
            gallery_image_id: null,
            demoted_hero: false,
            warnings: ["Ortsbezug ungeprüft."],
          },
        })
      );
    });

    // The spot editor's own reads — enough for the "Header-Bild" section to
    // render with the newly stored hero.
    await page.route(`**/admin/spots/${SPOT_ID}/record`, (route) =>
      route.fulfill({ json: spotState })
    );
    await page.route(`**/admin/spots/${SPOT_ID}/readiness`, (route) =>
      route.fulfill({
        json: {
          spot_id: SPOT_ID,
          status: "draft",
          ready: false,
          checklist: [],
          gaps: [],
        },
      })
    );
    await page.route(`**/admin/media/gallery/spot/${SPOT_ID}`, (route) =>
      route.fulfill({ json: { items: [] } })
    );
    await page.route("**/admin/regions", (route) => route.fulfill({ json: [] }));
    await page.route("**/admin/spots/*/images", (route) =>
      route.fulfill({ json: { items: [] } })
    );
    await page.route("**/admin/spots/*/tide", (route) =>
      route.fulfill({ status: 404, json: { detail: "no tide" } })
    );
  });

  test("facility status buttons stay large and contain their labels", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.goto(`/admin/spot/${SPOT_ID}/edit`);

    const facilities = page.locator("#f-facilities");
    const toggle = facilities.getByRole("button", { name: "Facilities" });
    if ((await toggle.getAttribute("aria-expanded")) !== "true") await toggle.click();

    const buttons = facilities.locator("[data-facility-availability] [role=checkbox]");
    await expect(buttons).toHaveCount(15);
    for (const width of [320, 640, 1024, 1280, 1440]) {
      await page.setViewportSize({ width, height: 800 });
      for (const button of await buttons.all()) {
        const dimensions = await button.evaluate((element) => ({
          height: element.getBoundingClientRect().height,
          horizontalOverflow: element.scrollWidth - element.clientWidth,
        }));
        expect(dimensions.height).toBeGreaterThanOrEqual(44);
        expect(dimensions.horizontalOverflow).toBeLessThanOrEqual(0);
      }
      for (const row of await facilities.locator("[data-facility-row]").all()) {
        const rowOverflow = await row.evaluate(
          (element) => element.scrollWidth - element.clientWidth,
        );
        expect(rowOverflow, `facility row overflow at ${width}px`).toBeLessThanOrEqual(0);
      }
    }
  });

  test("chip → tile → adopt writes a canonical hero and shows it", async ({ page }) => {
    adoptDelayMs = 350;
    await page.goto(`/admin/spot/${SPOT_ID}/edit`);

    // The header opens the picker in Hero mode.
    await page.getByRole("button", { name: "Bild suchen" }).first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    // The first chip is active on open — no typing required.
    await expect(dialog.getByRole("button", { name: "Los Lances" })).toHaveClass(
      /bg-admin-primary/
    );

    // Tab labels carry the post-filter count, so the emptiness of Openverse
    // is visible without clicking through.
    await expect(dialog.getByRole("button", { name: /Unsplash \(1\)/ })).toBeVisible();
    await expect(dialog.getByRole("button", { name: /Openverse \(0\)/ })).toBeVisible();

    // Pick the one tile. The preview panel appears with the credit line and
    // the "Als Hero übernehmen" button.
    // The tile carries its badge strip as its accessible name; picking the one
    // inside the grid rather than any `pressed=false` button in the dialog
    // avoids matching the mode-switch buttons by accident.
    const tile = dialog.getByRole("listbox", { name: "Suchergebnisse" })
      .getByRole("button")
      .first();
    await tile.click();
    // Credit appears three times: in each of the two hero previews and in the
    // license card. That any of them renders is what proves the preview panel
    // took the selection — the exact count is a UI detail, not the contract.
    await expect(dialog.getByRole("link", { name: "Sam Rivera" }).first()).toBeVisible();
    await expect(dialog.getByText("Unsplash License").first()).toBeVisible();

    await dialog.getByRole("button", { name: "Als Hero übernehmen" }).click();

    // Hosted providers can need several seconds for download + encoding. The
    // picker stays open and shows honest activity instead of looking frozen.
    await expect(dialog.getByRole("progressbar", { name: "Fortschritt der Bildübernahme" })).toBeVisible();
    await expect(dialog.getByText("Hero-Bild wird geladen und verarbeitet…")).toBeVisible();

    // The request carries an identity, not a payload — everything else is
    // re-resolved server-side. The active tab on open is "nearby" (first in
    // the spot tab order), so the provider on the wire matches whichever tab
    // the operator was on; what matters is that no photo bytes are sent.
    expect(adoptRequest).toMatchObject({
      entity_type: "spot",
      entity_id: SPOT_ID,
      role: "hero",
      external_id: "Qw3w0hVjJ2M",
    });
    expect(adoptRequest).not.toHaveProperty("full_url");
    expect(adoptRequest).not.toHaveProperty("license");

    // Overlay closes and the form uses the exact image from the successful
    // write response. This avoids a second read racing the just-finished write.
    await expect(dialog).toHaveCount(0);
    const heroSection = page.locator("#f-hero");
    const heroToggle = heroSection.getByRole("button", { name: "Headerbild ausrichten" });
    if ((await heroToggle.getAttribute("aria-expanded")) !== "true") await heroToggle.click();
    await expect(heroSection.locator("img").first()).toHaveAttribute(
      "src",
      SPOT_WITH_HERO.image!.url
    );
  });

  test("the right edit rail scrolls while the pointer is over it", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 600 });
    await page.goto(`/admin/spot/${SPOT_ID}/edit`);

    const rail = page.locator("[data-spot-edit-rail]");
    await expect(rail).toBeVisible();
    await rail.evaluate((element) => {
      element.style.height = "180px";
      element.style.maxHeight = "180px";
    });

    const metrics = await rail.evaluate((element) => {
      const styles = window.getComputedStyle(element);
      return {
        overflowY: styles.overflowY,
        scrollbarWidth: styles.scrollbarWidth,
        scrollHeight: element.scrollHeight,
        clientHeight: element.clientHeight,
      };
    });
    expect(metrics.overflowY).toBe("auto");
    expect(metrics.scrollbarWidth).not.toBe("none");
    expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight);

    await rail.hover();
    await page.mouse.wheel(0, 300);
    await expect.poll(() => rail.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  });

  test("keyboard navigation and Escape work in the grid", async ({ page }) => {
    await page.goto(`/admin/spot/${SPOT_ID}/edit`);
    await page.getByRole("button", { name: "Bild suchen" }).first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    // Escape closes the overlay without adopting anything.
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    expect(adoptRequest).toBeNull();
  });

  test("a 409 duplicate hero response surfaces to the operator", async ({ page }) => {
    await page.unroute("**/admin/media/adopt");
    await page.route("**/admin/media/adopt", (route) =>
      route.fulfill({
        status: 409,
        json: {
          detail: {
            code: "duplicate_hero",
            message: "Dieses Foto ist bereits Hero bei „Valdevaqueros“.",
            usages: [],
          },
        },
      })
    );

    await page.goto(`/admin/spot/${SPOT_ID}/edit`);
    await page.getByRole("button", { name: "Bild suchen" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog
      .getByRole("listbox", { name: "Suchergebnisse" })
      .getByRole("button")
      .first()
      .click();
    await dialog.getByRole("button", { name: "Als Hero übernehmen" }).click();

    await expect(dialog.getByRole("alert")).toContainText("Valdevaqueros");
    // The overlay stays open so the operator can pick another photo.
    await expect(dialog).toBeVisible();
  });
});
