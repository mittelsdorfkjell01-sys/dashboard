import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import {
  listFavorites,
  listMySubmissions,
  FAVORITES_EVENT,
  SUBMISSIONS_EVENT,
  type FavoriteSpot,
  type MySubmission,
} from "../../lib/account";
import { initialsOf } from "../../lib/initials";
import { sportLabel } from "../../lib/labels";
import { spotPath } from "../../lib/spotRoutes";
import {
  HeartIcon,
  GridIcon,
  ChevronRightIcon,
  SearchIcon,
  PlusCircleIcon,
} from "../../lib/icons";

/**
 * The signed-in visitor's private home. It shows only what the account actually
 * carries today — identity, saved (favourite) spots and proposed spots — each
 * with a clear next action when empty. Areas that are planned but not yet backed
 * by storage (description, preferred sports, own media, trips, travel reports, a
 * visited-spots map) appear as clearly-labelled "Geplant" tiles so the intended
 * structure is visible without pretending the features exist. This is the OWN
 * view; a public profile is a separate, not-yet-built surface.
 */
export default function Profil() {
  const { user } = useAuth();
  const [favs, setFavs] = useState<FavoriteSpot[]>(listFavorites);
  const [subs, setSubs] = useState<MySubmission[]>(listMySubmissions);

  useEffect(() => {
    const refreshFavs = () => setFavs(listFavorites());
    const refreshSubs = () => setSubs(listMySubmissions());
    window.addEventListener(FAVORITES_EVENT, refreshFavs);
    window.addEventListener(SUBMISSIONS_EVENT, refreshSubs);
    return () => {
      window.removeEventListener(FAVORITES_EVENT, refreshFavs);
      window.removeEventListener(SUBMISSIONS_EVENT, refreshSubs);
    };
  }, []);

  if (!user) return null;

  const memberSince = new Date(user.createdAt).toLocaleDateString("de-DE", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-10">
      {/* Identity */}
      <section className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <span className="grid h-20 w-20 shrink-0 place-items-center rounded-full bg-ink text-sz-26 font-bold text-surface">
          {initialsOf(user.displayName, user.email)}
        </span>
        <div className="min-w-0">
          <h2 className="truncate text-sz-24 font-semibold text-ink">{user.displayName || "Willkommen"}</h2>
          <p className="truncate text-ui text-muted">{user.email}</p>
          <p className="mt-1 text-label text-muted">Mitglied seit {memberSince}</p>
        </div>
        <Link
          to="/konto/einstellungen"
          className="shrink-0 self-start rounded-lg border border-line px-4 py-2 text-ui font-semibold text-ink transition-colors hover:bg-band sm:ml-auto sm:self-auto"
        >
          Profil bearbeiten
        </Link>
      </section>

      {/* Description + preferred sports — planned, shown so the IA is visible. */}
      <p className="max-w-[60ch] text-ui text-muted">
        <span className="mr-2 inline-flex items-center rounded-full bg-band px-2 py-0.5 text-caption font-semibold uppercase tracking-wide text-muted align-middle">
          Geplant
        </span>
        Eine kurze Beschreibung und deine bevorzugten Sportarten erscheinen hier, sobald
        sie zu deinem Konto gespeichert werden.
      </p>

      {/* Saved spots (favourites) */}
      <PreviewSection
        title="Gespeicherte Spots"
        count={favs.length}
        to="/konto/favoriten"
        icon={<HeartIcon className="text-sz-18" />}
        empty={
          <EmptyState
            icon={<HeartIcon className="text-sz-22" />}
            title="Noch keine gespeicherten Spots"
            hint="Tippe an einem Spot auf das Lesezeichen, um ihn hier zu sammeln."
            action={{ to: "/search", label: "Spots entdecken", icon: <SearchIcon className="text-sz-16" /> }}
          />
        }
      >
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {favs.slice(0, 4).map((f) => (
            <li key={f.id}>
              <Link
                to={spotPath(f)}
                className="flex min-h-[52px] items-center gap-3 rounded-2xl border border-line px-4 transition-colors hover:bg-band focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body font-semibold text-ink">{f.name}</span>
                  <span className="block truncate text-caption text-muted">
                    {[f.region, (f.sports ?? []).map(sportLabel).join(", ")].filter(Boolean).join(" · ")}
                  </span>
                </span>
                <ChevronRightIcon className="text-sz-16 text-muted" />
              </Link>
            </li>
          ))}
        </ul>
      </PreviewSection>

      {/* Proposed spots */}
      <PreviewSection
        title="Hinzugefügte Spots"
        count={subs.length}
        to="/konto/spots"
        icon={<GridIcon className="text-sz-18" />}
        empty={
          <EmptyState
            icon={<GridIcon className="text-sz-22" />}
            title="Noch keine Spots vorgeschlagen"
            hint="Fehlt ein Spot? Schlage ihn vor — wir prüfen ihn redaktionell."
            action={{ to: "/konto/spots", label: "Spot vorschlagen", icon: <PlusCircleIcon className="text-sz-18" /> }}
          />
        }
      >
        <ul className="space-y-2">
          {subs.slice(0, 3).map((s) => (
            <li key={s.id} className="flex min-h-[52px] items-center justify-between gap-3 rounded-2xl border border-line px-4">
              <span className="truncate text-body font-medium text-ink">{s.name}</span>
              <span className="shrink-0 text-caption text-muted">
                {new Date(s.createdAt).toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" })}
              </span>
            </li>
          ))}
        </ul>
      </PreviewSection>

      {/* Planned areas — information architecture only, not usable yet. */}
      <section>
        <h3 className="text-sz-16 font-semibold text-ink">Bald verfügbar</h3>
        <p className="mt-1 text-ui text-muted">Diese Bereiche folgen, sobald Speicherung, Rechte und Darstellung stehen.</p>
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {["Meine Medien", "Fahrten", "Reiseberichte", "Besuchte Spots"].map((label) => (
            <div
              key={label}
              aria-disabled="true"
              className="rounded-2xl border border-dashed border-line px-4 py-5 text-center"
            >
              <span className="block text-ui font-medium text-ink">{label}</span>
              <span className="mt-1 inline-block text-caption font-semibold uppercase tracking-wide text-muted">Geplant</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function PreviewSection({
  title,
  count,
  to,
  icon,
  empty,
  children,
}: {
  title: string;
  count: number;
  to: string;
  icon: ReactNode;
  empty: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-line pt-8">
      <div className="flex items-center justify-between gap-4">
        <h3 className="flex items-center gap-2 text-sz-16 font-semibold text-ink">
          <span className="text-muted">{icon}</span>
          {title}
          <span className="text-muted">· {count}</span>
        </h3>
        {count > 0 && (
          <Link
            to={to}
            className="shrink-0 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          >
            Alle ansehen
          </Link>
        )}
      </div>
      <div className="mt-4">{count === 0 ? empty : children}</div>
    </section>
  );
}

function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon: ReactNode;
  title: string;
  hint: string;
  action: { to: string; label: string; icon: ReactNode };
}) {
  return (
    <div className="rounded-2xl border border-dashed border-line px-6 py-10 text-center">
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-band text-ink">{icon}</span>
      <p className="mt-3 text-ui font-semibold text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-[40ch] text-ui text-muted">{hint}</p>
      <Link
        to={action.to}
        className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-lg bg-ink px-4 text-ui font-semibold text-surface transition-colors hover:bg-ink-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        {action.icon}
        {action.label}
      </Link>
    </div>
  );
}
