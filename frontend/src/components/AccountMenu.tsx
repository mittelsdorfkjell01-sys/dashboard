import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { MenuIcon, UserIcon } from "../lib/icons";
import { useAuth } from "../context/AuthContext";
import ThemeToggle from "./ThemeToggle";

const ACCOUNT_LINKS: { label: string; to: string }[] = [
  { label: "Profil", to: "/konto/profil" },
  { label: "Favoriten", to: "/konto/favoriten" },
  { label: "Hinzugefügte Spots", to: "/konto/spots" },
  { label: "Kontoeinstellungen", to: "/konto/einstellungen" },
];
const UTILITY: { label: string; to: string }[] = [
  { label: "Impressum", to: "/impressum" },
  { label: "Datenschutz", to: "/datenschutz" },
];

/** Text-and-icon account action + dropdown, shared by public headers. */
export default function AccountMenu({ bareOnMobile = false }: { bareOnMobile?: boolean }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const onLogout = async () => {
    setOpen(false);
    await logout();
    navigate("/");
  };

  const linkClass =
    "flex min-h-11 items-center px-3 text-ui font-medium text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Kontomenü"
        className={`flex h-11 w-11 items-center justify-center p-0 text-ink transition-opacity hover:opacity-60 sm:w-auto sm:gap-2.5 sm:px-2 ${bareOnMobile ? "max-sm:justify-end" : ""}`}
      >
        <MenuIcon className="text-sz-20" />
        <span className="hidden h-7 w-7 place-items-center sm:grid">
          <UserIcon className="text-sz-16" />
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            aria-label="Konto"
            initial={{ opacity: 0, y: reduce ? 0 : -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: reduce ? 0 : -6 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute right-0 top-[calc(100%+10px)] w-60 rounded-2xl bg-surface p-2"
          >
            {user ? (
              <>
                <div className="px-3 pb-2 pt-1">
                  <p className="truncate text-ui font-semibold text-ink">
                    {user.displayName}
                  </p>
                  <p className="truncate text-caption text-muted">{user.email}</p>
                </div>
                <div className="mt-2">
                  {ACCOUNT_LINKS.map((item) => (
                    <Link
                      key={item.to}
                      to={item.to}
                      role="menuitem"
                      onClick={() => setOpen(false)}
                      className={linkClass}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
                <div className="mt-2">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={onLogout}
                    className="flex min-h-11 w-full items-center px-3 text-left text-ui font-medium text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
                  >
                    Abmelden
                  </button>
                </div>
              </>
            ) : (
              <>
                <Link
                  to="/anmelden"
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className={linkClass}
                >
                  Anmelden
                </Link>
                <Link
                  to="/anmelden?mode=register"
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className={linkClass}
                >
                  Konto erstellen
                </Link>
              </>
            )}

            <div className="mt-2">
              <ThemeToggle menuItem />
              {UTILITY.map((item) => (
                <Link
                  key={item.label}
                  to={item.to}
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className={linkClass}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
