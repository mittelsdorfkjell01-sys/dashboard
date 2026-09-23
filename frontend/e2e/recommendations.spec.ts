import { expect, test, type Page, type Route } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

const REGION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const spots = [
  ["11111111-1111-4111-8111-111111111111", "porto-pollo", "Porto Pollo", "freeride"],
  ["22222222-2222-4222-8222-222222222222", "chop-city", "Chop City", "big_air"],
  ["33333333-3333-4333-8333-333333333333", "laguna", "Laguna", "freestyle"],
].map(([id, slug, name, style], index) => ({
  id, slug, name,
  region_id: REGION_ID,
  region_name: "Sardinien",
  region_country: "IT",
  location: { lat: 41.1 + index / 10, lon: 9.2 + index / 10 },
  sports: ["kitesurf"],
  image: null,
  facing: 180,
  water_type: ["sea"],
  bottom_type: ["sand"],
  level: ["advanced"],
  water_character: ["chop"],
  style: [style],
  facilities: null,
  typical_wind_kt: 21,
  typical_wave_height_m: 0.7,
  wind_availability: null,
}));

const orders: Record<string, typeof spots> = {
  anonymous: spots,
  freeride: [spots[0], spots[2], spots[1]],
  bigair: [spots[1], spots[2], spots[0]],
};

function profileFrom(route: Route): keyof typeof orders {
  const cookie = route.request().headers()["cookie"] ?? "";
  if (cookie.includes("e2e-profile=freeride")) return "freeride";
  if (cookie.includes("e2e-profile=bigair")) return "bigair";
  return "anonymous";
}

async function mockPublicApi(page: Page) {
  await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, async (route) => {
    const url = new URL(route.request().url());
    const profile = profileFrom(route);
    if (url.pathname === "/recommendations") {
      const surface = url.searchParams.get("surface");
      const data = surface === "season" ? orders[profile].slice(1) : orders[profile];
      return route.fulfill({ json: data });
    }
    if (url.pathname === "/spots") return route.fulfill({ json: orders[profile] });
    if (url.pathname === "/spots/version") return route.fulfill({ json: { version: "e2e" } });
    if (url.pathname === "/spots/top" || url.pathname === "/spots/live") return route.fulfill({ json: [] });
    if (url.pathname === "/regions/by-slug/sardinien") {
      return route.fulfill({ json: {
        id: REGION_ID, slug: "sardinien", name: "Sardinien", country: "IT",
        description: "Windspots an der Küste.", center: { lat: 41.2, lon: 9.3 },
        image: null, spot_count: 3, sports: ["kitesurf"],
      } });
    }
    if (url.pathname === "/regions") return route.fulfill({ json: [] });
    if (url.pathname === "/search") {
      return route.fulfill({ json: {
        resolved: "entities", treffer: 3, regionen: [],
        spots: orders[profile].map(({ id, slug, name, location, sports }) => ({
          id, slug, name, location, sports, distance_m: 1000,
        })),
      } });
    }
    if (url.pathname === "/account/me") {
      return profile === "anonymous"
        ? route.fulfill({ status: 401, json: { detail: "not authenticated" } })
        : route.fulfill({ json: { id: profile, email: `${profile}@example.com`, displayName: profile, preferences: {} } });
    }
    if (url.pathname === "/account/rider-profile/kitesurf") {
      return route.fulfill({ json: { sport: "kitesurf", level: "advanced", styleWeights: {}, preferredWaterCharacter: [], profileVersion: 1 } });
    }
    if (url.pathname === "/account/rider-profile") {
      return route.fulfill({ json: { weightKg: 78, homeLocation: null, maxTravelKm: null, travelMode: "trip", availability: [], minWaterTempC: null, excludedBottoms: [], profileVersion: 1 } });
    }
    if (url.pathname === "/account/gear") {
      return route.fulfill({ json: { items: [{ id: "kite", sport: "kitesurf", kind: "kite", size: 9, boardType: null, active: true, sortOrder: 0, profileVersion: 1 }] } });
    }
    if (url.pathname === "/events") return route.fulfill({ status: 202, json: { accepted: 1 } });
    return route.fulfill({ json: [] });
  });
}

test("landing renders all non-empty recommendation surfaces without scoring copy", async ({ page }) => {
  await page.addInitScript(() => {
    (window as Window & { __recommendationCls?: number }).__recommendationCls = 0;
    new PerformanceObserver((entries) => {
      for (const entry of entries.getEntries()) {
        const shift = entry as PerformanceEntry & { value: number; hadRecentInput: boolean };
        if (!shift.hadRecentInput) {
          const target = window as Window & { __recommendationCls?: number };
          target.__recommendationCls = (target.__recommendationCls ?? 0) + shift.value;
        }
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
  await mockPublicApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Aktuelle Top-Spots" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Interessant nächste Woche" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Saison" })).toBeVisible();
  const markup = await page.locator("body").evaluate((node) => node.outerHTML.toLowerCase());
  for (const forbidden of ["top-match", "match-prozent", "rank_score", "gut_anteil", "weil du", "passt zu"]) {
    expect(markup).not.toContain(forbidden);
  }
  const cls = await page.evaluate(() => (
    window as Window & { __recommendationCls?: number }
  ).__recommendationCls ?? 0);
  expect(cls).toBeLessThan(0.1);
});

test("a rider profile switch changes the server search order", async ({ page }) => {
  await mockPublicApi(page);
  await page.context().addCookies([{ name: "e2e-profile", value: "freeride", domain: "127.0.0.1", path: "/" }]);
  await page.goto("/search?q=Sardinien&sport=kitesurf");
  await expect(page.locator("main p.font-semibold").first()).toHaveText("Porto Pollo");

  await page.context().addCookies([{ name: "e2e-profile", value: "bigair", domain: "127.0.0.1", path: "/" }]);
  await page.reload();
  await expect(page.locator("main p.font-semibold").first()).toHaveText("Chop City");
});

test("captures anonymous and two rider orders for the same region", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name.includes("mobile"), "One desktop evidence set is sufficient");
  await mockPublicApi(page);
  const output = path.resolve(process.cwd(), "../.impeccable/review");
  mkdirSync(output, { recursive: true });
  for (const profile of ["anonymous", "freeride", "bigair"] as const) {
    if (profile === "anonymous") await page.context().clearCookies();
    else await page.context().addCookies([{ name: "e2e-profile", value: profile, domain: "127.0.0.1", path: "/" }]);
    await page.goto("/region/sardinien");
    const heading = page.getByRole("heading", { name: "Top in Sardinien" });
    await expect(heading).toBeVisible();
    const surface = page.locator('[data-recommendation-surface="region"]');
    await surface.scrollIntoViewIfNeeded();
    await page.waitForTimeout(450);
    await surface.screenshot({ path: path.join(output, `phase-d-region-${profile}.png`) });
  }
});
