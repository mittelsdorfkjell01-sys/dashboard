import { useEffect, useState } from "react";
import { SunIcon, MoonIcon } from "../lib/icons";
import { applyTheme, resolveInitialTheme, type Theme } from "../lib/theme";
import { SwitchTrack } from "./ui/Switch";

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
  // The label names the mode you switch *to*: dark active → "Whitemode", light
  // active → "Darkmode".
  const targetLabel = dark ? "Whitemode" : "Darkmode";
  const label = `${targetLabel} aktivieren`;

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
        <span>{targetLabel}</span>
        <SwitchTrack checked={dark} icon={<MoonIcon width={12} height={12} />} />
      </button>
    );
  }

  const visibleLabel = targetLabel;
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
        <span className={`absolute grid place-items-center transition-[opacity,transform] duration-base motion-reduce:transition-none ${theme === "light" ? "scale-100 rotate-0 opacity-100" : "scale-75 rotate-[35deg] opacity-0"}`}>
          <MoonIcon width={18} height={18} />
        </span>
        <span className={`absolute grid place-items-center transition-[opacity,transform] duration-base motion-reduce:transition-none ${theme === "dark" ? "scale-100 rotate-0 opacity-100" : "scale-75 -rotate-[35deg] opacity-0"}`}>
          <SunIcon width={18} height={18} />
        </span>
      </span>
    </button>
  );
}
