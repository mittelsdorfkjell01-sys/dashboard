import { useEffect, useState } from "react";
import { SunIcon, MoonIcon } from "../lib/icons";
import { applyTheme, resolveInitialTheme, type Theme } from "../lib/theme";

export default function ThemeToggle({ menuItem = false }: { menuItem?: boolean }) {
  const [theme, setTheme] = useState<Theme>(resolveInitialTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggle = () => setTheme((prev) => (prev === "light" ? "dark" : "light"));
  const label = theme === "light" ? "Dark Mode aktivieren" : "Light Mode aktivieren";
  const visibleLabel = theme === "light" ? "Dark Mode" : "Light Mode";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      className={
        menuItem
          ? "flex min-h-11 w-full items-center justify-between px-3 text-ui font-medium text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          : "inline-flex h-11 w-11 items-center justify-center text-ink transition-opacity hover:opacity-60"
      }
    >
      {menuItem && <span>{visibleLabel}</span>}
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
