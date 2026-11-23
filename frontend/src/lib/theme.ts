import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

export function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem("sw-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  window.localStorage.setItem("sw-theme", theme);
}

/** Apply the persisted/system theme before React paints any route. */
export function initializeTheme(): void {
  applyTheme(resolveInitialTheme());
}

/** The site theme as `applyTheme` stamps it on <html>, live: the maps follow
 *  it (public map since 2026-11-20, Spot-Info map since 2026-11-22). */
export function readSiteTheme(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

export function useSiteTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(readSiteTheme);
  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(readSiteTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return theme;
}
