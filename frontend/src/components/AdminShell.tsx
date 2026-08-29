// Admin back-office chrome: a sidebar nav + a top bar with the theme toggle,
// the signed-in user and logout. Child routes render into <Outlet />. Restyled
// to the independent admin design system (monochrome tokens + dark mode); the
// navigation structure, routes and behaviour are unchanged.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { roleLabel } from "../lib/labels";
import type { AdminRole } from "../lib/api";
import { Wordmark } from "./ui";
import { Button } from "./admin/ui";
import NotificationBell from "./admin/NotificationBell";
import MediaBudgetIndicator from "./admin/MediaBudgetIndicator";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  role?: AdminRole;
  icon: ReactNode;
  group: "Inhalte" | "Daten & Betrieb" | "Verwaltung";
}

// 16px line icons, stroke = currentColor, for a consistent quiet look.
const I = {
  overview: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="3" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  spots: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 21s-7-5.6-7-11a7 7 0 0 1 14 0c0 5.4-7 11-7 11Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx="12" cy="10" r="2.4" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  regions: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m9 4-6 2v14l6-2 6 2 6-2V4l-6 2-6-2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M9 4v14M15 6v14" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  hero: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="8.5" cy="10" r="1.6" stroke="currentColor" strokeWidth="1.6" />
      <path d="m4 17 5-4 3.5 3 3-2.5L20 17" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  weather: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M7.5 18.5h10a4 4 0 0 0 .5-8 6 6 0 0 0-11.4-1.7A4.9 4.9 0 0 0 7.5 18.5Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  review: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  tides: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M3 9c1.8 0 1.8-2 3.6-2s1.8 2 3.6 2 1.8-2 3.6-2 1.8 2 3.6 2 1.8-2 3.6-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3 15c1.8 0 1.8-2 3.6-2s1.8 2 3.6 2 1.8-2 3.6-2 1.8 2 3.6 2 1.8-2 3.6-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  map: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 12h18M12 3c2.5 2.5 3.8 5.6 3.8 9S14.5 18.5 12 21c-2.5-2.5-3.8-5.6-3.8-9S9.5 5.5 12 3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
  users: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="9" cy="8" r="3.2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3.5 20c0-3 2.5-5 5.5-5s5.5 2 5.5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M16 4.2A3.2 3.2 0 0 1 16 11m4.5 9c0-2.4-1.6-4.2-3.8-4.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  activity: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M3 12h4l2.5-7 5 14 2.5-7H21" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  operations: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 13a1 1 0 0 0 1-1l3-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5.5 18a8 8 0 1 1 13 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};

const NAV: NavItem[] = [
  // Frontend
  { to: "/admin", label: "Übersicht", end: true, icon: I.overview, group: "Inhalte" },
  { to: "/admin/spots", label: "Spots", icon: I.spots, group: "Inhalte" },
  { to: "/admin/hero", label: "Hero", icon: I.hero, group: "Inhalte" },
  { to: "/admin/regions", label: "Regionen", icon: I.regions, group: "Inhalte" },
  { to: "/admin/map", label: "Karte", icon: I.map, group: "Inhalte" },
  { to: "/admin/review", label: "Review", icon: I.review, group: "Inhalte" },
  // Backend
  { to: "/admin/operations", label: "Betrieb", icon: I.operations, group: "Daten & Betrieb" },
  { to: "/admin/weather", label: "Wetterprofile", icon: I.weather, group: "Daten & Betrieb" },
  { to: "/admin/tides", label: "Tidenkorrektur", icon: I.tides, group: "Daten & Betrieb" },
  // Admin
  { to: "/admin/users", label: "Benutzer", role: "admin", icon: I.users, group: "Verwaltung" },
  { to: "/admin/activity", label: "Aktivität", icon: I.activity, group: "Verwaltung" },
];

function sideNavClass({ isActive }: { isActive: boolean }) {
  return [
    "group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-label font-medium transition-colors",
    isActive
      ? "bg-admin-hover text-admin-fg"
      : "text-admin-fg2 hover:bg-admin-hover hover:text-admin-fg",
  ].join(" ");
}

function navItemMatches(item: NavItem, pathname: string): boolean {
  if (item.end) return pathname === item.to;
  if (pathname.startsWith(item.to)) return true;
  if (item.to === "/admin/spots") return pathname.startsWith("/admin/spot/");
  if (item.to === "/admin/regions") return pathname.startsWith("/admin/region/");
  if (item.to === "/admin/weather") return pathname.startsWith("/admin/weather-profile/");
  return false;
}

export default function AdminShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const headerStackRef = useRef<HTMLDivElement>(null);
  const contentColRef = useRef<HTMLDivElement>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const items = NAV.filter((n) => !n.role || n.role === user?.role);
  const activeItem = [...items]
    .sort((a, b) => b.to.length - a.to.length)
    .find((item) => navItemMatches(item, location.pathname)) ?? items[0];

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const closeOutside = (event: PointerEvent) => {
      if (!mobileMenuRef.current?.contains(event.target as Node)) setMobileMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileMenuOpen(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [mobileMenuOpen]);

  // Exposes the sticky header stack's real rendered height as a CSS var on
  // the content column, so page-level sticky sidebars (e.g. the spot/region
  // form's "Betrieb" panel) can pin themselves flush beneath it instead of
  // guessing a pixel offset — a mismatch there is what made those panels
  // visibly creep a few pixels before locking in place.
  useEffect(() => {
    const headerEl = headerStackRef.current;
    const contentEl = contentColRef.current;
    if (!headerEl || !contentEl) return;
    const update = () => {
      contentEl.style.setProperty("--admin-header-h", `${headerEl.offsetHeight}px`);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(headerEl);
    return () => ro.disconnect();
  }, []);

  const onLogout = async () => {
    await logout();
    navigate("/admin/login");
  };

  return (
    <div className="min-h-screen overflow-x-clip bg-admin-bg text-admin-fg">
      <div className="flex items-start">
        {/* Sidebar (desktop) */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-admin-border bg-admin-surface px-3 py-5 lg:flex">
          <Link to="/admin" className="px-2 py-1">
            <Wordmark size="md" tag="Admin" />
          </Link>
          <nav className="mt-7 flex flex-col gap-0.5">
            {items.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={sideNavClass}>
                {({ isActive }) => (
                  <>
                    <span
                      aria-hidden="true"
                      className={`absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-admin-primary transition-opacity ${
                        isActive ? "opacity-100" : "opacity-0"
                      }`}
                    />
                    <span className="grid h-[18px] w-[18px] place-items-center [&_svg]:h-[18px] [&_svg]:w-[18px]">
                      {n.icon}
                    </span>
                    {n.label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="mt-auto px-2 pt-4">
            <p className="text-caption text-admin-muted">
              surfwind data · Back office
            </p>
          </div>
        </aside>

        {/* Content column */}
        <div ref={contentColRef} className="min-w-0 flex-1">
          <div ref={headerStackRef} className="sticky top-0 z-20">
            <header className="flex min-h-16 items-center justify-between gap-3 border-b border-admin-border bg-admin-surface px-4 py-2 sm:bg-admin-surface/90 sm:px-8 sm:backdrop-blur-sm">
              {/* Brand — shown until the sidebar appears (lg). */}
              <Link to="/admin" className="lg:hidden">
                <Wordmark size="sm" tag="Admin" />
              </Link>
              <div className="hidden lg:block" />
              <div className="flex items-center gap-2 sm:gap-3">
                <MediaBudgetIndicator />
                <NotificationBell />
                {user && (
                  <>
                    <div className="mx-0.5 hidden h-5 w-px bg-admin-border lg:block" />
                    <span className="hidden items-center gap-2 text-label text-admin-fg lg:flex">
                      {user.display_name}
                      <span className="rounded-full border border-admin-border bg-admin-hover px-2 py-0.5 text-caption font-medium text-admin-muted">
                        {roleLabel(user.role)}
                      </span>
                    </span>
                    <Button variant="secondary" onClick={onLogout} className="hidden lg:inline-flex">
                      Abmelden
                    </Button>
                  </>
                )}
                <div ref={mobileMenuRef} className="relative lg:hidden">
                  <button
                    type="button"
                    aria-expanded={mobileMenuOpen}
                    aria-controls="admin-mobile-menu"
                    aria-label={mobileMenuOpen ? "Dashboard-Menü schließen" : "Dashboard-Menü öffnen"}
                    onClick={() => setMobileMenuOpen((open) => !open)}
                    className="admin-mobile-menu-trigger inline-flex min-h-11 items-center gap-2 rounded-md border border-admin-border bg-admin-surface px-3 text-sm font-medium text-admin-fg transition-colors hover:bg-admin-hover"
                  >
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-5 w-5">
                      {mobileMenuOpen ? (
                        <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                      ) : (
                        <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                      )}
                    </svg>
                    <span className="hidden max-w-28 truncate sm:inline">{activeItem?.label ?? "Menü"}</span>
                  </button>

                  {mobileMenuOpen && (
                    <div
                      id="admin-mobile-menu"
                      className="absolute right-0 top-[calc(100%+0.5rem)] w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-lg border border-admin-border bg-admin-elevated shadow-admin-pop"
                    >
                      <nav aria-label="Dashboard-Navigation" className="max-h-[calc(100dvh-6rem)] overflow-y-auto p-2">
                        {(["Inhalte", "Daten & Betrieb", "Verwaltung"] as const).map((group) => {
                          const groupItems = items.filter((item) => item.group === group);
                          if (groupItems.length === 0) return null;
                          return (
                            <div key={group} className="mt-2 first:mt-0">
                              <p className="px-3 pb-1 pt-2 text-caption font-semibold uppercase tracking-wide text-admin-muted">{group}</p>
                              {groupItems.map((item) => (
                                <NavLink
                                  key={item.to}
                                  to={item.to}
                                  end={item.end}
                                  className={({ isActive }) => `flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors ${isActive || navItemMatches(item, location.pathname) ? "bg-admin-hover text-admin-fg" : "text-admin-fg2 hover:bg-admin-hover hover:text-admin-fg"}`}
                                >
                                  <span className="grid h-5 w-5 place-items-center [&_svg]:h-5 [&_svg]:w-5">{item.icon}</span>
                                  {item.label}
                                </NavLink>
                              ))}
                            </div>
                          );
                        })}
                      </nav>
                      {user && (
                        <div className="flex items-center gap-3 border-t border-admin-border p-3">
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-admin-fg">{user.display_name}</p>
                            <p className="text-caption text-admin-muted">{roleLabel(user.role)}</p>
                          </div>
                          <Button variant="secondary" onClick={onLogout}>Abmelden</Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </header>
          </div>

          <main className="px-4 py-6 sm:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
