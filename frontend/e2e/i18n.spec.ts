import { expect, test } from "@playwright/test";

/**
 * Guards the one i18n failure mode neither TypeScript nor ESLint can see: a
 * *valid* catalogue key that reaches the DOM as literal text because its render
 * site printed the raw value instead of passing it through `t()`.
 *
 * It happened for real — the style and water label lists in MeinSetup carried
 * catalogue keys while their rows still rendered the tuple value, so the page
 * would have read "setup.styles.freeride". The key is a plain `string` in a
 * `string` slot, so the compiler is satisfied and the lint guard (which looks
 * for hard-coded German, the opposite problem) stays quiet.
 *
 * scripts/i18n-report.mjs performs the same check statically over all sources.
 * This spec is the runtime half: it covers the surfaces a visitor actually sees
 * without signing in — the footer and the account menu, which between them
 * exercise the shared SITE_LINKS list and interpolation.
 */
test("migrated surfaces render German copy, not catalogue keys", async ({ page }) => {
  await page.goto("/");

  // Footer and account menu both render the shared SITE_LINKS list.
  await expect(page.getByText("Fragen und Antworten").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Impressum" }).first()).toBeVisible();

  // The account menu's trigger label, heading and actions are all catalogue keys.
  await page.getByRole("button", { name: /Kontomenü|Konto/ }).first().click();
  await expect(page.getByText("Willkommen").first()).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Anmelden" }).first()).toBeVisible();

  // Nothing anywhere on the page may look like a catalogue path.
  const lines = (await page.locator("body").innerText()).split("\n");
  const keyish = lines.filter((line) =>
    /^(common|footer|siteLinks|header|account|accountNav|menu|settings|setup)\.[A-Za-z.]+$/.test(line.trim()),
  );
  expect(keyish, `catalogue keys rendered as text: ${keyish.join(", ")}`).toHaveLength(0);
});
