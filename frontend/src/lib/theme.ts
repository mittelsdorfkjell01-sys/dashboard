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
