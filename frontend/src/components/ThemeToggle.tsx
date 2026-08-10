import { useEffect, useState } from "react";
import { SunIcon, MoonIcon } from "../lib/icons";

type Theme = "light" | "dark";

function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem("sw-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(resolveInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("sw-theme", theme);
  }, [theme]);

  const toggle = () => setTheme((prev) => (prev === "light" ? "dark" : "light"));
  const label = theme === "light" ? "Dark Mode aktivieren" : "Light Mode aktivieren";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      className="inline-flex h-9 w-9 items-center justify-center rounded-2xl text-ink transition-colors hover:bg-band"
    >
      {theme === "light" ? (
        <MoonIcon width={18} height={18} />
      ) : (
        <SunIcon width={18} height={18} />
      )}
    </button>
  );
}
