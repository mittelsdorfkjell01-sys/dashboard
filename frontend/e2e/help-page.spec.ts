import { expect, test } from "@playwright/test";

/**
 * "Daten & Fragen" (/fragen) carries help and project background; contact is
 * its own page again (/kontakt). What is easy to break silently and therefore
 * pinned here: the old URLs must keep working, the entry other pages deep link
 * into must actually be open when its hash is used, and the two navigations
 * into the page — the sticky column on a desktop, the bottom jump menu on a
 * phone — must both mark where the reader is and not sit side by side.
 */

test("contact is its own page", async ({ page }) => {
  await page.goto("/kontakt");
  await expect(page).toHaveURL(/\/kontakt$/);
  await expect(page.locator("h1")).toHaveText("Kontakt");
  await expect(page.getByText("Worum geht es?")).toBeVisible();
});

test("the former contact anchor forwards to the contact page", async ({ page }) => {
  // Bookmarks, old mails and the previous /kontakt redirect all carry it.
  await page.goto("/fragen#kontakt");
  await expect(page).toHaveURL(/\/kontakt$/);
  await expect(page.locator("h1")).toHaveText("Kontakt");
});

test("the help page does not carry contact any more", async ({ page }) => {
  await page.goto("/fragen");
  await expect(page.locator("#kontakt")).toHaveCount(0);
  await expect(page.getByText("Worum geht es?")).toHaveCount(0);
});

test.describe("the sticky column", () => {
  // These are about what happens *during* the scroll, so the animation has to
  // exist: a machine with reduced motion switched on jumps to the target.
  test.use({ reducedMotion: "no-preference" });
  // The column is a desktop surface, and a touch device deliberately runs
  // without Lenis (see lib/lenis.tsx), so there is no travel to observe there.
  test.skip(({ isMobile }) => !!isMobile, "desktop surface");

  /** How far the section still is from the top of the window. Measured on the
   *  element, not on `window.scrollY`: Lenis does the scrolling. */
  const distance = (page: import("@playwright/test").Page, id: string) =>
    page.evaluate((section) => document.getElementById(section)!.getBoundingClientRect().top, id);

  test("the very first jump on a freshly opened page scrolls", async ({ page }) => {
    // It did not: Lenis had measured the document while the route was still a
    // loading shell, and clamped every jump against that stale height. The
    // first section link on a freshly opened page did nothing at all, and only
    // after scrolling by hand once did the navigation start working.
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/fragen");
    await page.locator("#konto").waitFor();
    expect(await distance(page, "konto")).toBeGreaterThan(1000);

    await page.getByRole("navigation", { name: "Auf dieser Seite" }).getByRole("link", { name: "Konto" }).click();
    await page.waitForTimeout(1500);
    expect(await distance(page, "konto")).toBeLessThan(300);
  });

  test("the clicked section is marked at once, not when the scroll lands", async ({ page }) => {
    // The jump is a ~1.1s smooth scroll. The marker used to be driven only by
    // the intersection observer, i.e. by where the reader *is*, so it stayed
    // on the section they came from for the whole travel — one entry behind
    // all the way down the list.
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/fragen");
    const nav = page.getByRole("navigation", { name: "Auf dieser Seite" });
    await expect(nav.getByRole("link", { name: "Sicherheit" })).toHaveAttribute("aria-current", "true");

    const account = nav.getByRole("link", { name: "Konto" });
    await account.click();
    await page.waitForTimeout(60);

    // Still a long way off — and the marker is already on the clicked entry.
    expect(await distance(page, "konto")).toBeGreaterThan(400);
    expect(await account.getAttribute("aria-current")).toBe("true");
    expect(await nav.getByRole("link", { name: "Sicherheit" }).getAttribute("aria-current")).toBeNull();

    // And it stays there once the page has actually arrived.
    await page.waitForTimeout(1500);
    expect(await distance(page, "konto")).toBeLessThan(300);
    await expect(account).toHaveAttribute("aria-current", "true");
  });

  test("a deep link marks its section without waiting for the scroll", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/fragen#saison");
    const nav = page.getByRole("navigation", { name: "Auf dieser Seite" });
    await expect(nav.getByRole("link", { name: "Saison" })).toHaveAttribute("aria-current", "true");
  });
});

test("on a phone the sections live in the bottom menu, not in a scrolling strip", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto("/fragen");
  await expect(page.getByRole("navigation", { name: "Auf dieser Seite" })).toBeHidden();

  await page.getByRole("button", { name: "Abschnittsmenü öffnen" }).click();
  const menu = page.getByRole("dialog", { name: "Auf dieser Seite" });
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("link")).toHaveCount(8);

  // The panel is the bare list: no title row, no close button, no filter.
  await expect(menu.getByRole("button")).toHaveCount(0);
  await expect(menu.getByRole("searchbox")).toHaveCount(0);

  await menu.getByRole("link", { name: /Gezeiten/ }).click();
  await expect(menu).toHaveCount(0);
  await expect(page).toHaveURL(/\/fragen#wetter$/);

  // Reopening says where the reader now is.
  await page.getByRole("button", { name: "Abschnittsmenü öffnen" }).click();
  await expect(
    page.getByRole("dialog", { name: "Auf dieser Seite" }).getByRole("link", { name: /Gezeiten/ }),
  ).toHaveAttribute("aria-current", "true");
});

test("the jump menu closes on a tap beside it and on the pill itself", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto("/fragen");
  const trigger = page.getByRole("button", { name: "Abschnittsmenü öffnen" });
  const menu = page.getByRole("dialog", { name: "Auf dieser Seite" });

  // A tap on the page beside the panel.
  await trigger.click();
  await expect(menu).toBeVisible();
  await page.mouse.click(20, 60);
  await expect(menu).toHaveCount(0);

  // And the pill is a toggle.
  await trigger.click();
  await expect(menu).toBeVisible();
  await trigger.click();
  await expect(menu).toHaveCount(0);
});

test("a swipe down over the jump menu dismisses it", async ({ page, context }, testInfo) => {
  test.skip(!testInfo.project.name.includes("mobile"), "Touch gesture");
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto("/fragen");
  await page.getByRole("button", { name: "Abschnittsmenü öffnen" }).click();
  const menu = page.getByRole("dialog", { name: "Auf dieser Seite" });
  await expect(menu).toBeVisible();

  // A real touch drag: the emulated mouse is turned into a scroll gesture by
  // the browser, so this is the only way to exercise what a thumb does.
  const box = (await menu.boundingBox())!;
  const x = Math.round(box.x + box.width / 2);
  const y = Math.round(box.y + 20);
  const cdp = await context.newCDPSession(page);
  const touch = (type: string, clientY: number) =>
    cdp.send("Input.dispatchTouchEvent", {
      type,
      touchPoints: type === "touchEnd" ? [] : [{ x, y: clientY }],
    } as never);
  await touch("touchStart", y);
  for (const step of [20, 45, 75, 110]) await touch("touchMove", y + step);
  await touch("touchEnd", y + 110);

  await expect(menu).toHaveCount(0);
  // Dismissing is not navigating: the reader stays where they were.
  await expect(page).not.toHaveURL(/#/);
});

test("the old about URL lands on the project section", async ({ page }) => {
  await page.goto("/ueber-uns");
  await expect(page).toHaveURL(/\/fragen#projekt$/);
  await expect(page.locator("#projekt")).toBeVisible();
});

test("/faq still renders the page", async ({ page }) => {
  await page.goto("/faq");
  await expect(page.locator("h1")).toHaveText("Daten & Fragen");
});

test("the regional wind entry opens when linked by its hash", async ({ page }) => {
  // Closed by default, like every other entry in the accordion.
  await page.goto("/fragen");
  await expect(page.locator("#regionale-windverfuegbarkeit")).not.toHaveAttribute("open", /.*/);

  // The region pages link here; arriving on the hash must reveal the answer
  // rather than leaving the visitor in front of a collapsed summary.
  await page.goto("/fragen#regionale-windverfuegbarkeit");
  await expect(page.locator("#regionale-windverfuegbarkeit")).toHaveAttribute("open", /.*/);
  await expect(
    page.getByText("Vorhersage und Windzuverlässigkeit findest du auf den einzelnen Spotseiten."),
  ).toBeVisible();
});

test("the safety block is open without any interaction", async ({ page }) => {
  await page.goto("/fragen");
  await expect(page.getByText("Ein Spoteintrag ist keine Sicherheitsfreigabe")).toBeVisible();
  await expect(page.getByText("In der EU erreichst du Rettungsdienste unter 112.")).toBeVisible();
});

test("the page does not scroll horizontally on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto("/fragen");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});

test("every string on the page comes from the catalogue", async ({ page }) => {
  await page.goto("/fragen");
  // Open every accordion, so the answers are in the DOM too.
  for (const summary of await page.locator("summary").all()) await summary.click();

  const lines = (await page.locator("body").innerText()).split("\n");
  const keyish = lines.filter((line) => /^help\.[A-Za-z.]+$/.test(line.trim()));
  expect(keyish, `catalogue keys rendered as text: ${keyish.join(", ")}`).toHaveLength(0);
});

test("the page is fully translated into English", async ({ page }) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem("swd.locale", "en");
    } catch {
      /* private browsing — the test then runs in German and fails loudly */
    }
  });
  await page.goto("/fragen");
  await expect(page.locator("h1")).toHaveText("Data & questions");
  await expect(page.getByText("A spot entry is not a safety approval")).toBeVisible();
  await expect(page.getByText("In the EU, call 112 for emergency services.")).toBeVisible();
  // The German source must not leak through the English catalogue.
  await expect(page.getByText("Ein Spoteintrag ist keine Sicherheitsfreigabe")).toHaveCount(0);
});

test("a scrolled help page keeps a back arrow pinned top-left", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/impressum");
  await page.goto("/fragen");
  // The page is a lazily loaded chunk: wheel before it has rendered and there
  // is nothing to scroll yet (the loading shell is one viewport tall), so the
  // turn is lost. Wait for the page's own back link, which the pin hands off from.
  await expect(page.locator("[data-page-back]")).toBeVisible();
  const pinned = page.locator("[data-scroll-back]");
  await expect(pinned).toHaveAttribute("aria-hidden", "true");
  await page.mouse.move(200, 400);
  await page.mouse.wheel(0, 1500);
  await expect(pinned).not.toHaveAttribute("aria-hidden", "true");
  if (process.env.SCROLL_BACK_SHOTS) await page.screenshot({ path: `${process.env.SCROLL_BACK_SHOTS}/fragen.png` });
  await pinned.click();
  await expect(page).toHaveURL(/\/impressum$/);
});
