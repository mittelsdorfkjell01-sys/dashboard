import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import {
  getFavoritesState,
  getSubmissionsState,
  refreshFavorites,
  refreshSubmissions,
  refreshVisits,
  FAVORITES_EVENT,
  SUBMISSIONS_EVENT,
  VISITS_EVENT,
  getVisitsState,
  type FavoriteSpot,
  type MySubmission,
  type CollectionState,
  type VisitedSpot,
} from "../../lib/account";
import { initialsOf } from "../../lib/initials";
import { sportLabel } from "../../lib/labels";
import { spotPath } from "../../lib/spotRoutes";
import {
  BookmarkIcon,
  SpotAddIcon,
  PinIcon,
  SchoolIcon,
  MoreIcon,
  SearchIcon,
} from "../../lib/icons";

/**
 * Profile — a full-bleed screen matching Figma Frame 77: a hero band with the
 * avatar and saved/added/visited counts, the identity block, a "Gear" section
 * and a "Spotsammlung" preview.
 *
 * What has a backend today: the saved (favourites) and added (submissions)
 * counts. Everything else in the Figma — cover photo, avatar photo, sport +
 * country and the visited-spots collection — has no storage yet,
 * so it shows honest "Geplant" placeholders (matching the account-area
 * decision), never invented data. Wire each block to its API as it lands.
 */
export default function Profil() {
  const { user } = useAuth();
  const [favState, setFavState] = useState<CollectionState<FavoriteSpot>>(getFavoritesState);
  const [subState, setSubState] = useState<CollectionState<MySubmission>>(getSubmissionsState);
  const [visitState, setVisitState] = useState<CollectionState<VisitedSpot>>(getVisitsState);

  useEffect(() => {
    const refreshFavs = () => setFavState(getFavoritesState());
    const refreshSubs = () => setSubState(getSubmissionsState());
    const syncVisits = () => setVisitState(getVisitsState());
    window.addEventListener(FAVORITES_EVENT, refreshFavs);
    window.addEventListener(SUBMISSIONS_EVENT, refreshSubs);
    window.addEventListener(VISITS_EVENT, syncVisits);
    void refreshFavorites();
    void refreshSubmissions();
    void refreshVisits();
    return () => {
      window.removeEventListener(FAVORITES_EVENT, refreshFavs);
      window.removeEventListener(SUBMISSIONS_EVENT, refreshSubs);
      window.removeEventListener(VISITS_EVENT, syncVisits);
    };
  }, []);

  if (!user) return null;

  const savedCount = favState.items.length;
  const addedCount = subState.items.length;
  const visitedCount = visitState.items.length;
  const sports = user.preferences?.sports ?? [];

  return (
    <div className="mx-auto max-w-content pb-[max(3rem,env(safe-area-inset-bottom))]">
      {/* Hero band — cover photo lands here later; a calm sea gradient stands in
          for now (a placeholder image area, not fabricated content). */}
      <div className="relative h-52 w-full profile-cover-gradient sm:rounded-b-card" aria-hidden />

      <div className="px-5">
        {/* Avatar (overlapping the hero) + counts */}
        <div className="flex items-end justify-between gap-4 -mt-12">
          <span className="grid h-24 w-24 shrink-0 place-items-center rounded-full bg-ink text-heading font-bold text-surface ring-4 ring-page">
            {initialsOf(user.displayName, user.email)}
          </span>
          <div className="flex items-center gap-5 pb-1">
            <StatLink to="/konto/favoriten" count={savedCount} label="gespeichert" icon={<BookmarkIcon className="text-lead" />} />
            <StatLink to="/konto/spots" count={addedCount} label="hinzugefügt" icon={<SpotAddIcon className="text-lead" />} />
            <StatLink to="/konto/besucht" count={visitedCount} label="besucht" icon={<PinIcon className="text-lead" />} />
          </div>
        </div>

        {/* Identity */}
        <div className="mt-4">
          <h1 className="truncate text-title font-semibold text-ink">{user.displayName || "Willkommen"}</h1>
          {sports.length > 0 ? (
            <p className="mt-1 text-ui text-muted">{sports.map(sportLabel).join(" · ")}</p>
          ) : (
            <p className="mt-1 text-ui text-muted">
              Welche Sportarten interessieren dich?{" "}
              <Link to="/konto/einstellungen" className="font-semibold text-ink underline underline-offset-4 hover:opacity-70">
                Sportarten wählen
              </Link>
            </p>
          )}
        </div>

        {/* Gear */}
        <section className="mt-10">
          <SectionHead
            icon={<SchoolIcon className="text-title" />}
            title="Gear"
            right={
              <Link
                to="/konto/setup"
                aria-label="Mein Setup bearbeiten"
                title="Mein Setup bearbeiten"
                className="grid h-11 w-11 place-items-center rounded-full text-muted transition-colors hover:bg-band hover:text-ink"
              >
                <MoreIcon className="text-lead" />
              </Link>
            }
          />
          <p className="mt-1 text-ui text-muted">Deine Kites und dein Board verwalten</p>
          <Link
            to="/konto/setup"
            className="mt-4 inline-flex min-h-11 items-center rounded-card border border-line bg-surface px-4 text-ui font-semibold text-ink transition-colors hover:bg-band"
          >
            Setup öffnen
          </Link>
        </section>

        {/* Spotsammlung — preview of visited spots */}
        <section className="mt-10">
          <SectionHead
            icon={<PinIcon className="text-title" />}
            title="Spotsammlung"
            right={
              <Link
                to="/konto/besucht"
                className="text-ui font-medium text-muted underline underline-offset-4 transition-opacity hover:opacity-70"
              >
                mehr ansehen
              </Link>
            }
          />
          <PlannedBox>
            {visitState.items.length > 0 ? (
              <ul className="space-y-2">
                {visitState.items.slice(0, 3).map((visit) => (
                  <li key={visit.id}><Link to={spotPath({ id: visit.spotId, name: visit.name })} className="text-ui font-semibold text-ink underline underline-offset-4">{visit.name}</Link></li>
                ))}
              </ul>
            ) : <p className="max-w-[46ch] text-ui text-muted">Die Spots, an denen du wirklich warst, sammeln sich hier.</p>}
            <Link
              to="/search"
              className="mt-4 inline-flex items-center gap-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
            >
              <SearchIcon className="text-body" />
              Spots entdecken
            </Link>
          </PlannedBox>
        </section>
      </div>
    </div>
  );
}

function StatLink({ to, count, label, icon }: { to: string; count: number; label: string; icon: ReactNode }) {
  return (
    <Link
      to={to}
      aria-label={`${count} ${label}`}
      className="flex items-center gap-1.5 rounded-card px-1 py-0.5 text-ink transition-opacity hover:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      <span className="text-lead font-semibold tabular-nums">{count}</span>
      <span className="text-muted">{icon}</span>
    </Link>
  );
}

function SectionHead({ icon, title, right }: { icon: ReactNode; title: string; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="flex items-center gap-2.5 text-lead font-semibold text-ink">
        <span className="text-ink">{icon}</span>
        {title}
      </h2>
      {right}
    </div>
  );
}

function PlannedBox({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3 rounded-card border border-dashed border-line bg-surface px-5 py-8">
      <span className="inline-block rounded-card bg-band px-2.5 py-1 text-caption font-semibold uppercase tracking-wide text-muted">
        Geplant
      </span>
      <div className="mt-3 max-w-[46ch] text-ui text-muted">{children}</div>
    </div>
  );
}
