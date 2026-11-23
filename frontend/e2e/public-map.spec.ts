import { expect, test, type Page } from "@playwright/test";
import { mockBackend } from "./fixtures/publicMapBackend";

/** The redesigned /map (public-map/): one MapLibre surface, mode switch on
 *  top, a slim spot bar and the scrollable forecast tile at the bottom. */

const SHOTS = process.env.PUBLIC_MAP_SHOTS;
// Field and forecast run from the current hour, so the clock has hours ahead.
const START = Math.floor(Date.now() / 3_600_000) * 3_600_000;
const HOURS = Array.from({ length: 30 }, (_, index) => new Date(START + index * 3_600_000).toISOString());

/** A spot forecast over the same hours, varying so bars and labels differ. */
function forecastFromNow() {
  const byDate = new Map<string, Array<Record<string, unknown>>>();
  HOURS.forEach((time, index) => {
    const date = time.slice(0, 10);
    if (!byDate.has(date)) byDate.set(date, []);
    byDate.get(date)!.push({
      time, wind: 8 + (index % 12), gust: 14 + (index % 12), dir: 250 + index * 3, air: 15,
      swell: 0.4 + (index % 5) / 10, period: 7, swell_dir: 280,
      waves: { total_wave: { significant_height_m: 0.4 + (index % 5) / 10 } }, precip: 0, sst: 14,
    });
  });
  return {
    spot_id: "00000000-0000-4000-8000-000000000001", model: "icon-eu", generated_at: HOURS[0], timezone: "UTC",
    days: [...byDate.entries()].map(([date, hours]) => ({
      date, local_date: date, confidence: "hoch", detail: "hourly",
      summary: { wind_avg: 12, wind_max: 19, gust_max: 25, air_min: 15, air_max: 15, swell_max: 0.8 }, hours,
    })),
  };
}

async function open(page: Page, query: string, withWaves = false) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await mockBackend(page, undefined, true, { withWaves, validTimes: HOURS });
  await page.route(/\/spots\/[^/]+\/forecast(\?.*)?$/, (route) => route.fulfill({ json: forecastFromNow() }));
  await page.goto(`/map?${query}`);
  await expect(page.getByRole("group", { name: "Kartenmodus" })).toBeVisible();
  // The field canvas exists once the map has loaded and listens for taps.
  await expect(page.locator(".swd-pm .swd-pm-field")).toHaveCount(1);
  return errors;
}

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` });
}

test("the wind opens as field and particles, a bare time slider and no legend", async ({ page }) => {
  const errors = await open(page, "mode=wind&lat=54&lon=10&z=9");
  await expect(page.getByRole("button", { name: "Wind", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".swd-pm-legend-float")).toHaveCount(0);
  await expect(page.locator(".swd-pm-particles")).toHaveCount(1);
  await expect(page.getByRole("region", { name: "Zeit" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Abspielen" })).toHaveCount(0);
  await expect(page.locator(".swd-pm-spot")).not.toContainText("kn");
  await page.waitForTimeout(800);
  await shot(page, "wind");
  expect(errors).toEqual([]);
});

test("Ebenen draws the wind as particles OR arrows, never both", async ({ page }) => {
  await open(page, "mode=wind&lat=54&lon=10&z=9");
  await page.getByRole("button", { name: "Ebenen" }).click();
  const particles = page.getByRole("radio", { name: "Partikel" });
  const arrows = page.getByRole("radio", { name: "Pfeile" });
  await expect(particles).toHaveAttribute("aria-checked", "true");
  await arrows.click();
  await expect(arrows).toHaveAttribute("aria-checked", "true");
  await expect(particles).toHaveAttribute("aria-checked", "false");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);
  await shot(page, "wind-arrows");
});

test("on the Spots map a spot shows only name, region and the way to the spot", async ({ page }) => {
  await open(page, "mode=spots&lat=54&lon=10&z=9");
  await expect(page.locator(".swd-pm-tile")).toHaveCount(0);
  await page.getByRole("button", { name: "Spot A" }).click();
  const bar = page.getByRole("region", { name: "Spot A" });
  await expect(bar).toContainText("Region A");
  await expect(bar).not.toContainText("kn");
  const link = bar.getByRole("link", { name: "Zum Spot" });
  await expect(link).toHaveAttribute("href", /\/spot\//);
  await expect(link).not.toHaveAttribute("href", /daten/);
  await page.getByRole("button", { name: "Spots im Ausschnitt" }).click();
  await expect(page.getByRole("region", { name: "Spots im Ausschnitt" })).toContainText("Spot A");
  await shot(page, "spots-bar");
});

test("on the wind map a spot puts \"Zum Spot\" (Daten) into the slider, and swiping moves the clock", async ({ page }) => {
  await open(page, "mode=wind&lat=54&lon=10&z=9");
  await page.getByRole("button", { name: "Spot A" }).click();
  await expect(page.locator(".swd-pm-bar")).toHaveCount(0);
  const tile = page.getByRole("region", { name: "Zeit" });
  await expect(tile.getByRole("link", { name: /Zum Spot/ })).toHaveAttribute("href", /daten/);
  const before = await tile.locator(".swd-pm-tile-head p").innerText();
  await tile.locator(".swd-pm-tile-strip").hover();
  await page.mouse.wheel(30 * 4, 0);
  await expect(tile.locator(".swd-pm-tile-head p")).not.toHaveText(before);
  await shot(page, "wind-spot");
});

test("waves are colour plus arrows in the direction of travel, without a legend", async ({ page }) => {
  await open(page, "mode=waves&lat=54&lon=5&z=8", true);
  await expect(page.locator(".swd-pm-arrows")).toHaveCount(1);
  // 2026-11-21: the wave legend is gone too.
  await expect(page.locator(".swd-pm-legend-float")).toHaveCount(0);
  await page.getByRole("button", { name: "Ebenen" }).click();
  await expect(page.getByRole("checkbox", { name: "Pfeile (Laufrichtung)" })).toBeChecked();
  await page.keyboard.press("Escape");
  await page.waitForTimeout(900);
  await shot(page, "waves");
});

test("follows the site's dark theme, ground and panels alike", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("sw-theme", "dark"));
  await open(page, "mode=wind&lat=54&lon=10&z=9");
  await expect(page.locator("main.swd-pm")).toHaveClass(/is-dark/);
  const tile = await page.locator(".swd-pm-tile").evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(tile).toBe("rgb(26, 31, 36)");
  await page.waitForTimeout(800);
  await shot(page, "dark-wind");
  await page.getByRole("button", { name: "Wellen", exact: true }).click();
  await page.waitForTimeout(900);
  await shot(page, "dark-waves");
});

test("the mode pill keeps one width and switching modes adds no history", async ({ page }) => {
  await open(page, "mode=spots&lat=54&lon=10&z=7", true);
  const pill = page.locator(".swd-pm-modeswitch");
  const widths: number[] = [];
  const length = await page.evaluate(() => history.length);
  for (const name of ["Wind", "Wellen", "Spots"]) {
    await page.getByRole("button", { name, exact: true }).click();
    widths.push(Math.round((await pill.boundingBox())!.width));
  }
  expect(new Set(widths).size).toBe(1);
  expect(await page.evaluate(() => history.length)).toBe(length);
});

test("a tap on the wind or wave map opens that point's forecast in the time strip", async ({ page }) => {
  await open(page, "mode=wind&lat=54&lon=5&z=8", true);
  // No hover pill any more (2026-11-21).
  await page.mouse.move(200, 300);
  await expect(page.locator(".swd-pm-tip")).toHaveCount(0);
  await page.mouse.click(200, 300);
  const tile = page.getByRole("region", { name: "Vorhersage und Zeit" });
  // Simplified 2026-11-21: the forecast sits in the strip's hour columns.
  await expect(tile.locator(".swd-pm-tile-bar").first()).toBeVisible();
  await expect(tile.locator(".swd-pm-tile-source")).toContainText("Wind");
  await expect(page.locator(".swd-pm-tapmark")).toHaveCount(1);
  await tile.getByRole("button", { name: "Vorhersage schließen" }).click();
  await expect(page.locator(".swd-pm-tile.has-forecast")).toHaveCount(0);
  await shot(page, "waves-point");
});

test("the forecast strip scrolls with a mouse drag and a plain wheel, and the clock follows", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name.includes("mobile"), "mouse only; touch pans natively");
  await open(page, "mode=wind&lat=54&lon=5&z=8", true);
  await page.mouse.click(400, 300);
  const strip = page.locator(".swd-pm-tile-strip");
  const head = page.locator(".swd-pm-tile-head p");
  const box = (await strip.boundingBox())!;
  const y = box.y + box.height / 2;
  const start = await strip.evaluate((element) => element.scrollLeft);
  const before = await head.innerText();
  await page.mouse.move(box.x + box.width / 2 + 100, y);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 - 50, y, { steps: 8 });
  await page.mouse.up();
  await expect.poll(() => strip.evaluate((element) => element.scrollLeft)).toBeGreaterThan(start + 100);
  await expect(head).not.toHaveText(before);
  const dragged = await strip.evaluate((element) => element.scrollLeft);
  await page.mouse.wheel(0, 120);
  await expect.poll(() => strip.evaluate((element) => element.scrollLeft)).toBeGreaterThan(dragged + 60);
});
