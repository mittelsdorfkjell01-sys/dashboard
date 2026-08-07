// Admin back-office chrome: a sidebar nav + a top bar with the theme toggle,
// the signed-in user and logout. Child routes render into <Outlet />. Restyled
// to the independent admin design system (monochrome tokens + dark mode); the
// navigation structure, routes and behaviour are unchanged.

import { useEffect, useRef, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { roleLabel } from "../lib/labels";
import type { AdminRole } from "../lib/api";
import { Wordmark } from "./ui";
import NotificationBell from "./admin/NotificationBell";
import MediaBudgetIndicator from "./admin/MediaBudgetIndicator";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  role?: AdminRole;
  icon: ReactNode;
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
  review: (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
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
};

const NAV: NavItem[] = [
  { to: "/admin", label: "Übersicht", end: true, icon: I.overview },
  { to: "/admin/spots", label: "Spots", icon: I.spots },
  { to: "/admin/regions", label: "Regionen", icon: I.regions },
  { to: "/admin/review", label: "Review", icon: I.review },
  { to: "/admin/map", label: "Karte", icon: I.map },
  { to: "/admin/activity", label: "Aktivität", icon: I.activity },
  { to: "/admin/users", label: "Benutzer", role: "admin", icon: I.users },
];

function sideNavClass({ isActive }: { isActive: boolean }) {
  return [
    "group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-label font-medium transition-colors",
    isActive
      ? "bg-admin-hover text-admin-fg"
      : "text-admin-fg2 hover:bg-admin-hover hover:text-admin-fg",
  ].join(" ");
}

export default function AdminShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const mobileNavRef = useRef<HTMLElement>(null);
  const items = NAV.filter((n) => !n.role || n.role === user?.role);

  useEffect(() => {
    mobileNavRef.current
      ?.querySelector<HTMLElement>('[aria-current="page"]')
      ?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [location.pathname]);

  const onLogout = async () => {
    await logout();
    navigate("/admin/login");
  };

  return (
    <div className="min-h-screen bg-admin-bg text-admin-fg">
      <div className="flex">
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
            <p className="text-caption text-admin-faint">
              surfwind data · Back office
            </p>
          </div>
        </aside>

        {/* Content column */}
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-admin-border bg-admin-surface/90 px-4 py-2.5 backdrop-blur-sm sm:px-8">
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
                  <div className="mx-0.5 hidden h-5 w-px bg-admin-border sm:block" />
                  <span className="hidden items-center gap-2 text-label text-admin-fg sm:flex">
                    {user.display_name}
                    <span className="rounded-full border border-admin-border bg-admin-hover px-2 py-0.5 text-caption font-medium text-admin-muted">
                      {roleLabel(user.role)}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={onLogout}
                    className="rounded-md border border-admin-border bg-admin-surface px-3 py-1.5 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg"
                  >
                    Abmelden
                  </button>
                </>
              )}
            </div>
          </header>

          {/* Compact top nav — used below the sidebar breakpoint (tablet, half-screen, mobile). */}
          <nav
            ref={mobileNavRef}
            aria-label="Dashboard-Navigation"
            className="no-scrollbar flex max-w-full gap-1.5 overflow-x-auto overscroll-x-contain border-b border-admin-border bg-admin-surface px-4 py-2 lg:hidden"
          >
            {items.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  [
                    "flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-label font-medium transition-colors",
                    isActive
                      ? "bg-admin-hover text-admin-fg"
                      : "text-admin-fg2 hover:bg-admin-hover",
                  ].join(" ")
                }
              >
                <span className="grid h-4 w-4 place-items-center [&_svg]:h-4 [&_svg]:w-4">
                  {n.icon}
                </span>
                {n.label}
              </NavLink>
            ))}
          </nav>

          <main className="px-4 py-6 sm:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
