import { test } from "@playwright/test";

test("LIVE crash watch", async ({ page }) => {
  page.on("crash", () => console.log("PAGE CRASHED"));
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
  const mem = async (tag: string) => {
    const m = await page.evaluate(() => {
      const perf = performance as Performance & { memory?: { usedJSHeapSize: number; jsHeapSizeLimit: number } };
      return perf.memory ? Math.round(perf.memory.usedJSHeapSize / 1e6) : -1;
    }).catch(() => -2);
    console.log(tag, "heapMB", m);
  };

  await page.goto("http://localhost:5173/map?mode=wind&lat=54.4&lon=10.2&z=7");
  await page.waitForTimeout(6000);
  await mem("start");

  const next = page.getByRole("button", { name: "Nächster Tag" });
  const label = page.locator(".swd-wx-time-value");
  for (let i = 0; i < 4; i += 1) {
    const disabled = await next.isDisabled().catch((e) => `ERR ${e.message.slice(0, 60)}`);
    if (disabled === true) { console.log("arrow disabled at step", i); break; }
    await next.click().catch((e) => console.log("click failed", e.message.slice(0, 80)));
    await page.waitForTimeout(2500);
    const text = await label.innerText().catch((e) => `ERR ${e.message.slice(0, 60)}`);
    console.log("step", i, "->", text);
    await mem(`step ${i}`);
  }
  // and dragging the slider across the day
  const slider = page.locator(".swd-wx-time input[type=range]");
  const box = await slider.boundingBox().catch(() => null);
  if (box) {
    await page.mouse.move(box.x + 10, box.y + box.height / 2);
    await page.mouse.down();
    for (let x = 0; x <= box.width; x += box.width / 20) {
      await page.mouse.move(box.x + x, box.y + box.height / 2);
      await page.waitForTimeout(120);
    }
    await page.mouse.up();
    await page.waitForTimeout(1500);
    console.log("after drag:", await label.innerText().catch((e) => `ERR ${e.message.slice(0, 60)}`));
    await mem("after drag");
  }
});
