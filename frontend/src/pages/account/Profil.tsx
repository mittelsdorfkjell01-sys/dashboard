import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import {
  listFavorites,
  listMySubmissions,
  FAVORITES_EVENT,
  SUBMISSIONS_EVENT,
} from "../../lib/account";
import { HeartIcon, GridIcon } from "../../lib/icons";

function useCounts() {
  const [counts, setCounts] = useState({ fav: 0, subs: 0 });
  useEffect(() => {
    const refresh = () =>
      setCounts({ fav: listFavorites().length, subs: listMySubmissions().length });
    refresh();
    window.addEventListener(FAVORITES_EVENT, refresh);
    window.addEventListener(SUBMISSIONS_EVENT, refresh);
    return () => {
      window.removeEventListener(FAVORITES_EVENT, refresh);
      window.removeEventListener(SUBMISSIONS_EVENT, refresh);
    };
  }, []);
  return counts;
}

export default function Profil() {
  const { user } = useAuth();
  const counts = useCounts();
  if (!user) return null;

  const initials =
    user.displayName
      .split(/\s+/)
      .map((s) => s[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || user.email[0]?.toUpperCase();

  const memberSince = new Date(user.createdAt).toLocaleDateString("de-DE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-5 rounded-2xl border border-line bg-white p-6 sm:flex-row sm:items-center">
        <span className="grid h-20 w-20 shrink-0 place-items-center rounded-full bg-teal text-[26px] font-bold text-white">
          {initials}
        </span>
        <div className="min-w-0">
          <h2 className="truncate text-[22px] font-semibold text-ink">
            {user.displayName}
          </h2>
          <p className="truncate text-[14px] text-muted">{user.email}</p>
          <p className="mt-1 text-[13px] text-muted">
            Mitglied seit {memberSince}
          </p>
        </div>
        <Link
          to="/konto/einstellungen"
          className="shrink-0 rounded-xl bg-teal px-4 py-2 text-[14px] font-medium text-white transition-colors hover:bg-teal-hover sm:ml-auto"
        >
          Profil bearbeiten
        </Link>
      </section>

      <div className="grid grid-cols-2 gap-4">
        <StatCard
          to="/konto/favoriten"
          icon={<HeartIcon className="text-[20px]" />}
          value={counts.fav}
          label="Favoriten"
        />
        <StatCard
          to="/konto/spots"
          icon={<GridIcon className="text-[20px]" />}
          value={counts.subs}
          label="Hinzugefügte Spots"
        />
      </div>
    </div>
  );
}

function StatCard({
  to,
  icon,
  value,
  label,
}: {
  to: string;
  icon: ReactNode;
  value: number;
  label: string;
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-4 rounded-2xl border border-line bg-white p-5 transition-transform hover:-translate-y-0.5"
    >
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-band text-teal">
        {icon}
      </span>
      <span>
        <span className="block text-[24px] font-bold leading-none text-ink">
          {value}
        </span>
        <span className="mt-1 block text-[13px] text-muted">{label}</span>
      </span>
    </Link>
  );
}
