import { NavLink, Navigate, Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { Wordmark } from "../../components/ui";
import { HeartIcon, UserIcon, GridIcon, GearIcon, LogoutIcon } from "../../lib/icons";

const TABS = [
  { to: "/konto/profil", label: "Profil", icon: UserIcon },
  { to: "/konto/favoriten", label: "Favoriten", icon: HeartIcon },
  { to: "/konto/spots", label: "Hinzugefügte Spots", icon: GridIcon },
  { to: "/konto/einstellungen", label: "Kontoeinstellungen", icon: GearIcon },
];

/**
 * Shell for the signed-in account area: brand bar, a tab rail for the four
 * sub-pages, and an <Outlet/>. Redirects to /anmelden when signed out.
 */
export default function AccountLayout() {
  const { user, ready, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (!ready) return null;
  if (!user) {
    const redirect = encodeURIComponent(location.pathname);
    return <Navigate to={`/anmelden?redirect=${redirect}`} replace />;
  }

  const onLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-page">
      {/* brand bar */}
      <header className="border-b border-line bg-page/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1000px] items-center justify-between px-4 py-3.5 sm:px-8">
          <Link to="/" className="select-none" aria-label="Zur Startseite">
            <Wordmark size="sm" />
          </Link>
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-line px-3.5 py-1.5 text-label font-semibold text-ink transition-colors hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            <LogoutIcon className="text-sz-16" />
            <span className="hidden sm:inline">Abmelden</span>
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-[1000px] px-4 pb-24 pt-8 sm:px-8 sm:pt-12">
        <h1 className="text-sz-28 font-semibold text-ink sm:text-sz-32">Mein Konto</h1>
        <p className="mt-1 text-ui text-muted">
          Angemeldet als <span className="font-medium text-ink">{user.email}</span>
        </p>

        {/* tab rail — horizontally scrollable on phones, ink accent for the
            active area (editorial, not the public teal). */}
        <nav className="mt-6 flex gap-2 overflow-x-auto no-scrollbar [scrollbar-width:none]" aria-label="Konto-Bereiche">
          {TABS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex min-h-11 shrink-0 items-center gap-2 rounded-full px-4 text-ui font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
                  isActive ? "bg-ink text-surface" : "text-ink ring-1 ring-line hover:bg-band"
                }`
              }
            >
              <Icon className="text-sz-16" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
