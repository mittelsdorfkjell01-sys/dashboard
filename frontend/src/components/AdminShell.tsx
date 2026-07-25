// Admin back-office chrome (Sprint B): a sidebar nav + a top bar with the
// signed-in user and logout. Child routes render into <Outlet />.

import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { roleLabel } from "../lib/labels";
import type { AdminRole } from "../lib/api";
import { Wordmark } from "./ui";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  role?: AdminRole;
}

const NAV: NavItem[] = [
  { to: "/admin", label: "Übersicht", end: true },
  { to: "/admin/spots", label: "Spots" },
  { to: "/admin/regions", label: "Regionen" },
  { to: "/admin/review", label: "Review" },
  { to: "/admin/users", label: "Benutzer", role: "admin" },
];

function navClass({ isActive }: { isActive: boolean }) {
  return [
    "block rounded-xl px-3 py-2 text-[14px] font-medium transition-colors",
    isActive ? "bg-teal text-white" : "text-ink hover:bg-teal/5",
  ].join(" ");
}

export default function AdminShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = NAV.filter((n) => !n.role || n.role === user?.role);

  const onLogout = async () => {
    await logout();
    navigate("/admin/login");
  };

  return (
    <div className="min-h-screen bg-band">
      <div className="mx-auto flex max-w-[1400px]">
        {/* Sidebar (desktop) */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-white px-4 py-6 md:flex">
          <Link to="/admin" className="px-2">
            <Wordmark size="md" tag="Admin" />
          </Link>
          <nav className="mt-8 flex flex-col gap-1">
            {items.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={navClass}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        {/* Content column */}
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-line bg-white px-4 py-3 sm:px-8">
            {/* Mobile brand */}
            <Link to="/admin" className="md:hidden">
              <Wordmark size="sm" tag="Admin" />
            </Link>
            <div className="hidden md:block" />
            {user && (
              <div className="flex items-center gap-3">
                <span className="hidden items-center gap-2 text-[13px] text-ink sm:flex">
                  {user.display_name}
                  <span className="rounded-full bg-ink/5 px-2 py-0.5 text-[11px] font-medium text-muted">
                    {roleLabel(user.role)}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={onLogout}
                  className="rounded-full border border-teal/30 px-3 py-1.5 text-[13px] font-medium text-teal hover:bg-teal/5"
                >
                  Abmelden
                </button>
              </div>
            )}
          </header>

          {/* Mobile nav */}
          <nav className="flex gap-2 overflow-x-auto border-b border-line bg-white px-4 py-2 md:hidden">
            {items.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  [
                    "shrink-0 rounded-full px-3 py-1.5 text-[13px] font-medium",
                    isActive ? "bg-teal text-white" : "text-ink hover:bg-teal/5",
                  ].join(" ")
                }
              >
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
