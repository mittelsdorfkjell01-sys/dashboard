import { expect, test, type Locator } from "@playwright/test";

/**
 * The burger menu's fragile promises:
 *  • its rows do not move when the language changes,
 *  • its order: search, site links, account, then preferences and who you
 *    are at the foot,
 *  • the legal pages are found by its search, not listed as rows, and a page
 *    opened from a result leads back into the menu,
 *  • its switches animate like a physical toggle, press included.
 *
 * All of it was reported from a phone, so the sheet variant is the subject;
 * the viewport is set explicitly, which makes the spec meaningful in the
 * desktop project too (the component picks its variant by viewport).
 */

const OPEN = /Kontomenü/;

const rowTops = (sheet: Locator) =>
  sheet.evaluate((el) => {
    const tops: Record<string, number> = {};
    el.querySelectorAll("button, a, input").forEach((node) => {
      const label = (node.textContent || "").trim().slice(0, 20) || node.tagName;
      tops[label] = Math.round(node.getBoundingClientRect().y);
    });
    return tops;
  });

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
});

test("the menu rows keep their place when the language changes", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  const sheet = page.getByRole("dialog");
  await expect(sheet).toBeVisible();

  const german = await rowTops(sheet);
  await sheet.getByRole("button", { name: /Sprache/ }).click();
  await expect(sheet.getByRole("link", { name: "Sign in" })).toBeVisible();
  const english = await rowTops(sheet);

  expect(english["Darkmode"]).toBe(german["Darkmode"]);
  expect(english["LanguageEN"]).toBe(german["SpracheDE"]);
  expect(english["Sign in"]).toBe(german["Anmelden"]);
});

test("search, then the site links; preferences and sign-in at the foot", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  const sheet = page.getByRole("dialog");

  const box = async (l: ReturnType<typeof sheet.getByRole>) => (await l.boundingBox())!;
  const darkmode = await box(sheet.getByRole("switch").first());
  const language = await box(sheet.getByRole("button", { name: /Sprache/ }));
  const search = await box(sheet.getByRole("searchbox", { name: "Im Menü suchen" }));
  const map = await box(sheet.getByRole("link", { name: "Windkarte" }));
  const help = await box(sheet.getByRole("link", { name: "Daten & Fragen" }));
  const contact = await box(sheet.getByRole("link", { name: "Kontakt" }));
  const suggest = await box(sheet.getByRole("link", { name: "Spot vorschlagen" }));
  const signIn = await box(sheet.getByRole("link", { name: "Anmelden" }));

  for (const [upper, lower] of [
    [search, map],
    [map, help],
    [help, contact],
    [contact, suggest],
    [suggest, darkmode],
    [darkmode, language],
    [language, signIn],
  ]) {
    expect(upper.y).toBeLessThan(lower.y);
  }
  // The low search field, with the magnifier only: no placeholder copy.
  expect(search.height).toBe(36);
  await expect(sheet.getByRole("searchbox")).not.toHaveAttribute("placeholder");
  // Preferences and sign-in are pinned to the foot of the sheet.
  expect(signIn.y + signIn.height).toBeGreaterThan(780 - 100);
  expect(darkmode.y).toBeGreaterThan(780 / 2);

  // Plain text rows: no icons, regular weight, 12px.
  await expect(sheet.locator("nav svg")).toHaveCount(0);
  const style = await sheet
    .getByRole("link", { name: "Windkarte" })
    .evaluate((el) => ({ size: getComputedStyle(el).fontSize, weight: getComputedStyle(el).fontWeight }));
  expect(style).toEqual({ size: "12px", weight: "400" });
  // "Anmelden" keeps its earlier form: the person glyph and a semibold label.
  const signInLink = sheet.getByRole("link", { name: "Anmelden" });
  await expect(signInLink.locator("svg")).toHaveCount(1);
  const label = await signInLink.locator("span").last()
    .evaluate((el) => ({ size: getComputedStyle(el).fontSize, weight: getComputedStyle(el).fontWeight }));
  expect(label).toEqual({ size: "14px", weight: "600" });

  // The legal pages stay in the footer; the search reaches them.
  for (const label of ["Nutzungsbedingungen", "Impressum", "Datenschutz"]) {
    await expect(sheet.getByRole("link", { name: label, exact: true })).toHaveCount(0);
  }
});

test("signed out, suggesting a spot leads through sign-in", async ({ page }) => {
  // No backend runs under e2e; answer the session check the way a signed-out
  // visitor gets it, so the account guard redirects instead of reporting the
  // account service as unreachable.
  // Match the API path only: a glob like `**/account/**` also catches the dev
  // server's own module `/src/pages/account/…` and breaks the page.
  await page.route((url) => url.pathname.startsWith("/account/"), (route) =>
    route.fulfill({
      status: 401,
      json: { detail: "Nicht angemeldet." },
      headers: {
        "access-control-allow-origin": route.request().headers()["origin"] ?? "*",
        "access-control-allow-credentials": "true",
      },
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  await page.getByRole("dialog").getByRole("link", { name: "Spot vorschlagen" }).click();
  await expect(page).toHaveURL(/\/anmelden\?redirect=%2Fkonto%2Fspots/);
});

test("the search finds a legal section and lands on it", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  const sheet = page.getByRole("dialog");
  await sheet.getByRole("searchbox").fill("cookies");

  // While searching, the results replace the rest of the menu.
  await expect(sheet.getByRole("link", { name: "Windkarte" })).toHaveCount(0);
  await expect(sheet.getByRole("switch")).toHaveCount(0);
  await sheet.getByRole("link", { name: /Cookies und lokale Speicherung/ }).click();

  await expect(page).toHaveURL(/\/datenschutz#cookies$/);
  const heading = page.getByRole("heading", { name: "8. Cookies und lokale Speicherung" });
  await expect(heading).toBeInViewport();
});

test("Enter opens the first result", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  await page.getByRole("dialog").getByRole("searchbox").fill("impressum");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/impressum$/);
});

test("the search keeps focus when the page re-renders under the open menu", async ({ page }) => {
  // The session check resolves while the visitor is already typing. It used to
  // re-run the sheet's open effect, which moved focus to the close button, so
  // Enter closed the menu instead of opening the result.
  await page.route(
    (url) => url.pathname === "/account/me",
    async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await route.fulfill({
        status: 401,
        json: { detail: "Nicht angemeldet." },
        headers: {
          "access-control-allow-origin": route.request().headers()["origin"] ?? "*",
          "access-control-allow-credentials": "true",
        },
      });
    },
  );
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  const search = page.getByRole("dialog").getByRole("searchbox");
  await search.fill("impressum");
  await page.waitForTimeout(2000);
  await expect(search).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/impressum$/);
});

test("the menu search shows no ring or edge when tapped", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  const search = page.getByRole("dialog").getByRole("searchbox");
  await search.click();
  await expect(search).toBeFocused();
  // The caret is the focus signal here: no outline colour, no ring (it read
  // as a white edge in dark mode).
  const focus = await search.evaluate((el) => {
    const s = getComputedStyle(el);
    return { outline: s.outlineColor, shadow: s.boxShadow };
  });
  expect(focus).toEqual({ outline: "rgba(0, 0, 0, 0)", shadow: "none" });
});

test("a search with no match says so", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  await page.getByRole("dialog").getByRole("searchbox").fill("xyzzy");
  await expect(page.getByRole("status").filter({ hasText: "xyzzy" })).toBeVisible();
});

// Every page the search reaches carries the same way back into the menu.
for (const [query, path] of [
  ["Daten & Fragen", "/fragen"],
  ["Kontakt", "/kontakt"],
  ["Nutzungsbedingungen", "/nutzungsbedingungen"],
  ["Impressum", "/impressum"],
  ["Datenschutz", "/datenschutz"],
] as const) {
  test(`${query} opened from the menu search comes back into the menu`, async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: OPEN }).first().click();
    await page.getByRole("dialog").getByRole("searchbox").fill(query);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(new RegExp(`${path}$`));

    await page.getByRole("button", { name: "Zurück" }).first().click();
    await expect(page).not.toHaveURL(new RegExp(path));
    await expect(page.getByRole("dialog").getByRole("searchbox")).toBeVisible();
  });
}

test("the sign-in page and the footer still link the Impressum", async ({ page }) => {
  await page.goto("/anmelden");
  await expect(page.getByRole("contentinfo").getByRole("link", { name: "Impressum" })).toBeVisible();
});

test("the switch thumb runs on the switch curve and stretches under the press", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: OPEN }).first().click();
  // The menu opens as a circle out of its button (300ms); taps only land
  // inside the circle, so press once it has fully opened.
  await expect(page.getByRole("dialog")).toHaveAttribute("data-shown", "true");
  await page.waitForTimeout(350);
  const row = page.getByRole("dialog").getByRole("switch").first();
  const thumb = row.locator('[data-part="switch-thumb"]');
  const fill = row.locator('[data-part="switch-fill"]');

  const easing = await thumb.evaluate((el) => getComputedStyle(el).transitionTimingFunction);
  expect(easing).toContain("1.6"); // the overshoot of ease-switch

  const width = () => thumb.evaluate((el) => parseFloat(getComputedStyle(el).width));
  const resting = await width();
  const box = (await row.boundingBox())!;
  await page.mouse.move(box.x + box.width - 30, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(150);
  expect(await width()).toBeGreaterThan(resting);
  await page.mouse.up();

  // And it travels: the thumb ends up on the other side of the track.
  await page.waitForTimeout(450);
  const travelled = await thumb.evaluate((el) => new DOMMatrix(getComputedStyle(el).transform).m41);
  expect(travelled).toBeGreaterThan(20);
  expect(await width()).toBeCloseTo(resting, 0);
  // The brand blue has filled the track from the left behind the thumb.
  const fillScale = await fill.evaluate((el) => new DOMMatrix(getComputedStyle(el).transform).a);
  expect(fillScale).toBeCloseTo(1, 2);
});
