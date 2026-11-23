import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Sign-in and registration (2026-11-20):
 *  • the glass tile keeps its top edge and grows smoothly for registration,
 *  • registration asks for email and the password twice, and one short box
 *    confirms the terms (which carry the minimum age),
 *  • Google and Apple appear only when the server has them configured,
 *  • the confirmation link signs in right away in the registering browser and
 *    asks for the password anywhere else (the server answers 428 there).
 */

const account = {
  id: "04c5fb5b-44c2-494b-b5bf-4817517339ef",
  email: "surfer@example.com",
  displayName: "Surfer",
  createdAt: "2026-01-01T10:00:00+00:00",
  emailVerified: true,
  pendingEmail: null,
  mailAvailable: true,
  preferences: {},
};

const cors = (route: Route) => ({
  "access-control-allow-origin": route.request().headers()["origin"] ?? "*",
  "access-control-allow-credentials": "true",
  "access-control-allow-methods": "GET, POST, PATCH, OPTIONS",
  "access-control-allow-headers": "content-type,x-csrf-token",
});

/** Match API paths only — a glob like `**\/account/**` also catches the dev
 *  server's own `/src/pages/account/…` modules. */
async function mockAccount(
  page: Page,
  confirm: (route: Route) => Promise<void>,
  providers: { google: boolean; apple: boolean } = { google: false, apple: false },
) {
  await page.route((url) => url.pathname.startsWith("/account/"), async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors(route) });
    if (path === "/account/oauth/providers") return route.fulfill({ json: providers, headers: cors(route) });
    if (path === "/account/email/confirm") return confirm(route);
    if (path === "/account/me") return route.fulfill({ status: 401, json: { detail: "x" }, headers: cors(route) });
    return route.fulfill({ json: { items: [], hasMore: false }, headers: cors(route) });
  });
}

test("the tile keeps its top edge and grows smoothly for registration", async ({ page }) => {
  await mockAccount(page, (route) => route.fulfill({ status: 400, headers: cors(route) }));
  for (const [w, h] of [[390, 844], [1440, 900]] as const) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("/anmelden");
    const tile = page.locator("main > div").first();
    const login = (await tile.boundingBox())!;
    await page.getByRole("button", { name: "Registrieren", exact: true }).first().click();
    // It animates rather than jumping: shortly after the click it is still
    // on its way, and it ends taller with the same top edge.
    const transition = await page.locator("[data-smooth-height]").evaluate((el) => getComputedStyle(el).transitionProperty);
    expect(transition).toBe("height");
    await expect.poll(async () => (await tile.boundingBox())!.height).toBeGreaterThan(login.height + 40);
    await page.waitForTimeout(450);
    const register = (await tile.boundingBox())!;
    expect(register.y).toBeCloseTo(login.y, 0);
    expect(register.height).toBeGreaterThan(login.height);
  }
});

test("form text keeps real font sizes without transformed glyphs", async ({ page }) => {
  await mockAccount(page, (route) => route.fulfill({ status: 400, headers: cors(route) }));
  const email = page.locator('input[type="email"]');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/anmelden");
  await expect(email).toHaveCSS("font-size", "16px");
  await expect(email).toHaveCSS("transform", "none");
  await expect(page.getByText("E-Mail", { exact: true })).toHaveCSS("font-size", "12px");

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(email).toHaveCSS("font-size", "12px");
  await expect(email).toHaveCSS("transform", "none");
});

test("registration asks for email and the password twice, with one short consent", async ({ page }) => {
  await mockAccount(page, (route) => route.fulfill({ status: 400, headers: cors(route) }));
  await page.goto("/anmelden?mode=register");
  await expect(page.getByLabel("Anzeigename")).toHaveCount(0);
  await expect(page.locator("#auth-new-password")).toHaveAttribute("autocomplete", "new-password");
  await expect(page.locator("#auth-repeat-password")).toHaveAttribute("autocomplete", "new-password");

  const boxes = page.locator('main input[type="checkbox"]');
  await expect(boxes).toHaveCount(1);
  await expect(page.getByText("Ich akzeptiere die Nutzungsbedingungen und kenne die Datenschutzerklärung.")).toBeVisible();

  // A different second entry is named under the field.
  await page.locator("#auth-new-password").fill("surfwind-123");
  await page.locator("#auth-repeat-password").fill("surfwind-124");
  await expect(page.getByText("Die Passwörter stimmen nicht überein.")).toBeVisible();
  await expect(page.locator("#auth-repeat-password")).toHaveAttribute("aria-invalid", "true");
});

test("Google and Apple show only when the server offers them, and start the flow there", async ({ page }) => {
  await mockAccount(page, (route) => route.fulfill({ status: 400, headers: cors(route) }));
  await page.goto("/anmelden?redirect=%2Fkonto%2Ffavoriten");
  await expect(page.getByText("oder weiter mit")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Mit Google fortfahren/ })).toHaveCount(0);

  await page.unrouteAll();
  await mockAccount(page, (route) => route.fulfill({ status: 400, headers: cors(route) }), { google: true, apple: true });
  await page.reload();
  const google = page.getByRole("link", { name: "Mit Google fortfahren" });
  await expect(google).toBeVisible();
  await expect(page.getByRole("link", { name: "Mit Apple fortfahren" })).toBeVisible();
  await expect(google).toHaveAttribute("href", /\/account\/oauth\/google\/start\?redirect=%2Fkonto%2Ffavoriten$/);
  await expect(page.getByText(/Damit akzeptierst du die/)).toBeVisible();
});

test("a failed provider sign-in comes back with a readable reason", async ({ page }) => {
  await mockAccount(page, (route) => route.fulfill({ status: 400, headers: cors(route) }));
  await page.goto("/anmelden?oauth_error=denied");
  await expect(page.getByRole("alert")).toHaveText("Die Anmeldung wurde abgebrochen.");
});

test("the link in the registering browser confirms and signs in", async ({ page }) => {
  let body: Record<string, unknown> | null = null;
  await mockAccount(page, async (route) => {
    body = route.request().postDataJSON();
    await route.fulfill({ json: account, headers: cors(route) });
  });
  await page.goto("/bestaetigen?token=abc&purpose=verify");
  await expect(page.getByRole("status")).toHaveText("E-Mail-Adresse bestätigt. Du bist jetzt angemeldet.");
  expect(body).toEqual({ token: "abc" });
  await expect(page.getByLabel("Neues Passwort")).toHaveCount(0);
});

test("the link on another device asks for the password, then confirms", async ({ page }) => {
  const calls: Record<string, unknown>[] = [];
  await mockAccount(page, async (route) => {
    const body = route.request().postDataJSON();
    calls.push(body);
    if (!body.password) {
      return route.fulfill({
        status: 428,
        json: { detail: "Lege ein Passwort fest, um dein Konto zu bestätigen." },
        headers: cors(route),
      });
    }
    return route.fulfill({ json: account, headers: cors(route) });
  });
  await page.goto("/bestaetigen?token=abc&purpose=verify");
  const field = page.getByLabel("Neues Passwort");
  await expect(field).toBeVisible();
  await expect(page.getByText(/nicht in dem Browser, in dem du dich registriert hast/)).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);

  await field.fill("recipient-pw-123");
  await page.getByRole("button", { name: "Bestätigen" }).click();
  await expect(page.getByRole("status")).toContainText("bestätigt");
  expect(calls).toEqual([{ token: "abc" }, { token: "abc", password: "recipient-pw-123" }]);
});
