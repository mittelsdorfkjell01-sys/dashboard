const bootImage = document.querySelector<HTMLImageElement>("#landing-boot-hero img");

async function startApplication() {
  if (bootImage) {
    try {
      await Promise.race([
        bootImage.decode(),
        new Promise<void>((resolve) => window.setTimeout(resolve, 1_200)),
      ]);
    } catch {
      // The React fallback field remains usable when the static asset fails.
    }
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
    await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
    const landingData = document.createElement("link");
    landingData.rel = "preload";
    landingData.as = "fetch";
    landingData.href = "/api/spots/landing";
    landingData.crossOrigin = "use-credentials";
    document.head.append(landingData);
    // Keep React's overlay out of the hero's first presentation window. The
    // data request already runs in parallel, so this protects LCP without
    // postponing the landing catalogue request.
    await new Promise<void>((resolve) => window.setTimeout(resolve, 250));
  }
  await import("./main");
}

void startApplication();
