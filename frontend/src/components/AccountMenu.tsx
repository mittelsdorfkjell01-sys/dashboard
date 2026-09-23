import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  MenuIcon,
  UserIcon,
  BookmarkIcon,
  PinIcon,
  SpotAddIcon,
  SchoolIcon,
  GearIcon,
  LogoutIcon,
  CloseIcon,
} from "../lib/icons";
import { useAuth } from "../context/AuthContext";
import { initialsOf } from "../lib/initials";
import { useDesktopViewport } from "../lib/useAutoHideHeader";
import ThemeToggle from "./ThemeToggle";

interface NavItem {
  label: string;
  to: string;
  icon: (p: { className?: string }) => ReactNode;
}

const ACCOUNT_NAV: NavItem[] = [
  { label: "Profil", to: "/konto/profil", icon: UserIcon },
  { label: "Mein Setup", to: "/konto/setup", icon: SchoolIcon },
  { label: "Saved", to: "/konto/favoriten", icon: BookmarkIcon },
  { label: "Spots besucht", to: "/konto/besucht", icon: PinIcon },
  { label: "Spots hinzufügen", to: "/konto/spots", icon: SpotAddIcon },
  { label: "Einstellungen", to: "/konto/einstellungen", icon: GearIcon },
];
const UTILITY: { label: string; to: string }[] = [
  { label: "Impressum", to: "/impressum" },
  { label: "Datenschutz", to: "/datenschutz" },
];

/**
 * Account entry point shared by every public header. On phones it opens a
 * full-screen sheet (large tap targets, focus-trapped, body-scroll-locked,
 * returns focus to the trigger on close); from `sm` up it is a compact
 * dropdown. Signed-in visitors see their name + avatar and the account areas;
 * signed-out visitors get a clear sign-in / register entry that returns them to
 * the page they were on after authenticating.
 */
export default function AccountMenu({ bareOnMobile = false }: { bareOnMobile?: boolean }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const desktop = useDesktopViewport();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const close = () => setOpen(false);

  const onLogout = async () => {
    close();
    await logout();
    navigate("/");
  };

  // Preserve where the visitor was so protected areas and sign-in return here.
  const here = location.pathname + location.search;
  const signInHref = `/anmelden?redirect=${encodeURIComponent(here)}`;
  const registerHref = `/anmelden?mode=register&redirect=${encodeURIComponent(here)}`;

  return (
    <div className="relative">
      <button
        ref={triggerRef}
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

      {/* Only the variant for the current breakpoint is mounted. Rendering both
          at once (CSS-hidden) kept the desktop dropdown's document `mousedown`
          outside-click listener alive on mobile: a tap on the portaled sheet
          counted as "outside", closing the menu on mousedown so the link's
          click never fired — the sheet just closed and no navigation happened. */}
      {open && desktop && (
        <DesktopDropdown
          user={user}
          onClose={close}
          onLogout={onLogout}
          signInHref={signInHref}
          registerHref={registerHref}
        />
      )}

      {open && !desktop && (
        <MobileSheet
          user={user}
          onClose={close}
          onLogout={onLogout}
          returnFocusRef={triggerRef}
          signInHref={signInHref}
          registerHref={registerHref}
        />
      )}
    </div>
  );
}

type Account = ReturnType<typeof useAuth>["user"];

function ProfileHeader({
  user,
  onNavigate,
  size = "sm",
}: {
  user: NonNullable<Account>;
  onNavigate: () => void;
  size?: "sm" | "lg";
}) {
  const lg = size === "lg";
  return (
    <Link
      to="/konto/profil"
      onClick={onNavigate}
      role="menuitem"
      className={`flex items-center rounded-2xl transition-colors hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${lg ? "gap-4 px-1 py-2" : "gap-3 px-2 py-2"}`}
    >
      <span
        className={`grid shrink-0 place-items-center rounded-full bg-ink font-bold text-surface ${lg ? "h-16 w-16 text-sz-22" : "h-11 w-11 text-label"}`}
      >
        {initialsOf(user.displayName, user.email)}
      </span>
      <span className="min-w-0">
        <span className={`block truncate font-semibold text-ink ${lg ? "text-sz-22" : "text-ui"}`}>
          {user.displayName || "Mein Profil"}
        </span>
        <span className={`block truncate text-muted ${lg ? "text-ui" : "text-caption"}`}>{user.email}</span>
      </span>
    </Link>
  );
}

function SignInBlock({ signInHref, registerHref, onNavigate }: { signInHref: string; registerHref: string; onNavigate: () => void }) {
  return (
    <div className="rounded-2xl bg-band p-4">
      <p className="text-ui font-semibold text-ink">Willkommen</p>
      <p className="mt-0.5 text-caption text-muted">Melde dich an, um Favoriten und eigene Spots zu verwalten.</p>
      <div className="mt-3 flex flex-col gap-2">
        <Link
          to={signInHref}
          onClick={onNavigate}
          role="menuitem"
          className="inline-flex min-h-11 items-center justify-center rounded-lg bg-ink px-4 text-ui font-semibold text-surface transition-colors hover:bg-ink-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          Anmelden
        </Link>
        <Link
          to={registerHref}
          onClick={onNavigate}
          role="menuitem"
          className="inline-flex min-h-11 items-center justify-center rounded-lg border border-line px-4 text-ui font-semibold text-ink transition-colors hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          Konto erstellen
        </Link>
      </div>
    </div>
  );
}

// --- desktop dropdown ------------------------------------------------------

function DesktopDropdown({
  user,
  onClose,
  onLogout,
  signInHref,
  registerHref,
}: {
  user: Account;
  onClose: () => void;
  onLogout: () => void;
  signInHref: string;
  registerHref: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const rowClass =
    "flex min-h-11 items-center gap-3 rounded-xl px-3 text-ui font-medium text-ink transition-colors hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

  return (
    <div
      ref={ref}
      role="menu"
      aria-label="Konto"
      className="absolute right-0 top-[calc(100%+10px)] hidden w-72 rounded-2xl bg-surface p-2 shadow-float ring-1 ring-line sm:block"
    >
      {user ? (
        <ProfileHeader user={user} onNavigate={onClose} />
      ) : (
        <SignInBlock signInHref={signInHref} registerHref={registerHref} onNavigate={onClose} />
      )}

      {user && (
        <div className="mt-1.5">
          {ACCOUNT_NAV.map(({ label, to, icon: Icon }) => (
            <Link key={to} to={to} role="menuitem" onClick={onClose} className={rowClass}>
              <Icon className="text-sz-18 text-muted" />
              {label}
            </Link>
          ))}
        </div>
      )}

      <div className="mt-1.5 border-t border-line pt-1.5">
        <ThemeToggle menuItem />
        {UTILITY.map((item) => (
          <Link key={item.label} to={item.to} role="menuitem" onClick={onClose} className={rowClass}>
            {item.label}
          </Link>
        ))}
        {user && (
          <button type="button" role="menuitem" onClick={onLogout} className={`${rowClass} w-full text-left`}>
            <LogoutIcon className="text-sz-18 text-muted" />
            Abmelden
          </button>
        )}
      </div>
    </div>
  );
}

// --- mobile full-screen sheet ----------------------------------------------

function MobileSheet({
  user,
  onClose,
  onLogout,
  returnFocusRef,
  signInHref,
  registerHref,
}: {
  user: Account;
  onClose: () => void;
  onLogout: () => void;
  returnFocusRef: React.RefObject<HTMLButtonElement>;
  signInHref: string;
  registerHref: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Body-scroll lock + Escape + focus return, mirroring the map fullscreen and
  // gallery overlays already used on the site.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const trigger = returnFocusRef.current;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      // Simple focus trap across the sheet's focusable elements.
      const focusables = panelRef.current?.querySelectorAll<HTMLElement>(
        'a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])',
      );
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKey);
      trigger?.focus();
    };
  }, [onClose, returnFocusRef]);

  // Editorial rows: icon + label, no chevron, generous tap targets — matching
  // the Figma account sheet (Frame 76).
  const rowClass =
    "flex min-h-[56px] items-center gap-5 rounded-2xl px-3 text-body font-medium text-ink transition-colors active:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

  return createPortal(
    <div className="fixed inset-0 z-[2000] flex flex-col bg-page sm:hidden" role="dialog" aria-modal="true" aria-label="Kontomenü">
      <div ref={panelRef} className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-3">
        {/* Just a close affordance, top-right, as in Figma. */}
        <div className="flex justify-end pb-4">
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Menü schließen"
            className="grid h-11 w-11 place-items-center rounded-full text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            <CloseIcon className="text-sz-24" />
          </button>
        </div>

        {user ? (
          <ProfileHeader user={user} onNavigate={onClose} size="lg" />
        ) : (
          <SignInBlock signInHref={signInHref} registerHref={registerHref} onNavigate={onClose} />
        )}

        {user && (
          <nav aria-label="Konto-Bereiche" className="mt-8">
            {ACCOUNT_NAV.map(({ label, to, icon: Icon }) => (
              <Link key={to} to={to} onClick={onClose} className={rowClass}>
                <Icon className="text-sz-24 text-ink" />
                <span className="flex-1">{label}</span>
              </Link>
            ))}
          </nav>
        )}

        {/* Darkmode switch sits on its own, set apart from the account areas. */}
        <div className="mt-6">
          <ThemeToggle variant="switch" />
        </div>

        {/* Legal links, pushed toward the foot of the sheet. */}
        <div className="mt-auto pt-10">
          {UTILITY.map((item) => (
            <Link key={item.label} to={item.to} onClick={onClose} className={`${rowClass} pl-3`}>
              <span className="flex-1">{item.label}</span>
            </Link>
          ))}

          {user && (
            <button type="button" onClick={onLogout} className={`${rowClass} mt-6 w-full text-left`}>
              <LogoutIcon className="text-sz-24 text-ink" />
              <span className="flex-1">abmelden</span>
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
