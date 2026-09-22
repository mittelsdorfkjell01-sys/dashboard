# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: frontend\e2e\landing-loading.spec.ts >> all spots expand in place without a second catalogue request or scroll reset
- Location: frontend\e2e\landing-loading.spec.ts:25:1

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/", waiting until "load"

```

# Test source

```ts
  1   | import { expect, test } from "@playwright/test";
  2   | 
  3   | const spots = Array.from({ length: 36 }, (_, index) => ({
  4   |   id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
  5   |   slug: `spot-${index}`,
  6   |   name: `Spot ${index}`,
  7   |   region_id: null,
  8   |   region_name: "Testregion",
  9   |   region_country: "DE",
  10  |   location: { lat: 54 + index / 100, lon: 10 },
  11  |   sports: ["kitesurf"],
  12  |   image: null,
  13  |   facing: null,
  14  |   water_type: [],
  15  |   bottom_type: [],
  16  |   level: [],
  17  |   water_character: [],
  18  |   style: [],
  19  |   facilities: null,
  20  |   best_months: null,
  21  |   typical_wind_kt: null,
  22  |   typical_wave_height_m: null,
  23  | }));
  24  | 
  25  | test("all spots expand in place without a second catalogue request or scroll reset", async ({ page }) => {
  26  |   let catalogueCalls = 0;
  27  |   await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
  28  |     const url = new URL(route.request().url());
  29  |     if (url.pathname === "/spots") {
  30  |       catalogueCalls += 1;
  31  |       expect(url.searchParams.get("limit")).toBe("500");
  32  |       return route.fulfill({ json: spots });
  33  |     }
  34  |     if (url.pathname === "/spots/top" || url.pathname === "/spots/live") {
  35  |       return route.fulfill({ json: [] });
  36  |     }
  37  |     if (url.pathname === "/auth/me") {
  38  |       return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
  39  |     }
  40  |     return route.fulfill({ json: [] });
  41  |   });
  42  | 
> 43  |   await page.goto("/");
      |              ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  44  |   await expect(page.locator("p", { hasText: /^Spot 19$/ })).toBeVisible();
  45  |   await expect(page.locator("p", { hasText: /^Spot 20$/ })).toHaveCount(0);
  46  | 
  47  |   const button = page.getByRole("button", { name: "Alle Spots anzeigen" });
  48  |   await button.scrollIntoViewIfNeeded();
  49  |   const before = await page.evaluate(() => window.scrollY);
  50  |   await button.click();
  51  | 
  52  |   await expect(page.locator("p", { hasText: /^Spot 35$/ })).toBeVisible();
  53  |   const after = await page.evaluate(() => window.scrollY);
  54  |   expect(after).toBeGreaterThan(before - 50);
  55  |   expect(catalogueCalls).toBe(1);
  56  | });
  57  | 
  58  | test("hero search remains fully visible when opened after scrolling", async ({ page }, testInfo) => {
  59  |   test.skip(testInfo.project.name.includes("mobile"), "Desktop hero search uses the inline panel");
  60  | 
  61  |   await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
  62  |     const url = new URL(route.request().url());
  63  |     if (url.pathname === "/spots") return route.fulfill({ json: spots });
  64  |     if (url.pathname === "/auth/me") {
  65  |       return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
  66  |     }
  67  |     return route.fulfill({ json: [] });
  68  |   });
  69  | 
  70  |   await page.goto("/");
  71  |   await page.evaluate(() => window.scrollTo(0, window.innerHeight * 0.42));
  72  |   await page.locator("#landing-search").getByRole("button", { name: "Jetzt suchen" }).click();
  73  | 
  74  |   const stack = page.getByTestId("desktop-search-stack");
  75  |   const panel = page.getByTestId("desktop-search-panel");
  76  |   await expect(stack).toBeVisible();
  77  |   await expect(panel).toBeVisible();
  78  |   await expect(page.getByRole("textbox", { name: "Region oder Spot suchen" })).toBeFocused();
  79  | 
  80  |   const box = await stack.boundingBox();
  81  |   const panelBox = await panel.boundingBox();
  82  |   const viewport = page.viewportSize();
  83  |   expect(box).not.toBeNull();
  84  |   expect(panelBox).not.toBeNull();
  85  |   expect(viewport).not.toBeNull();
  86  |   expect(box!.y).toBeGreaterThanOrEqual(23);
  87  |   expect(panelBox!.y + panelBox!.height).toBeLessThanOrEqual(viewport!.height - 23);
  88  | });
  89  | 
  90  | test("mobile search contains focus and returns it to its trigger", async ({ page }, testInfo) => {
  91  |   test.skip(!testInfo.project.name.includes("mobile"), "Mobile search uses the full-screen sheet");
  92  | 
  93  |   await page.route(/^http:\/\/(?:localhost|127\.0\.0\.1):8000\//, (route) => {
  94  |     const url = new URL(route.request().url());
  95  |     if (url.pathname === "/spots") return route.fulfill({ json: spots });
  96  |     if (url.pathname === "/auth/me") {
  97  |       return route.fulfill({ status: 401, json: { detail: "not authenticated" } });
  98  |     }
  99  |     return route.fulfill({ json: [] });
  100 |   });
  101 | 
  102 |   await page.goto("/");
  103 |   const trigger = page.locator("#landing-search").getByRole("button", { name: "Jetzt suchen" });
  104 |   await trigger.click();
  105 | 
  106 |   const dialog = page.getByRole("dialog", { name: "Suche" });
  107 |   const close = dialog.getByRole("button", { name: "Schließen" });
  108 |   await expect(close).toBeFocused();
  109 | 
  110 |   await page.keyboard.press("Shift+Tab");
  111 |   await expect(dialog.getByRole("button", { name: "Suchen", exact: true })).toBeFocused();
  112 | 
  113 |   await close.click();
  114 |   await expect(trigger).toBeFocused();
  115 | });
  116 | 
```