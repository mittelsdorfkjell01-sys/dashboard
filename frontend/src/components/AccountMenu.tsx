import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MenuIcon, UserIcon, CloseIcon, SearchIcon } from "../lib/icons";
import { useAuth } from "../context/AuthContext";
import { initialsOf } from "../lib/initials";
import { useDesktopViewport } from "../lib/useAutoHideHeader";
import ThemeToggle from "./ThemeToggle";
import LanguageSwitcher from "./LanguageSwitcher";
import { buildMenuSearchIndex, searchMenu } from "../lib/menuSearch";
import { consumeAccountMenuRequest } from "../lib/accountMenuReturn";
import type { TranslationKey } from "../lib/i18n";

interface NavItem {
  /** Catalogue key, resolved at render — see lib/i18n/locales/de.ts. */
  key: TranslationKey;
  to: string;
  planned?: boolean;
}

/**
 * The site's own destinations, listed right under the search. The legal pages
 * are not among them: they stay in the footer, and the search reaches them.
 * `signedOutOnly`: "Spot vorschlagen" leads to the same page as the account
 * row "Spots hinzufügen", so a signed-in visitor would see it twice.
 */
const SITE_NAV: (NavItem & { signedOutOnly?: boolean; fromMenu?: boolean })[] = [
  { key: "menu.search.map", to: "/map" },
  { key: "siteLinks.faq", to: "/fragen", fromMenu: true },
  { key: "siteLinks.contact", to: "/kontakt", fromMenu: true },
  { key: "menu.suggestSpot", to: "/konto/spots", signedOutOnly: true },
];

const ACCOUNT_NAV: NavItem[] = [
  { key: "accountNav.profile", to: "/konto/profil" },
  { key: "accountNav.setup", to: "/konto/setup" },
  { key: "accountNav.saved", to: "/konto/favoriten" },
  { key: "accountNav.visited", to: "/konto/besucht" },
  { key: "accountNav.trips", to: "/konto/reisen" },
  { key: "accountNav.addSpots", to: "/konto/spots" },
  { key: "accountNav.settings", to: "/konto/einstellungen" },
];

/**
 * The burger menu shared by every public header. On phones it opens a
 * full-screen sheet (focus-trapped, body-scroll-locked, returns focus to the
 * trigger on close); from `sm` up it is a compact dropdown. Both read in the
 * same order, top to bottom:
 *
 *   1. a low search field, just the magnifier, over features and the
 *      sections of the info pages,
 *   2. the site's own destinations (wind map, help, contact, and — signed
 *      out — suggesting a spot),
 *   3. one hairline, then the account areas and sign-out — signed in only,
 *   4. at the foot: the two display preferences (dark mode, language), and
 *      under them who you are — avatar + name, or "Anmelden" when signed out.
 *
 * Plain text rows: no icons, regular weight, the 12px caption size — the menu
 * is an index, not a set of buttons. "Anmelden" is the exception, see
 * SignInRow.
 *
 * The three legal pages are not rows here: they live in the footer
 * (lib/siteLinks.ts), and the search reaches every one of their sections.
 */
export default function AccountMenu({
  bareOnMobile = false,
  onHero = false,
  onOpenChange,
}: {
  bareOnMobile?: boolean;
  /** The trigger sits on the landing hero photo: keep it brand-dark in both
   *  themes (see `.on-hero-ink`). Never applied to the menu itself, which is a
   *  normal themed surface. */
  onHero?: boolean;
  /** Fires whenever the menu opens or closes, so a header that sits in a lower
   *  stacking layer than the page content below it can lift itself while the
   *  dropdown is out (see LandingHeader: the landing's hero search bar is
   *  `z-modal` and otherwise paints over the open dropdown). */
  onOpenChange?: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const desktop = useDesktopViewport();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    onOpenChange?.(open);
  }, [open, onOpenChange]);

  // A page reached from this menu can send the visitor back into it (see
  // lib/accountMenuReturn). The request outlives the history step; the first
  // menu to mount afterwards takes it.
  useEffect(() => {
    if (consumeAccountMenuRequest()) setOpen(true);
  }, [location.key]);

  // Stable on purpose: the sheet's open/close effect depends on it, and a new
  // function on every render re-ran that effect — which moved focus from the
  // search field to the close button whenever the page re-rendered under an
  // open menu (data arriving, the session check resolving).
  const close = useCallback(() => setOpen(false), []);

  const onLogout = async () => {
    close();
    await logout();
    navigate("/");
  };

  // Preserve where the visitor was so protected areas and sign-in return here.
  const here = location.pathname + location.search;
  const signInHref = `/anmelden?redirect=${encodeURIComponent(here)}`;

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={t("menu.trigger")}
        className={`flex h-11 w-11 items-center justify-center p-0 text-ink transition-opacity hover:opacity-60 sm:w-auto sm:gap-2.5 sm:px-2 ${bareOnMobile ? "max-sm:justify-end" : ""} ${onHero ? "on-hero-ink" : ""}`}
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
        <DesktopDropdown user={user} onClose={close} onLogout={onLogout} signInHref={signInHref} />
      )}

      {open && !desktop && (
        <MobileSheet
          user={user}
          onClose={close}
          onLogout={onLogout}
          returnFocusRef={triggerRef}
          signInHref={signInHref}
        />
      )}
    </div>
  );
}

type Account = ReturnType<typeof useAuth>["user"];

const ROW_FOCUS =
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink";

/** Who you are, at the foot of the menu. Links to the profile. There is no
 *  photo backend yet, so the avatar is the initials disc used site-wide. */
function ProfileRow({
  user,
  onNavigate,
  className,
}: {
  user: NonNullable<Account>;
  onNavigate: () => void;
  className: string;
}) {
  const { t } = useTranslation();
  return (
    <Link to="/konto/profil" onClick={onNavigate} className={className}>
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-ink text-caption font-semibold text-surface">
        {initialsOf(user.displayName, user.email)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate">{user.displayName || t("menu.myProfile")}</span>
        <span className="block truncate text-muted">{user.email}</span>
      </span>
    </Link>
  );
}

/** The signed-out foot: one row, in the place the profile would be. Creating
 *  an account is one tap further, on the sign-in page itself. The one row
 *  that keeps a glyph and weight (2026-11-19): it is the menu's single call
 *  to act, and it fills the slot the avatar takes when signed in. */
function SignInRow({ href, onNavigate, className }: { href: string; onNavigate: () => void; className: string }) {
  const { t } = useTranslation();
  return (
    <Link to={href} onClick={onNavigate} className={className}>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-band text-ink">
        <UserIcon className="text-body" />
      </span>
      <span className="flex-1 text-ui font-semibold">{t("menu.signIn")}</span>
    </Link>
  );
}

/**
 * The search field and, while it holds a query, its results. While searching
 * the results replace the rest of the menu, so a phone shows them directly
 * under the field.
 */
function MenuSearch({
  query,
  onQueryChange,
  onNavigate,
  rowClass,
  autoFocus = false,
}: {
  query: string;
  onQueryChange: (q: string) => void;
  onNavigate: () => void;
  rowClass: string;
  autoFocus?: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const listId = useId();
  // `t` is re-bound on a language change, so the translated labels follow.
  const index = useMemo(() => buildMenuSearchIndex(t), [t]);
  const results = useMemo(() => searchMenu(index, query), [index, query]);
  const searching = query.trim() !== "";

  return (
    <div>
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          const first = results[0];
          if (!first) return;
          onNavigate();
          navigate(first.to, { state: { fromMenu: true } });
        }}
        className="relative"
      >
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ui text-muted" />
        {/* A low field, not the shared form Input: 36px, and no placeholder:
            the magnifier says what it is, the label names it for screen
            readers. Typed text is 12px from sm up; phones keep 16px, the size
            below which iOS zooms the page into a focused field. */}
        <input
          type="search"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={(e) => {
            // Escape first empties the field; a second Escape closes the menu.
            if (e.key === "Escape" && query) {
              e.nativeEvent.stopImmediatePropagation();
              onQueryChange("");
            }
          }}
          aria-label={t("menu.search.label")}
          aria-controls={searching ? listId : undefined}
          enterKeyHint="go"
          autoComplete="off"
          // Desktop only (see DesktopDropdown): a keyboard is already there.
          autoFocus={autoFocus}
          // The browser's own clear-× is a blue glyph from outside the system;
          // Escape and backspace already empty the field.
          // No focus edge (2026-11-20, user decision for this field only): a
          // text field matches :focus-visible on every tap, and the global
          // 2px edge in `ink` read as a white ring in dark mode. The caret is
          // the focus signal here, as on the comment fields. `!` beats the
          // global rule's !important (class over :where specificity).
          className="h-9 w-full rounded-card border border-line bg-surface pl-9 pr-3 text-body text-ink outline-none transition-[border-color] placeholder:text-muted hover:border-muted focus-visible:!outline-none sm:text-caption [&::-webkit-search-cancel-button]:appearance-none"
        />
      </form>

      {searching && (
        <div id={listId} className="mt-3">
          {results.length > 0 ? (
            <ul aria-label={t("menu.search.results")}>
              {results.map((r) => (
                <li key={r.id}>
                  <Link to={r.to} state={{ fromMenu: true }} onClick={onNavigate} className={rowClass}>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{r.label}</span>
                      <span className="block truncate text-muted">{r.context}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p role="status" className="px-3 py-3 text-caption text-muted">
              {t("menu.search.empty", { query: query.trim() })}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** The two display preferences, at the foot directly above sign-in or the
 *  profile: identical rows, label left and switch right. */
function MenuPrefs() {
  return (
    <div className="mb-2">
      <ThemeToggle variant="menu" />
      <LanguageSwitcher variant="menu" />
    </div>
  );
}

/** The menu under the search: destinations, the account, and at the foot who
 *  you are. */
function MenuBody({
  user,
  onClose,
  onLogout,
  signInHref,
  rowClass,
}: {
  user: Account;
  onClose: () => void;
  onLogout: () => void;
  signInHref: string;
  rowClass: string;
}) {
  const { t } = useTranslation();
  return (
    <>
      <nav aria-label={t("menu.explore")} className="mt-2">
        {SITE_NAV.filter((item) => !(user && item.signedOutOnly)).map(({ key, to, fromMenu }) => (
          <Link key={to} to={to} state={fromMenu ? { fromMenu: true } : undefined} onClick={onClose} className={rowClass}>
            {t(key)}
          </Link>
        ))}
      </nav>

      {/* One hairline where the kind of content changes: the site above, the
          visitor's own account below. */}
      {user && (
        <nav aria-label={t("menu.areas")} className="mt-2 border-t border-line pt-2">
          {ACCOUNT_NAV.map(({ key, to, planned }) => (
            <Link key={to} to={to} onClick={onClose} className={rowClass}>
              <span className="flex-1">{t(key)}</span>
              {planned && <span className="text-muted">{t("menu.planned")}</span>}
            </Link>
          ))}
          <button type="button" onClick={onLogout} className={`${rowClass} w-full text-left`}>
            {t("menu.signOut")}
          </button>
        </nav>
      )}

      {/* The foot, pinned to the bottom of the sheet and last in the
          dropdown: the display preferences, then who you are. A hairline,
          because what follows is settings and identity, not places to go. */}
      <div className="mt-auto pt-4">
        <div className="border-t border-line pt-2">
          <MenuPrefs />
        </div>
        {/* Clear air between the preferences and who you are (2026-11-20):
            the hairline and the two switches sit higher, so sign-in / the
            profile row stands on its own at the very foot. */}
        <div className="mt-6">
          {user ? (
            <ProfileRow user={user} onNavigate={onClose} className={rowClass} />
          ) : (
            <SignInRow href={signInHref} onNavigate={onClose} className={rowClass} />
          )}
        </div>
      </div>
    </>
  );
}

// --- desktop dropdown ------------------------------------------------------

function DesktopDropdown({
  user,
  onClose,
  onLogout,
  signInHref,
}: {
  user: Account;
  onClose: () => void;
  onLogout: () => void;
  signInHref: string;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
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

  const rowClass = `flex min-h-10 items-center gap-3 rounded-card px-3 text-caption text-ink transition-colors hover:bg-band ${ROW_FOCUS}`;

  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={t("menu.trigger")}
      className="absolute right-0 top-[calc(100%+10px)] hidden max-h-[calc(100svh-6rem)] w-80 flex-col overflow-y-auto overscroll-contain rounded-card bg-surface p-2 shadow-float ring-1 ring-line sm:flex"
    >
      <MenuSearch query={query} onQueryChange={setQuery} onNavigate={onClose} rowClass={rowClass} autoFocus />
      {!query.trim() && (
        <MenuBody user={user} onClose={onClose} onLogout={onLogout} signInHref={signInHref} rowClass={rowClass} />
      )}
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
}: {
  user: Account;
  onClose: () => void;
  onLogout: () => void;
  returnFocusRef: React.RefObject<HTMLButtonElement>;
  signInHref: string;
}) {
  const { t } = useTranslation();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [query, setQuery] = useState("");
  // Read through a ref so the effect below runs once per opening, whatever the
  // parent passes: re-running it re-focuses the close button.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Body-scroll lock + Escape + focus return, mirroring the map fullscreen and
  // gallery overlays already used on the site.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const trigger = returnFocusRef.current;
    // The close button, not the search field: focusing the field would put
    // the keyboard over half the menu on every tap of the burger.
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCloseRef.current();
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
  }, [returnFocusRef]);

  // 12px regular rows, like the dropdown; the tap target stays 44px.
  const rowClass = `flex min-h-11 items-center gap-3 rounded-card px-3 text-caption text-ink transition-colors active:bg-band ${ROW_FOCUS}`;

  return createPortal(
    <div className="fixed inset-0 z-menu flex flex-col bg-page sm:hidden" role="dialog" aria-modal="true" aria-label={t("menu.trigger")}>
      <div ref={panelRef} className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-3">
        {/* The close affordance alone on the top line, top-right. */}
        <div className="flex justify-end">
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label={t("menu.close")}
            className={`grid h-11 w-11 place-items-center rounded-full text-ink ${ROW_FOCUS}`}
          >
            <CloseIcon className="text-title" />
          </button>
        </div>

        <MenuSearch query={query} onQueryChange={setQuery} onNavigate={onClose} rowClass={rowClass} />

        {!query.trim() && (
          <MenuBody user={user} onClose={onClose} onLogout={onLogout} signInHref={signInHref} rowClass={rowClass} />
        )}
      </div>
    </div>,
    document.body,
  );
}
