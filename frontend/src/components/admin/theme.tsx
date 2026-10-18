// Admin theme — light (default) and dark, switched by hand.
//
// The admin back office ships two themes. Light is the default: a new browser,
// or one that never touched the toggle, lands in light. The choice is explicit
// and sticky — we deliberately do NOT follow `prefers-color-scheme`, so the
// back office does not flip under an editor mid-session because the OS crossed
// into its night schedule.
//
// The provider puts `admin-scope` on <body> while an admin route is mounted
// (removed on unmount) and writes the resolved theme as `data-admin-theme`
// beside it. That activates the matching token set + brand-utility remap in
// ui/admin-theme.css. Scoping on <body> (rather than a wrapper div) means
// portaled dialogs (Modal → document.body) inherit the tokens too. The
// stylesheet is imported here so it ships only in the admin bundle.

import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import "./ui/admin-theme.css";

export type AdminTheme = "light" | "dark";

const STORAGE_KEY = "swd:admin-theme";

function readStoredTheme(): AdminTheme {
  // Private mode / blocked site data can make localStorage throw on access,
  // not just return null — the back office must still render, in light.
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

interface AdminThemeValue {
  theme: AdminTheme;
  setTheme: (theme: AdminTheme) => void;
  toggleTheme: () => void;
}

const AdminThemeContext = createContext<AdminThemeValue | null>(null);

export function AdminThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<AdminTheme>(readStoredTheme);

  // Layout effect so the class + theme attribute land before first paint (no
  // unstyled flash, and no light flash on a dark-mode reload).
  useLayoutEffect(() => {
    const { body } = document;
    body.classList.add("admin-scope");
    body.dataset.adminTheme = theme;
    return () => {
      body.classList.remove("admin-scope");
      delete body.dataset.adminTheme;
    };
  }, [theme]);

  const setTheme = useCallback((next: AdminTheme) => {
    const { body } = document;
    // Suppress transitions for the frame in which every surface changes colour
    // at once; a cross-fade of the whole app reads as a flash, not as polish.
    body.dataset.adminThemeSwitching = "";
    setThemeState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // A rejected write only costs persistence, not the switch itself.
    }
    window.requestAnimationFrame(() => {
      delete body.dataset.adminThemeSwitching;
    });
  }, []);

  const value = useMemo<AdminThemeValue>(
    () => ({
      theme,
      setTheme,
      toggleTheme: () => setTheme(theme === "dark" ? "light" : "dark"),
    }),
    [theme, setTheme]
  );

  return <AdminThemeContext.Provider value={value}>{children}</AdminThemeContext.Provider>;
}

/** Read/switch the admin theme. Falls back to a no-op light theme outside the
 *  provider so an isolated component test does not have to wrap it. */
export function useAdminTheme(): AdminThemeValue {
  return (
    useContext(AdminThemeContext) ?? {
      theme: "light",
      setTheme: () => {},
      toggleTheme: () => {},
    }
  );
}
