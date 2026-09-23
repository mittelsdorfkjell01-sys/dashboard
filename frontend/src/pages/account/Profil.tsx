import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import {
  getFavoritesState,
  getSubmissionsState,
  refreshFavorites,
  refreshSubmissions,
  FAVORITES_EVENT,
  SUBMISSIONS_EVENT,
  type FavoriteSpot,
  type MySubmission,
  type CollectionState,
} from "../../lib/account";
import { initialsOf } from "../../lib/initials";
import { sportLabel } from "../../lib/labels";
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

  useEffect(() => {
    const refreshFavs = () => setFavState(getFavoritesState());
    const refreshSubs = () => setSubState(getSubmissionsState());
    window.addEventListener(FAVORITES_EVENT, refreshFavs);
    window.addEventListener(SUBMISSIONS_EVENT, refreshSubs);
    void refreshFavorites();
    void refreshSubmissions();
    return () => {
      window.removeEventListener(FAVORITES_EVENT, refreshFavs);
      window.removeEventListener(SUBMISSIONS_EVENT, refreshSubs);
    };
  }, []);

  if (!user) return null;

  const savedCount = favState.items.length;
  const addedCount = subState.items.length;
  const visitedCount = 0; // No visits backend yet — see BesuchteSpots.
  const sports = user.preferences?.sports ?? [];

  return (
    <div className="mx-auto max-w-[720px] pb-[max(3rem,env(safe-area-inset-bottom))]">
      {/* Hero band — cover photo lands here later; a calm sea gradient stands in
          for now (a placeholder image area, not fabricated content). */}
      <div className="relative h-52 w-full bg-gradient-to-br from-[#8fb8cc] via-[#5a8aa3] to-[#2f4f61] sm:rounded-b-[28px]" aria-hidden />

      <div className="px-5">
        {/* Avatar (overlapping the hero) + counts */}
        <div className="flex items-end justify-between gap-4 -mt-12">
          <span className="grid h-24 w-24 shrink-0 place-items-center rounded-full bg-ink text-sz-28 font-bold text-surface ring-4 ring-page">
            {initialsOf(user.displayName, user.email)}
          </span>
          <div className="flex items-center gap-5 pb-1">
            <StatLink to="/konto/favoriten" count={savedCount} label="gespeichert" icon={<BookmarkIcon className="text-sz-18" />} />
            <StatLink to="/konto/spots" count={addedCount} label="hinzugefügt" icon={<SpotAddIcon className="text-sz-18" />} />
            <StatLink to="/konto/besucht" count={visitedCount} label="besucht" icon={<PinIcon className="text-sz-18" />} />
          </div>
        </div>

        {/* Identity */}
        <div className="mt-4">
          <h1 className="truncate text-sz-24 font-semibold text-ink">{user.displayName || "Willkommen"}</h1>
          <p className="mt-1 text-ui text-muted">
            {sports.length > 0 ? sports.map(sportLabel).join(" · ") : "Sportart folgt"}
          </p>
          <p className="text-ui text-muted">Land folgt</p>
        </div>

        {/* Gear */}
        <section className="mt-10">
          <SectionHead
            icon={<SchoolIcon className="text-sz-22" />}
            title="Gear"
            right={
              <Link
                to="/konto/setup"
                aria-label="Mein Setup bearbeiten"
                title="Mein Setup bearbeiten"
                className="grid h-11 w-11 place-items-center rounded-full text-muted transition-colors hover:bg-band hover:text-ink"
              >
                <MoreIcon className="text-sz-20" />
              </Link>
            }
          />
          <p className="mt-1 text-ui text-muted">Deine Kites und dein Board verwalten</p>
          <Link
            to="/konto/setup"
            className="mt-4 inline-flex min-h-11 items-center rounded-lg border border-line bg-surface px-4 text-ui font-semibold text-ink transition-colors hover:bg-band"
          >
            Setup öffnen
          </Link>
        </section>

        {/* Spotsammlung — preview of visited spots */}
        <section className="mt-10">
          <SectionHead
            icon={<PinIcon className="text-sz-22" />}
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
            <p className="max-w-[46ch] text-ui text-muted">Die Spots, an denen du wirklich warst, sammeln sich hier.</p>
            <Link
              to="/search"
              className="mt-4 inline-flex items-center gap-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
            >
              <SearchIcon className="text-sz-16" />
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
      className="flex items-center gap-1.5 rounded-lg px-1 py-0.5 text-ink transition-opacity hover:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      <span className="text-sz-18 font-semibold tabular-nums">{count}</span>
      <span className="text-muted">{icon}</span>
    </Link>
  );
}

function SectionHead({ icon, title, right }: { icon: ReactNode; title: string; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="flex items-center gap-2.5 text-sz-18 font-semibold text-ink">
        <span className="text-ink">{icon}</span>
        {title}
      </h2>
      {right}
    </div>
  );
}

function PlannedBox({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3 rounded-[14px] border border-dashed border-line bg-surface px-5 py-8">
      <span className="inline-block rounded-full bg-band px-2.5 py-1 text-caption font-semibold uppercase tracking-wide text-muted">
        Geplant
      </span>
      <div className="mt-3 max-w-[46ch] text-ui text-muted">{children}</div>
    </div>
  );
}
