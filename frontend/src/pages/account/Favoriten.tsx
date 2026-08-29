import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  listFavorites,
  removeFavorite,
  FAVORITES_EVENT,
  type FavoriteSpot,
} from "../../lib/account";
import { sportLabel } from "../../lib/labels";
import { HeartFilledIcon, SearchIcon } from "../../lib/icons";
import { spotPath } from "../../lib/spotRoutes";

export default function Favoriten() {
  const [favs, setFavs] = useState<FavoriteSpot[]>(listFavorites);

  useEffect(() => {
    const refresh = () => setFavs(listFavorites());
    window.addEventListener(FAVORITES_EVENT, refresh);
    return () => window.removeEventListener(FAVORITES_EVENT, refresh);
  }, []);

  if (favs.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-surface px-6 py-14 text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-band text-teal">
          <HeartFilledIcon className="text-sz-24" />
        </span>
        <h2 className="mt-4 text-sz-17 font-semibold text-ink">
          Noch keine Favoriten
        </h2>
        <p className="mx-auto mt-1 max-w-[38ch] text-ui text-muted">
          Tippe auf das Herz an einem Spot, um ihn hier zu sammeln.
        </p>
        <Link
          to="/search"
          className="mt-5 inline-flex items-center gap-2 px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
        >
          <SearchIcon className="text-sz-16" />
          Spots entdecken
        </Link>
      </div>
    );
  }

  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {favs.map((f) => (
        <li
          key={f.id}
          className="flex items-center gap-3 rounded-2xl border border-line bg-surface p-3.5"
        >
          <Link to={spotPath(f)} className="min-w-0 flex-1">
            <span className="block truncate text-body font-semibold text-ink">
              {f.name}
            </span>
            <span className="block truncate text-caption text-muted">
              {[f.region, (f.sports ?? []).map(sportLabel).join(", ")]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </Link>
          <button
            type="button"
            onClick={() => removeFavorite(f.id)}
            aria-label={`${f.name} aus Favoriten entfernen`}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-orange transition-colors hover:bg-band"
          >
            <HeartFilledIcon className="text-sz-20" />
          </button>
        </li>
      ))}
    </ul>
  );
}
