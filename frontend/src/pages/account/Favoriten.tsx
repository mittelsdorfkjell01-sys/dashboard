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
      <div className="rounded-2xl border border-dashed border-line bg-white px-6 py-14 text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-band text-teal">
          <HeartFilledIcon className="text-[24px]" />
        </span>
        <h2 className="mt-4 text-[17px] font-semibold text-ink">
          Noch keine Favoriten
        </h2>
        <p className="mx-auto mt-1 max-w-[38ch] text-[14px] text-muted">
          Tippe auf das Herz an einem Spot, um ihn hier zu sammeln.
        </p>
        <Link
          to="/search"
          className="mt-5 inline-flex items-center gap-2 rounded-xl bg-teal px-4 py-2 text-[14px] font-medium text-white transition-colors hover:bg-teal-hover"
        >
          <SearchIcon className="text-[16px]" />
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
          className="flex items-center gap-3 rounded-2xl border border-line bg-white p-3.5"
        >
          <Link to={spotPath(f)} className="min-w-0 flex-1">
            <span className="block truncate text-[15px] font-semibold text-ink">
              {f.name}
            </span>
            <span className="block truncate text-[12px] text-muted">
              {[f.region, (f.sports ?? []).map(sportLabel).join(", ")]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </Link>
          <button
            type="button"
            onClick={() => removeFavorite(f.id)}
            aria-label={`${f.name} aus Favoriten entfernen`}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-2xl text-orange transition-colors hover:bg-band"
          >
            <HeartFilledIcon className="text-[20px]" />
          </button>
        </li>
      ))}
    </ul>
  );
}
