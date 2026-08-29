import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { SunIcon, MoonIcon } from "../lib/icons";
import { applyTheme, resolveInitialTheme, type Theme } from "../lib/theme";

export default function ThemeToggle({ menuItem = false }: { menuItem?: boolean }) {
  const [theme, setTheme] = useState<Theme>(resolveInitialTheme);
  const reduce = useReducedMotion();

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
        <AnimatePresence initial={false} mode="wait">
          <motion.span
            key={theme}
            initial={reduce ? false : { opacity: 0, rotate: -35, scale: 0.72 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, rotate: 35, scale: 0.72 }}
            transition={{ duration: reduce ? 0 : 0.18, ease: "easeOut" }}
            className="absolute grid place-items-center"
          >
            {theme === "light" ? (
              <MoonIcon width={18} height={18} />
            ) : (
              <SunIcon width={18} height={18} />
            )}
          </motion.span>
        </AnimatePresence>
      </span>
    </button>
  );
}
