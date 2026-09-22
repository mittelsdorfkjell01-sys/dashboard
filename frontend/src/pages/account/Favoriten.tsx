import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getFavoritesState,
  removeFavorite,
  refreshFavorites,
  FAVORITES_EVENT,
  type FavoriteSpot,
  type CollectionState,
} from "../../lib/account";
import { sportLabel } from "../../lib/labels";
import { BookmarkFilledIcon, SearchIcon } from "../../lib/icons";
import { spotPath } from "../../lib/spotRoutes";
import { AccountPage } from "./AccountLayout";

export default function Favoriten() {
  const [state, setState] = useState<CollectionState<FavoriteSpot>>(getFavoritesState);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const refresh = () => setState(getFavoritesState());
    window.addEventListener(FAVORITES_EVENT, refresh);
    void refreshFavorites();
    return () => window.removeEventListener(FAVORITES_EVENT, refresh);
  }, []);

  const remove = async (id: string) => {
    setBusyId(id);
    setActionError(null);
    try { await removeFavorite(id); }
    catch { setActionError("Spot konnte nicht entfernt werden. Bitte versuche es erneut."); }
    finally { setBusyId(null); }
  };

  if (state.status === "loading" && state.items.length === 0)
    return <AccountPage title="Saved"><p role="status" className="py-12 text-center text-ui text-muted">Wird geladen …</p></AccountPage>;
  if (state.status === "error")
    return <AccountPage title="Saved"><div role="alert" className="rounded-2xl border border-line p-6 text-ui"><p>{state.error}</p><button type="button" onClick={() => void refreshFavorites()} className="mt-3 min-h-11 font-semibold underline">Erneut versuchen</button></div></AccountPage>;

  if (state.items.length === 0) {
    return (
      <AccountPage title="Saved">
        <div className="rounded-[14px] border border-dashed border-line bg-surface px-6 py-14 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-[14px] bg-band text-ink">
            <BookmarkFilledIcon className="text-sz-24" />
          </span>
          <h2 className="mt-4 text-sz-17 font-semibold text-ink">
            Noch nichts gespeichert
          </h2>
          <p className="mx-auto mt-1 max-w-[38ch] text-ui text-muted">
            Tippe an einem Spot auf das Lesezeichen, um ihn hier zu sammeln.
          </p>
          <Link
            to="/search"
            className="mt-5 inline-flex items-center gap-2 px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          >
            <SearchIcon className="text-sz-16" />
            Spots entdecken
          </Link>
        </div>
      </AccountPage>
    );
  }

  return (
    <AccountPage title="Saved" intro={`${state.items.length} ${state.items.length === 1 ? "Spot" : "Spots"} gespeichert`}>
    {actionError && <p role="alert" className="mb-3 text-ui text-danger">{actionError}</p>}
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {state.items.map((f) => (
        <li
          key={f.id}
          className="flex items-center gap-3 rounded-[14px] border border-line bg-surface p-3.5"
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
            onClick={() => void remove(f.id)}
            disabled={busyId === f.id}
            aria-label={`${f.name} aus Saved entfernen`}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] text-ink transition-colors hover:bg-band"
          >
            <BookmarkFilledIcon className="text-sz-20" />
          </button>
        </li>
      ))}
    </ul>
    </AccountPage>
  );
}
