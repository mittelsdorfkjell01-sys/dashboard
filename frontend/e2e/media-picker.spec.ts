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
    await page.route("**/admin/media/adopt/stream", (route) => {
      adoptRequest = route.request().postDataJSON();
      spotState = SPOT_WITH_HERO;
      return new Promise((resolve) => setTimeout(resolve, adoptDelayMs)).then(() =>
        route.fulfill({
          contentType: "application/x-ndjson",
          body: [
            { type: "progress", percent: 0, message: "Bild wird vorbereitet…" },
            { type: "progress", percent: 75, message: "Bild wird gespeichert…" },
            { type: "progress", percent: 100, message: "Hero-Bild übernommen." },
            { type: "result", result: {
              entity_type: "spot",
              entity_id: SPOT_ID,
              role: "hero",
              image: SPOT_WITH_HERO.image,
              gallery_image_id: null,
              demoted_hero: false,
              warnings: ["Ortsbezug ungeprüft."],
            } },
          ].map((event) => JSON.stringify(event)).join("\n") + "\n",
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

  test("saving a legacy Sand value sends the canonical bottom type", async ({ page }) => {
    spotState = { ...SPOT_WITHOUT_HERO, bottom_type: ["Sand", "sand"] };
    let patchBody: Record<string, unknown> | null = null;
    await page.route(`**/admin/spots/${SPOT_ID}`, (route) => {
      patchBody = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({ json: { ...spotState, bottom_type: ["sand"] } });
    });

    await page.goto(`/admin/spot/${SPOT_ID}/edit`);
    await expect(page.locator("#f-bottom_type [role=checkbox]").first())
      .toHaveAttribute("aria-checked", "true");
    await page.getByRole("button", { name: "Änderungen speichern" }).click();

    await expect.poll(() => patchBody).toMatchObject({
      bottom_type: ["sand"],
      expected_values: { bottom_type: ["Sand", "sand"] },
    });
  });

  test("a selected computer upload replaces the old hero preview", async ({ page }) => {
    spotState = SPOT_WITH_HERO;
    let uploads = 0;
    let galleryItems = [{
      id: "33333333-3333-3333-3333-333333333333",
      url: SPOT_WITH_HERO.image.url,
      width: 1600,
      status: "published_hero",
      kind: "gallery",
    }];
    await page.route(`**/admin/media/gallery/spot/${SPOT_ID}`, (route) =>
      route.fulfill({ json: { items: galleryItems } })
    );
    await page.route(`**/admin/spots/${SPOT_ID}/image/upload`, (route) => {
      uploads += 1;
      galleryItems = [];
      const uploadedSpot = {
        ...SPOT_WITH_HERO,
        image: { ...SPOT_WITH_HERO.image, url: "/media/new-hero.avif", provider: "upload" },
      };
      // The next record GET may still return the old image. The editor must
      // use the successful upload response for its immediate state.
      return route.fulfill({ json: uploadedSpot });
    });

    await page.goto(`/admin/spot/${SPOT_ID}/edit`);
    const heroSection = page.locator("#f-hero");
    const heroToggle = heroSection.getByRole("button", { name: "Headerbild ausrichten" });
    if ((await heroToggle.getAttribute("aria-expanded")) !== "true") await heroToggle.click();
    const gallerySection = page.locator("#f-galerie");
    const galleryToggle = gallerySection.getByRole("button", { name: "Galerie" });
    if ((await galleryToggle.getAttribute("aria-expanded")) !== "true") await galleryToggle.click();
    await expect(heroSection.getByText("Bildposition und Drehung"))
      .toBeVisible();
    await expect(gallerySection.getByRole("button", { name: "Entfernen" }))
      .toHaveCount(1);
    await heroSection.locator("input[type=file]").setInputFiles({
      name: "new-hero.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAD0lEQVR4nGPkqrjEwMAAAAXqAVYVfiwaAAAAAElFTkSuQmCC",
        "base64",
      ),
    });

    await expect(page.getByAltText("Vorschau des neuen Hero-Bildes")).toBeVisible();
    await expect(heroSection.getByText("Bildposition und Drehung"))
      .toHaveCount(0);
    await page.getByPlaceholder("Fotograf:in / Quelle").fill("Fotografin");
    await page.getByRole("button", { name: "Änderungen speichern" }).click();
    await expect.poll(() => uploads).toBe(1);
    await expect(page.getByAltText("Vorschau des neuen Hero-Bildes")).toHaveCount(0);
    await expect(heroSection.locator("img").first()).toHaveAttribute("src", /new-hero\.avif$/);
    await expect(heroSection.getByRole("button", { name: "Ortsbezug prüfen" }))
      .toBeVisible();
    await expect(gallerySection.getByText("Noch keine Galeriebilder."))
      .toBeVisible();
  });

  test("geo verification stays visible and can be reversed", async ({ page }) => {
    spotState = SPOT_WITH_HERO; // older image without a geo_verified field
    await page.route(`**/admin/spots/${SPOT_ID}/image/geo-verified`, (route) => {
      const { value } = route.request().postDataJSON() as { value: boolean };
      spotState = {
        ...spotState,
        image: { ...SPOT_WITH_HERO.image, geo_verified: value },
      };
      return route.fulfill({ json: spotState });
    });

    await page.goto(`/admin/spot/${SPOT_ID}/edit`);
    const heroSection = page.locator("#f-hero");
    const heroToggle = heroSection.getByRole("button", { name: "Headerbild ausrichten" });
    if ((await heroToggle.getAttribute("aria-expanded")) !== "true") await heroToggle.click();
    await expect(heroSection.getByRole("button", { name: "Ortsbezug prüfen" })).toBeVisible();
    await heroSection.getByRole("button", { name: "Ortsbezug prüfen" }).click();
    await expect(heroSection.getByText("Ortsbezug geprüft", { exact: true })).toBeVisible();
    await heroSection.getByRole("button", { name: "Prüfung zurücknehmen" }).click();
    await expect(heroSection.getByRole("button", { name: "Ortsbezug prüfen" })).toBeVisible();
  });

  test("removing the current gallery hero clears its preview", async ({ page }) => {
    spotState = SPOT_WITH_HERO;
    const imageId = "33333333-3333-3333-3333-333333333333";
    let galleryItems = [{
      id: imageId,
      url: SPOT_WITH_HERO.image.url,
      width: 1600,
      status: "published_hero",
      provider: "unsplash",
      kind: "gallery",
    }];
    await page.route(`**/admin/media/gallery/spot/${SPOT_ID}`, (route) =>
      route.fulfill({ json: { items: galleryItems } })
    );
    await page.route(`**/admin/media/gallery/${imageId}`, (route) => {
      galleryItems = [];
      spotState = SPOT_WITHOUT_HERO;
      return route.fulfill({ status: 204 });
    });

    await page.goto(`/admin/spot/${SPOT_ID}/edit`);
    const heroSection = page.locator("#f-hero");
    const heroToggle = heroSection.getByRole("button", { name: "Headerbild ausrichten" });
    if ((await heroToggle.getAttribute("aria-expanded")) !== "true") await heroToggle.click();
    const gallerySection = page.locator("#f-galerie");
    const galleryToggle = gallerySection.getByRole("button", { name: "Galerie" });
    if ((await galleryToggle.getAttribute("aria-expanded")) !== "true") await galleryToggle.click();
    await expect(heroSection.getByText("Bildposition und Drehung"))
      .toBeVisible();
    await gallerySection.locator("li").hover();
    await gallerySection.getByRole("button", { name: "Entfernen" }).click();

    await expect(gallerySection.getByText("Noch keine Galeriebilder."))
      .toBeVisible();
    await expect(heroSection.getByText("Bildposition und Drehung"))
      .toHaveCount(0);
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

  test("Wikimedia photos remain visible when direct image requests are blocked", async ({ page }) => {
    const thumbnail = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/photo.jpg/500px-photo.jpg";
    const original = "https://upload.wikimedia.org/wikipedia/commons/a/a1/photo.jpg";
    const image = {
      ...UNSPLASH_ITEM,
      provider: "wikimedia",
      external_id: "45219876",
      thumb_url: thumbnail,
      preview_url: original,
      full_url: original,
      delivery: "hosted",
    };
    let proxied = 0;
    await page.route("**/admin/media/search**", (route) => {
      if (new URL(route.request().url()).searchParams.get("provider") !== "wikimedia") {
        return route.fallback();
      }
      return route.fulfill({
        json: {
          provider: "wikimedia", status: "ok", items: [image], total: 1, page: 1,
          meta: { cached: false, budget: null, message: null },
        },
      });
    });
    await page.route("https://upload.wikimedia.org/**", (route) =>
      route.fulfill({ status: 403, contentType: "text/plain", body: "blocked" })
    );
    await page.route("**/admin/media/thumbnail**", (route) => {
      proxied += 1;
      return route.fulfill({
        contentType: "image/png",
        body: Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAD0lEQVR4nGPkqrjEwMAAAAXqAVYVfiwaAAAAAElFTkSuQmCC",
          "base64",
        ),
      });
    });

    await page.goto(`/admin/spot/${SPOT_ID}/edit`);
    await page.getByRole("button", { name: "Bild suchen" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: /Wikimedia \(1\)/ }).click();
    const tile = dialog.getByRole("listbox", { name: "Suchergebnisse" }).getByRole("button").first();
    await expect(tile.locator("img")).toHaveAttribute("src", /\/admin\/media\/thumbnail\?/);
    await expect.poll(() => tile.locator("img").evaluate((img: HTMLImageElement) => img.naturalWidth))
      .toBeGreaterThan(0);

    await tile.click();
    const preview = dialog.locator("aside img").first();
    await expect(preview).toHaveAttribute("src", /\/admin\/media\/thumbnail\?/);
    await expect.poll(() => preview.evaluate((img: HTMLImageElement) => img.naturalWidth))
      .toBeGreaterThan(0);
    expect(proxied).toBeGreaterThan(0);
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
    await expect(dialog.getByText("Hero-Bild wird vorbereitet…")).toBeVisible();
    await expect(dialog.getByRole("progressbar", { name: "Fortschritt der Bildübernahme" })).toHaveAttribute("aria-valuenow", "0");

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

  test("a 409 duplicate hero event surfaces to the operator", async ({ page }) => {
    await page.unroute("**/admin/media/adopt/stream");
    await page.route("**/admin/media/adopt/stream", (route) =>
      route.fulfill({
        contentType: "application/x-ndjson",
        body: JSON.stringify({
          type: "error",
          status: 409,
          message: "Dieses Foto ist bereits Hero bei „Valdevaqueros“.",
          detail: {
            code: "duplicate_hero",
            message: "Dieses Foto ist bereits Hero bei „Valdevaqueros“.",
            usages: [],
          },
        }) + "\n",
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
