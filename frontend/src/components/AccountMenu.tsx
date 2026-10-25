import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  MenuIcon,
  UserIcon,
  SchoolIcon,
  LogoutIcon,
  CloseIcon,
  AccountProfileIcon,
  AccountSavedIcon,
  AccountVisitedIcon,
  AccountAddSpotsIcon,
  AccountSettingsIcon,
} from "../lib/icons";
import { useAuth } from "../context/AuthContext";
import { initialsOf } from "../lib/initials";
import { useDesktopViewport } from "../lib/useAutoHideHeader";
import ThemeToggle from "./ThemeToggle";
import { SITE_LINKS } from "../lib/siteLinks";
import type { TranslationKey } from "../lib/i18n";

interface NavItem {
  /** Catalogue key, resolved at render — see lib/i18n/locales/de.ts. */
  key: TranslationKey;
  to: string;
  icon: (p: { className?: string }) => ReactNode;
  planned?: boolean;
}

const ACCOUNT_NAV: NavItem[] = [
  { key: "accountNav.profile", to: "/konto/profil", icon: AccountProfileIcon },
  { key: "accountNav.setup", to: "/konto/setup", icon: SchoolIcon },
  { key: "accountNav.saved", to: "/konto/favoriten", icon: AccountSavedIcon },
  { key: "accountNav.visited", to: "/konto/besucht", icon: AccountVisitedIcon, planned: true },
  { key: "accountNav.addSpots", to: "/konto/spots", icon: AccountAddSpotsIcon },
  { key: "accountNav.settings", to: "/konto/einstellungen", icon: AccountSettingsIcon },
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
  const { t } = useTranslation();
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
        aria-label={t("menu.trigger")}
        className={`flex h-11 w-11 items-center justify-center p-0 text-ink transition-opacity hover:opacity-60 sm:w-auto sm:gap-2.5 sm:px-2 ${bareOnMobile ? "max-sm:justify-end" : ""}`}
      >
        <MenuIcon className="text-lead" />
        <span className="hidden h-7 w-7 place-items-center sm:grid">
          <UserIcon className="text-body" />
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
  const { t } = useTranslation();
  const lg = size === "lg";
  return (
    <Link
      to="/konto/profil"
      onClick={onNavigate}
      role="menuitem"
      className={`flex items-center rounded-card transition-colors hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${lg ? "gap-4 px-1 py-2" : "gap-3 px-2 py-2"}`}
    >
      <span
        className={`grid shrink-0 place-items-center rounded-full bg-ink font-bold text-surface ${lg ? "h-16 w-16 text-title" : "h-11 w-11 text-ui"}`}
      >
        {initialsOf(user.displayName, user.email)}
      </span>
      <span className="min-w-0">
        <span className={`block truncate font-semibold text-ink ${lg ? "text-title" : "text-ui"}`}>
          {user.displayName || t("menu.myProfile")}
        </span>
        <span className={`block truncate text-muted ${lg ? "text-ui" : "text-caption"}`}>{user.email}</span>
      </span>
    </Link>
  );
}

function SignInBlock({ signInHref, registerHref, onNavigate }: { signInHref: string; registerHref: string; onNavigate: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-card bg-band p-4">
      <p className="text-ui font-semibold text-ink">{t("menu.welcome")}</p>
      <p className="mt-0.5 text-caption text-muted">{t("menu.welcomeBody")}</p>
      <div className="mt-3 flex flex-col gap-2">
        <Link
          to={signInHref}
          onClick={onNavigate}
          role="menuitem"
          className="inline-flex min-h-11 items-center justify-center rounded-card bg-ink px-4 text-ui font-semibold text-surface transition-colors hover:bg-ink-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          {t("menu.signIn")}
        </Link>
        <Link
          to={registerHref}
          onClick={onNavigate}
          role="menuitem"
          className="inline-flex min-h-11 items-center justify-center rounded-card border border-line px-4 text-ui font-semibold text-ink transition-colors hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          {t("menu.createAccount")}
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
  const { t } = useTranslation();
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
    "flex min-h-11 items-center gap-3 rounded-card px-3 text-ui font-medium text-ink transition-colors hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

  return (
    <div
      ref={ref}
      role="menu"
      aria-label={t("menu.account")}
      className="absolute right-0 top-[calc(100%+10px)] hidden w-72 rounded-card bg-surface p-2 shadow-float ring-1 ring-line sm:block"
    >
      {user ? (
        <ProfileHeader user={user} onNavigate={onClose} />
      ) : (
        <SignInBlock signInHref={signInHref} registerHref={registerHref} onNavigate={onClose} />
      )}

      {user && (
        <div className="mt-1.5">
          {ACCOUNT_NAV.map(({ key, to, icon: Icon, planned }) => (
            <Link key={to} to={to} role="menuitem" onClick={onClose} className={rowClass}>
              <Icon className="text-lead text-muted" />
              <span className="flex-1">{t(key)}</span>
              {planned && <span className="text-caption font-semibold text-muted">{t("menu.planned")}</span>}
            </Link>
          ))}
        </div>
      )}

      <div className="mt-1.5 border-t border-line pt-1.5">
        <ThemeToggle menuItem />
        {SITE_LINKS.map((item) => (
          <Link key={item.to} to={item.to} role="menuitem" onClick={onClose} className={rowClass}>
            {t(item.key)}
          </Link>
        ))}
        {user && (
          <button type="button" role="menuitem" onClick={onLogout} className={`${rowClass} w-full text-left`}>
            <LogoutIcon className="text-lead text-muted" />
            {t("menu.signOut")}
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
  const { t } = useTranslation();
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
    "flex min-h-[56px] items-center gap-5 rounded-card px-3 text-body font-medium text-ink transition-colors active:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

  return createPortal(
    <div className="fixed inset-0 z-menu flex flex-col bg-page sm:hidden" role="dialog" aria-modal="true" aria-label={t("menu.trigger")}>
      <div ref={panelRef} className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-3">
        {/* Just a close affordance, top-right, as in Figma. */}
        <div className="flex justify-end pb-4">
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label={t("menu.close")}
            className="grid h-11 w-11 place-items-center rounded-full text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            <CloseIcon className="text-title" />
          </button>
        </div>

        {user ? (
          <ProfileHeader user={user} onNavigate={onClose} size="lg" />
        ) : (
          <SignInBlock signInHref={signInHref} registerHref={registerHref} onNavigate={onClose} />
        )}

        {user && (
          <nav aria-label={t("menu.areas")} className="mt-8">
            {ACCOUNT_NAV.map(({ key, to, icon: Icon, planned }) => (
              <Link key={to} to={to} onClick={onClose} className={rowClass}>
                <Icon className="text-title text-ink" />
                <span className="flex-1">{t(key)}</span>
                {planned && <span className="text-caption font-semibold text-muted">{t("menu.planned")}</span>}
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
          {SITE_LINKS.map((item) => (
            <Link key={item.to} to={item.to} onClick={onClose} className={`${rowClass} pl-3`}>
              <span className="flex-1">{t(item.key)}</span>
            </Link>
          ))}

          {user && (
            <button type="button" onClick={onLogout} className={`${rowClass} mt-6 w-full text-left`}>
              <LogoutIcon className="text-title text-ink" />
              <span className="flex-1">{t("menu.signOutSheet")}</span>
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
