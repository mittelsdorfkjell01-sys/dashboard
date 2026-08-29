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
    <div className="min-h-screen bg-band">
      {/* brand bar */}
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1000px] items-center justify-between px-4 py-3.5 sm:px-8">
          <Link to="/" aria-label="surfwind data — Startseite" className="select-none">
            <Wordmark size="sm" />
          </Link>
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-2xl border border-line px-3.5 py-1.5 text-label font-medium text-teal transition-colors hover:bg-band"
          >
            <LogoutIcon className="text-sz-16" />
            Abmelden
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-8 sm:py-12">
        <h1 className="text-sz-32 font-semibold text-ink">Mein Konto</h1>
        <p className="mt-1 text-ui text-muted">
          Angemeldet als <span className="font-medium text-ink">{user.email}</span>
        </p>

        {/* tab rail */}
        <nav className="mt-6 flex gap-1.5 overflow-x-auto no-scrollbar" aria-label="Konto-Bereiche">
          {TABS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex shrink-0 items-center gap-2 rounded-2xl px-4 py-2 text-ui font-medium transition-colors ${
                  isActive
                    ? "bg-teal text-white"
                    : "bg-surface text-ink ring-1 ring-line hover:bg-teal/5"
                }`
              }
            >
              <Icon className="text-sz-16" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
