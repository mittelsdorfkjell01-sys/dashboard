import { useEffect, useState } from "react";
import { SunIcon, MoonIcon } from "../lib/icons";
import { applyTheme, resolveInitialTheme, type Theme } from "../lib/theme";

type Variant = "icon" | "menu" | "switch";

/**
 * Theme control in three shapes:
 *  - "icon"   → a bare sun/moon button for header rails
 *  - "menu"   → a dropdown row with a small label + sun/moon (desktop account menu)
 *  - "switch" → a full-width "Darkmode" row with an iOS-style pill switch, matching
 *               the mobile account sheet in Figma (Frame 76).
 */
export default function ThemeToggle({
  menuItem = false,
  variant = menuItem ? "menu" : "icon",
}: {
  menuItem?: boolean;
  variant?: Variant;
}) {
  const [theme, setTheme] = useState<Theme>(resolveInitialTheme);
  const dark = theme === "dark";

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggle = () => setTheme((prev) => (prev === "light" ? "dark" : "light"));
  const label = dark ? "Light Mode aktivieren" : "Dark Mode aktivieren";

  if (variant === "switch") {
    return (
      <button
        type="button"
        onClick={toggle}
        role="switch"
        aria-checked={dark}
        aria-label={label}
        className="flex min-h-[52px] w-full items-center justify-between px-3 text-body font-medium text-ink transition-opacity active:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        <span>Darkmode</span>
        <span
          aria-hidden
          className={`relative inline-flex h-8 w-14 shrink-0 items-center rounded-full px-1 transition-colors duration-200 ${dark ? "bg-ink" : "bg-band ring-1 ring-line"}`}
        >
          <span
            className={`grid h-6 w-6 place-items-center rounded-full bg-surface ring-1 ring-black/5 transition-transform duration-200 motion-reduce:transition-none ${dark ? "translate-x-6" : "translate-x-0"}`}
          >
            <MoonIcon width={12} height={12} className="text-ink" />
          </span>
        </span>
      </button>
    );
  }

  const visibleLabel = dark ? "Light Mode" : "Dark Mode";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      className={
        variant === "menu"
          ? "flex min-h-11 w-full items-center justify-between px-3 text-ui font-medium text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          : "inline-flex h-11 w-11 items-center justify-center text-ink transition-opacity hover:opacity-60"
      }
    >
      {variant === "menu" && <span>{visibleLabel}</span>}
      <span className="relative grid h-5 w-5 place-items-center" aria-hidden>
        <span className={`absolute grid place-items-center transition-[opacity,transform] duration-200 motion-reduce:transition-none ${theme === "light" ? "scale-100 rotate-0 opacity-100" : "scale-75 rotate-[35deg] opacity-0"}`}>
          <MoonIcon width={18} height={18} />
        </span>
        <span className={`absolute grid place-items-center transition-[opacity,transform] duration-200 motion-reduce:transition-none ${theme === "dark" ? "scale-100 rotate-0 opacity-100" : "scale-75 -rotate-[35deg] opacity-0"}`}>
          <SunIcon width={18} height={18} />
        </span>
      </span>
    </button>
  );
}
