// Admin theme — light/dark for the back office only.
//
// Puts an `admin-scope` class + `data-theme` on <body> while any admin route is
// mounted, and removes both on unmount. Scoping on <body> (rather than a
// wrapper div) means portaled dialogs (Modal → document.body) inherit the
// admin tokens too. The whole token layer + brand-utility remap lives in
// ui/admin-theme.css, imported here so it ships only in the admin bundle.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import "./ui/admin-theme.css";

export type AdminTheme = "light" | "dark";

const STORAGE_KEY = "swd-admin-theme";

function systemTheme(): AdminTheme {
  return typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function initialTheme(): AdminTheme {
  if (typeof window === "undefined") return "light";
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved === "light" || saved === "dark" ? saved : systemTheme();
}

interface Ctx {
  theme: AdminTheme;
  setTheme: (t: AdminTheme) => void;
  toggle: () => void;
}

const AdminThemeCtx = createContext<Ctx | null>(null);

export function AdminThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<AdminTheme>(initialTheme);
  // Track whether the user has made an explicit choice; if not, keep following
  // the OS setting live.
  const [explicit, setExplicit] = useState<boolean>(() =>
    typeof window !== "undefined"
      ? window.localStorage.getItem(STORAGE_KEY) != null
      : false
  );

  // Apply the scope + theme to <body> for the lifetime of the admin. Layout
  // effect so the class/attr land before first paint (no token flash).
  useLayoutEffect(() => {
    const { body } = document;
    body.classList.add("admin-scope");
    body.dataset.theme = theme;
    return () => {
      body.classList.remove("admin-scope");
      delete body.dataset.theme;
    };
  }, [theme]);

  // Follow the OS while the user hasn't overridden it.
  useEffect(() => {
    if (explicit) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setThemeState(mq.matches ? "dark" : "light");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [explicit]);

  const setTheme = useCallback((t: AdminTheme) => {
    setThemeState(t);
    setExplicit(true);
    try {
      window.localStorage.setItem(STORAGE_KEY, t);
    } catch {
      /* private mode / storage disabled — ignore */
    }
  }, []);

  const toggle = useCallback(
    () => setTheme(theme === "dark" ? "light" : "dark"),
    [theme, setTheme]
  );

  const value = useMemo(
    () => ({ theme, setTheme, toggle }),
    [theme, setTheme, toggle]
  );

  return (
    <AdminThemeCtx.Provider value={value}>{children}</AdminThemeCtx.Provider>
  );
}

export function useAdminTheme(): Ctx {
  const ctx = useContext(AdminThemeCtx);
  if (!ctx)
    throw new Error("useAdminTheme must be used within an AdminThemeProvider");
  return ctx;
}

/** Header control: a compact sun/moon toggle. */
export function AdminThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggle } = useAdminTheme();
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      title={isDark ? "Light Mode" : "Dark Mode"}
      aria-label={isDark ? "Zu hellem Design wechseln" : "Zu dunklem Design wechseln"}
      className={`inline-grid h-8 w-8 place-items-center rounded-md border border-admin-border bg-admin-surface text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg ${className}`}
    >
      {isDark ? (
        // Sun
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.6" />
          <path
            d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      ) : (
        // Moon
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}
