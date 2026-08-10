import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { MenuIcon, UserIcon } from "../lib/icons";
import { useAuth } from "../context/AuthContext";

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

/** Account pill + dropdown, shared by the landing and map/search headers. */
export default function AccountMenu() {
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
    "block rounded-xl px-3 py-2.5 text-[14px] font-medium text-ink transition-colors hover:bg-band";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Konto-Menü"
        className="flex h-9 w-9 items-center justify-center rounded-2xl bg-teal p-0 text-white transition-colors hover:bg-teal-hover sm:h-auto sm:w-auto sm:gap-2.5 sm:px-3.5 sm:py-2"
      >
        <MenuIcon className="text-[20px]" />
        <span className="hidden h-7 w-7 place-items-center rounded-full bg-white/20 sm:grid">
          <UserIcon className="text-[16px]" />
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
            className="absolute right-0 top-[calc(100%+10px)] w-60 rounded-2xl border border-line bg-surface p-2"
          >
            {user ? (
              <>
                <div className="px-3 pb-2 pt-1">
                  <p className="truncate text-[14px] font-semibold text-ink">
                    {user.displayName}
                  </p>
                  <p className="truncate text-[12px] text-muted">{user.email}</p>
                </div>
                <div className="border-t border-line pt-1">
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
                <div className="mt-1 border-t border-line pt-1">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={onLogout}
                    className="block w-full rounded-xl px-3 py-2.5 text-left text-[14px] font-medium text-teal transition-colors hover:bg-band"
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
                  className="mb-1 block rounded-xl bg-teal px-3 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-teal-hover"
                >
                  Konto erstellen
                </Link>
              </>
            )}

            <div className="mt-1 border-t border-line pt-1">
              {UTILITY.map((item) => (
                <Link
                  key={item.label}
                  to={item.to}
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className="block rounded-xl px-3 py-2.5 text-[14px] font-medium text-teal transition-colors hover:bg-band"
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
