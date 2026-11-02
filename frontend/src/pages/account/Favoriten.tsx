import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
    catch { setActionError(t("favorites.removeFailed")); }
    finally { setBusyId(null); }
  };

  if (state.status === "loading" && state.items.length === 0)
    return <AccountPage title={t("favorites.title")}><p role="status" className="py-12 text-center text-ui text-muted">{t("common.loading")}</p></AccountPage>;
  if (state.status === "error")
    return <AccountPage title={t("favorites.title")}><div role="alert" className="rounded-card border border-line p-6 text-ui"><p>{state.error}</p><button type="button" onClick={() => void refreshFavorites()} className="mt-3 min-h-11 font-semibold underline">{t("common.retry")}</button></div></AccountPage>;

  if (state.items.length === 0) {
    return (
      <AccountPage title={t("favorites.title")}>
        <div className="rounded-card border border-dashed border-line bg-surface px-6 py-14 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-card bg-band text-ink">
            <BookmarkFilledIcon className="text-title" />
          </span>
          <h2 className="mt-4 text-body font-semibold text-ink">
            {t("favorites.emptyTitle")}
          </h2>
          <p className="mx-auto mt-1 max-w-[38ch] text-ui text-muted">
            {t("favorites.emptyBody")}
          </p>
          <Link
            to="/search"
            className="mt-5 inline-flex items-center gap-2 px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          >
            <SearchIcon className="text-body" />
            {t("favorites.discover")}
          </Link>
        </div>
      </AccountPage>
    );
  }

  return (
    <AccountPage title={t("favorites.title")} intro={t("favorites.count", { count: state.items.length })}>
    {actionError && <p role="alert" className="mb-3 text-ui text-danger">{actionError}</p>}
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {state.items.map((f) => (
        <li
          key={f.id}
          className="flex items-center gap-3 rounded-card border border-line bg-surface p-3.5"
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
            aria-label={t("favorites.remove", { name: f.name })}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-card text-ink transition-colors hover:bg-band"
          >
            <BookmarkFilledIcon className="text-lead" />
          </button>
          <Link to={`/konto/reisen?spotId=${encodeURIComponent(f.id)}&spotName=${encodeURIComponent(f.name)}`} className="min-h-11 content-center px-2 text-caption font-semibold text-ink underline">{t("favorites.plan")}</Link>
        </li>
      ))}
    </ul>
    {state.items.length > 1 && <section className="mt-8"><h2 className="text-title font-semibold text-ink">{t("favorites.compare")}</h2><p className="mt-1 text-ui text-muted">{t("favorites.compareHint")}</p><div className="mt-3 overflow-x-auto rounded-card border border-line"><table className="min-w-[44rem] w-full border-collapse bg-surface text-left text-ui"><thead><tr className="border-b border-line">{[t("favorites.property"), ...state.items.map((item) => item.name)].map((label) => <th key={label} className="p-3 font-semibold text-ink">{label}</th>)}</tr></thead><tbody>{([
      [t("favorites.sports"), (item: FavoriteSpot) => (item.sports ?? []).map(sportLabel).join(", ")],
      [t("favorites.level"), (item: FavoriteSpot) => (item.levels ?? []).join(", ")],
      [t("favorites.water"), (item: FavoriteSpot) => (item.waterCharacter ?? []).join(", ")],
      [t("favorites.review"), (item: FavoriteSpot) => item.contentStatus === "verified" ? t("favorites.verified") : t("favorites.pending")],
      [t("favorites.region"), (item: FavoriteSpot) => item.region ?? ""],
    ] as Array<[string, (item: FavoriteSpot) => string]>).map(([label, value]) => <tr key={label} className="border-b border-line last:border-0"><th className="p-3 font-semibold text-muted">{label}</th>{state.items.map((item) => <td key={item.id} className="p-3 text-ink-soft">{value(item) || t("favorites.unknown")}</td>)}</tr>)}</tbody></table></div></section>}
    </AccountPage>
  );
}
