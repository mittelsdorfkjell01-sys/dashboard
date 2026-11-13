import { expect, test } from "@playwright/test";

/**
 * "Daten & Fragen" (/fragen) merged the former FAQ, Kontakt and Über-uns pages.
 * Two things about that merge are easy to break silently and are therefore
 * pinned here: the old URLs must keep working, and the entry other pages deep
 * link into must actually be open when its hash is used.
 */

test("the old contact URL lands on the contact section", async ({ page }) => {
  await page.goto("/kontakt");
  await expect(page).toHaveURL(/\/fragen#kontakt$/);
  await expect(page.locator("#kontakt")).toBeVisible();
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
